from redbot.core import commands, checks, Config

import os
import asyncio
import re
from datetime import timedelta, datetime
import time
import pickle
import random
import math

from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import discord

from .createevent import CreateCalendarEvent

import importlib.util
spec = importlib.util.spec_from_file_location("module.name", os.path.dirname(os.path.realpath(__file__)) + "/../Logger/logger.py")
foo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(foo)

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar']

class Calendar(commands.Cog):
    """Calendar Cog for the Discord Bot.
       Implements Google Calendar Functionality with the bot."""

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=100000001)

        default_guild = {
            "calendarId": "primary",
            "calendarEventsChannel": None,
            
            "successEmoji": None,
            "cancelEmoji": None,
            "eventMessageFunctionEmojis": None,
            
            "usersConverter": [],
            "eventMessages": [],
        }
        self.config.register_guild(**default_guild)
        
        self.ignoreEmojiEvents = []
        self.runningEventRequests = []
        
        self.maxAttendeesInRowToSplit = 10
        
        #TODO: Store in config
        self.tokenFilePath = 'token.pickle'
        
        self.colors = None
        
         # Get the google calendar service
        service = self.get_calendar_service()
        if service:
            self.colors = service.colors().get().execute()
        
        self.prevUpdateTime = datetime.utcnow() - timedelta(25)
        # Update interval in seconds
        self.updateIntervalTime = 30
        # Init all the guilds steam builds
        self.loop = asyncio.get_event_loop()
        self.task = self.loop.create_task(self.updateCalendarEventsInGuilds())
        
    def __del__(self):
        if self.task:
            # End the auto update loop
            print("Del: Stopping Calendar Update Loop")
            self.task.cancel()
        
    def cog_unload(self):
        # End the auto update loop
        print("cog_unload: Stopping Calendar Update Loop")
        self.task.cancel()
        self.task = None
            
    async def updateCalendarEventsInGuilds(self):
        while True:
            try:
                print("Updating Calendar Events")
                
                # Get the google calendar service
                service = self.get_calendar_service()
                if not service:
                    print("Update Calendar Error: Invalid Service. Try logging the service in again!")
                    return
                
                startTime = datetime.utcnow()
            
                # Go through all the guilds
                for guild in self.bot.guilds:
                    calendarId = await self.config.guild(guild).calendarId()
                    eventsChannel = await self.config.guild(guild).calendarEventsChannel()
                    calendarEventChannel = guild.get_channel(eventsChannel)
                    if not calendarEventChannel:
                        continue
                    usersConverters = await self.config.guild(guild).usersConverter()
                    eventMessages = await self.config.guild(guild).eventMessages()
                    
                    # Get all the events for this guild and update the messages
                    page_token = None
                    while True:
                        events = service.events().list(calendarId=calendarId, showDeleted=True, updatedMin=self.prevUpdateTime.strftime('%Y-%m-%dT%H:%M:%S.%fZ'), pageToken=page_token).execute()
                        for event in events['items']:
                            eventMessage = next((eventMessage for eventMessage in eventMessages if eventMessage['eventId'] == event['id']), None)
                            if eventMessage:                   
                                try:
                                    msg = await calendarEventChannel.fetch_message(eventMessage['messageId'])
                                    
                                    # If the discord message has been updated later than the event, the update was most likely from discord and we don't need to update
                                    lastGoogleEventUpdate = datetime.strptime(event['updated'], '%Y-%m-%dT%H:%M:%S.%fZ')#.replace(tzinfo=pytz.utc)
                                    if msg.edited_at and msg.edited_at > lastGoogleEventUpdate:
                                        continue
                                    
                                    if event['status'] == 'confirmed' or event['status'] == 'tentative':
                                        # Update the message with the event
                                        await self.updateEventMessage(msg, event)
                                        await foo.Logger().logEventMessage(guild, foo.Logger.Type.Info, "Calendar", f"Updater - Updated Discord message from Event `{event['id']} ({event['htmlLink']})`")
                                    elif event['status'] == 'cancelled':
                                        # Remove event message
                                        await msg.delete()
                                        await self.removeCalendarEventMessage(guild, event['id'])
                                        await foo.Logger().logEventMessage(guild, foo.Logger.Type.Info, "Calendar", f"Updater - Removed Event `{event['id']}` and it's discord message")
                                        
                                        #TODO: Some message that the event has been cancelled
                                except discord.NotFound:
                                    print("Unable to find the message with event")
                                    await self.removeCalendarEventMessage(guild, event['id'])
                                    await foo.Logger().logEventMessage(guild, foo.Logger.Type.Warning, "Calendar", f"Updater - Was unable to find discord message with event `{event['id']}`")
                                except discord.HTTPException:
                                    print("Retrieving the message resulted with a network error.")
                                    await foo.Logger().logEventMessage(guild, foo.Logger.Type.Error, "Calendar", f"Updater -  Retrieving Discord message resulted with a network error! Event: `{event['id']}`")
                                    
                        # Get next page if there are more events
                        page_token = events.get('nextPageToken')
                        if not page_token:
                            break
                
            except asyncio.CancelledError:
                print("Cancelled Loop")
                await foo.Logger().logEventMessage(guild, foo.Logger.Type.Warning, "Calendar", f"Updater - Cancelled Update Loop from asyncio.CancelledError")
                return
            except Exception as e:
                print("An exception occured!")
                await foo.Logger().logEventMessage(guild, foo.Logger.Type.Error, "Calendar", f"Updater - An Exception occured: `{str(e)}`!! But was handled by this amazing bot (¬‿¬).")
                print(e)
            finally: 
                # Update prev update time
                self.prevUpdateTime = startTime
                
            # Sleep for some time for the next update
            await asyncio.sleep(self.updateIntervalTime)

    def get_calendar_service(self):
        creds = None

        # Check and get the autorization data
        if os.path.exists(self.tokenFilePath):
            with open(self.tokenFilePath, 'rb') as token:
                creds = pickle.load(token)
        else:
            return None

        if not creds or not creds.valid:
            # Refresh creds if possible!
            if creds and creds.expired and creds.refresh_token:
                #await ctx.send("Trying to refresh crendentials, you might have to check the bot host screen for google login!")
                creds.refresh(Request())

                with open(self.tokenFilePath, 'wb') as token:
                    pickle.dump(creds, token)
            else:
                return None

        return build('calendar', 'v3', credentials=creds)

    async def handleCredentials(self, ctx: commands.Context):
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        creds = None
        
        await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Info, "Calendar", f"`{ctx.author.name}` Called HandleCredentials")

        if os.path.exists(self.tokenFilePath):
            with open(self.tokenFilePath, 'rb') as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            # Check if we need ro refresh credentials or initialze them
            if creds and creds.expired and creds.refresh_token:
                await ctx.send("Trying to refresh crendentials, you might have to check the bot host screen for google login!")
                creds.refresh(Request())
                await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Info, "Calendar", f"Credentials were refreshed")
            else:
                # Check if credentials file is found in the execution folder
                CredentialsPath = "credentials.json"
                if not os.path.exists(CredentialsPath):
                    await ctx.send("We cannot find a default credentials file, where is it located?")
                    try:
                        # Check function if the user is equal to the person that started the command and its in the same channel
                        def check(m):
                            return m.author == ctx.author and m.channel == ctx.channel
                        
                        # Get credentials path message
                        message = await self.bot.wait_for('message', timeout=60.0, check=check)
                        CredentialsPath = message.content

                        # Check if given file path exists
                        if not os.path.exists(CredentialsPath):
                            await ctx.send("Error: No credentials.json found! This file is required to make a connection to google!")
                            return
                    except asyncio.TimeoutError:
                        await ctx.send("Timed out, canceling initcalendar")
                        return

                # Try actual google authentication with given credentials
                try:
                    await ctx.send("Check the bot server for a google calendar login screen in the browser!")
                    flow = InstalledAppFlow.from_client_secrets_file(CredentialsPath, SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    await ctx.send("Something went wrong while using credentials to authenticate with google! Check output log.")
                    print("Error: CALENDAR initcalendar - Use Google Credentials issue ====================")
                    print(e)
                    return
                
            # Save the credentials for the next run
            with open(self.tokenFilePath, 'wb') as token:
                pickle.dump(creds, token)

            await ctx.send("Authenticated and saved google calendar information!")
            await ctx.send("Saved token file in " + os.path.dirname(os.path.realpath(self.tokenFilePath)))
            await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Warning, "Calendar", f"Credentials were updated!")
        else:
            await ctx.send("Already Valid Credentials Available! Delete token.pickle in the bot to reset.")
            return
 

    @commands.group()
    @commands.guild_only()
    async def calendar(self, ctx: commands.Context):
        pass
    

    @calendar.command()
    @checks.is_owner()
    async def setTokenFilePath(self, ctx, tokenPath: str):
        self.tokenFilePath = tokenPath
        await ctx.send("Successfully updated token filepath!")


    @calendar.command()
    async def addUser(self, ctx: commands.Context, discordTag: discord.Member, fullName: str, email: str, studentID: int):
        usersConverter = await self.config.guild(ctx.guild).usersConverter()
        usersConverter.append({"userID": discordTag.id, "name": fullName, "email": email, "studentID": studentID})
        await self.config.guild(ctx.guild).usersConverter.set(usersConverter)
        await ctx.send("Added user")        
        await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Info, "Calendar", f"`{discordTag.name}` User added to the calendar")
    @calendar.command()
    async def addSelf(self, ctx: commands.Context, fullName, email, studentID):
        usersConverter = await self.config.guild(ctx.guild).usersConverter()
        usersConverter.append({"userID": ctx.author.id, "name": fullName, "email": email, "studentID": studentID})
        await self.config.guild(ctx.guild).usersConverter.set(usersConverter)
        await ctx.send("Added user")
        await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Info, "Calendar", f"`{ctx.author.name}` User added themself to the calendar")
        
    @calendar.command()
    @checks.is_owner()
    @checks.admin_or_permissions(administrator=True)
    async def getRegisteredUsers(self, ctx: commands.Context):
        totalMessage = ""
        for index, user in enumerate(await self.config.guild(ctx.guild).usersConverter()):
            totalMessage += str(index) + " : **" + user["name"] + "** | " + user["email"] + " | " + str(user["studentID"]) + " | " + str(user["userID"]) + "\n"
        await ctx.send(totalMessage)
    @calendar.command()
    @checks.is_owner()
    @checks.admin_or_permissions(administrator=True)
    async def removeUser(self, ctx: commands.Context, userIndex: int):
        usersConverter = await self.config.guild(ctx.guild).usersConverter()
        removeUser = usersConverter[userIndex]
        usersConverter.pop(userIndex)
        await self.config.guild(ctx.guild).usersConverter.set(usersConverter)
        await ctx.send("Removed User: **" + removeUser["name"] + "** | " + removeUser["email"] + " | " + str(removeUser["studentID"]) + " | " + str(removeUser["userID"]))
        await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Warning, "Calendar", "`" + str(removeUser["name"]) + "` was removed from the calendar users!")

    @calendar.command()
    @checks.is_owner()
    @checks.admin_or_permissions(administrator=True)
    async def init(self, ctx: commands.Context):
        
        await self.setCalendarCreateReactions(ctx)
        
        # Check function if the user is equal to the person that started the command and its in the same channel
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        msg = await ctx.send("Please specify the calendar event **Channel** to send the completed calendar events to after creation. Format: *#ChannelName*")
        try:
            message = await self.bot.wait_for('message', timeout=30.0, check=check)
            textChannels = [channel for channel in message.channel_mentions if type(channel) == discord.TextChannel]
            if len(textChannels) <= 0:
                await ctx.send("No valid text channel specified. Make sure it is a public text channel!")
                return
            else:
                await self.config.guild(ctx.guild).calendarEventsChannel.set(textChannels[0].id)
                await message.delete()
        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")
        finally:
            await msg.delete()
            
        await self.setCalendarOptionsReactions(ctx)
            
        # Handle crendentials
        await self.handleCredentials(ctx)
        
    async def setCalendarCreateReactions(self, ctx: commands.Context):
        # Check function if the user is equal to the person that started the command and its in the same channel
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        msg = await ctx.send("Please specify the **success (ok)** emoji by sending it!")
        try:
            message = await self.bot.wait_for('message', timeout=30.0, check=check)
            await self.config.guild(ctx.guild).successEmoji.set(message.content)
            await message.delete()
        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")
        finally:
            await msg.delete()

        msg = await ctx.send("Please specify the **cancel (error)** emoji by sending it!")
        try:
            message = await self.bot.wait_for('message', timeout=30.0, check=check)
            await self.config.guild(ctx.guild).cancelEmoji.set(message.content)
            await message.delete()
        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")
        finally:
            await msg.delete()
    async def setCalendarOptionsReactions(self, ctx: commands.Context):
        # Check function if the user is equal to the person that started the command and its in the same channel
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        msg = await ctx.send("Please specify the **Add Self to Event** emoji by sending it!")
        try:
            message = await self.bot.wait_for('message', timeout=30.0, check=check)
            AddSelfToEventEmoji = message.content
            await message.delete()
        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")
        finally:
            await msg.delete()
            
        msg = await ctx.send("Please specify the **Remove Self from Event** emoji by sending it!")
        try:
            message = await self.bot.wait_for('message', timeout=30.0, check=check)
            RemoveSelfFromEventEmoji = message.content
            await message.delete()
        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")
        finally:
            await msg.delete()
            
            
        msg = await ctx.send("Please specify the **Accept Event** emoji by sending it!")
        try:
            message = await self.bot.wait_for('message', timeout=30.0, check=check)
            AcceptEventEmoji = message.content
            await message.delete()
        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")
        finally:
            await msg.delete()
            
        msg = await ctx.send("Please specify the **To be decided later if able to attend Event** emoji by sending it!")
        try:
            message = await self.bot.wait_for('message', timeout=30.0, check=check)
            MaybeAcceptEventEmoji = message.content
            await message.delete()
        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")
        finally:
            await msg.delete()

        msg = await ctx.send("Please specify the **Deny Event** emoji by sending it!")
        try:
            message = await self.bot.wait_for('message', timeout=30.0, check=check)
            DenyEventEmoji = message.content
            await message.delete()
        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")
        finally:
            await msg.delete()
            
        await self.config.guild(ctx.guild).eventMessageFunctionEmojis.set({
            "AddSelf": AddSelfToEventEmoji,
            "RemoveSelf": RemoveSelfFromEventEmoji,
            "AcceptEvent": AcceptEventEmoji,
            "MaybeEvent": MaybeAcceptEventEmoji,
            "DenyEvent": DenyEventEmoji
        })
    
    @calendar.command(aliases=['specifyCalendar'])
    @checks.is_owner()
    @checks.admin_or_permissions(administrator=True)
    async def selectCalendar(self, ctx: commands.Context):
        service = self.get_calendar_service()
        if not service:
            await ctx.send("Invalid Calendar Credentials! Contact bot owner to add these.")
            return
        
        await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Info, "Calendar", f"Calendar change was started by `{ctx.author.name}`")
        
        try:
            # Get all the possible google calendars
            calendarsListResponse = service.calendarList().list().execute()
            
            message = ""
            for index, calendar_list_entry in enumerate(calendarsListResponse['items']):
                message += str(index) + " : **" + calendar_list_entry['summary'] + "** | " + calendar_list_entry['id'] + "\n"
            await ctx.send(message)
            
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel
    
            # Get the selected index
            message = await self.bot.wait_for('message', timeout=30.0, check=check)
            try:
                selectedCalendar = int(message.content)
            except ValueError:
                await ctx.send("Error! That can not be converted into a number!")
                return
        
            await self.config.guild(ctx.guild).calendarId.set(calendarsListResponse['items'][selectedCalendar]['id'])
            
            await ctx.send("Successfully set the Calendar to *" + calendarsListResponse['items'][selectedCalendar]['summary'] + "*")
            await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Info, "Calendar", f"Changed calendar to `{calendarsListResponse['items'][selectedCalendar]['summary']}`")
            
        except HttpError as e:
            await ctx.send("Error while retrieving the calendars. Code: " + str(e.resp.status) + " Message: " + e._get_reason())
            await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Error, "Calendar", f"An exception occured while setting the calendar `{str(e)}`")
            return

    @calendar.command()
    @checks.is_owner()
    @checks.admin_or_permissions(administrator=True)
    async def credentials(self, ctx: commands.Context):
        await self.handleCredentials(ctx)

    @calendar.command(aliases=['createevent', 'new', 'newevent'])
    async def create(self, ctx: commands.Context):
        service = self.get_calendar_service()
        if not service:
            await ctx.send("Invalid Calendar Credentials! Contact bot owner to add these.")
            return

        # Create the calendar event    
        calendarEventHandler = CreateCalendarEvent(ctx, self.bot, self.config)

        # Create editable event data message ======================================
        embed = discord.Embed(type="rich", colour=100)
        embed.set_footer(text="Event name")
        embed.set_author(name="Calendar Event", icon_url=ctx.message.author.avatar_url)

        calendarDataMsg = await ctx.send(embed=embed)

        eventCreationStageMsg = await ctx.send("What are we calling this event?")
        calendarEventHandler.stageMessage = eventCreationStageMsg

        # Event Name ===============================
        await calendarEventHandler.HandleNameMessage()
        if not await calendarEventHandler.HandleName(): 
            await calendarDataMsg.delete(delay=1)
            await calendarEventHandler.stageMessage.delete()
            return
        await calendarEventHandler.HandleTimeMessage()

        await asyncio.sleep(.15)

        embed.title = calendarEventHandler.name
        embed.set_footer(text="Event start datetime")
        await calendarDataMsg.edit(embed=embed)

        # Event Start Time ==========================
        if not await calendarEventHandler.HandleTime(): 
            await calendarDataMsg.delete(delay=1)
            await calendarEventHandler.stageMessage.delete()
            return
        await calendarEventHandler.HandleDurationMessage()

        await asyncio.sleep(.15)

        formattedDatetime = calendarEventHandler.time.strftime("%A, %d. %B %Y %I:%M%p")
        embed.add_field(name="Start Time", value=formattedDatetime, inline=False)
        embed.set_footer(text="Event duration")
        await calendarDataMsg.edit(embed=embed)

        # Event Duration ===========================
        if not await calendarEventHandler.HandleDuration(): 
            await calendarDataMsg.delete(delay=1)
            await calendarEventHandler.stageMessage.delete()
            return
        await calendarEventHandler.HandleDescriptionMessage()

        await asyncio.sleep(.15)

        embed.add_field(name="Duration", value=calendarEventHandler.duration.strftime("%H:%M") + " Hours", inline=False)
        embed.set_footer(text="Event description")
        await calendarDataMsg.edit(embed=embed)

        # Event Description ========================
        if not await calendarEventHandler.HandleDescription(): 
            await calendarDataMsg.delete(delay=1)
            await calendarEventHandler.stageMessage.delete()
            return
        await calendarEventHandler.HandleAttendeesMessage()

        await asyncio.sleep(.15)

        embed.description = calendarEventHandler.description
        embed.set_footer(text="Event attendees")
        await calendarDataMsg.edit(embed=embed)

        # Event Attendees ==========================
        if not await calendarEventHandler.HandleAttendees(): 
            await calendarDataMsg.delete(delay=1)
            await calendarEventHandler.stageMessage.delete()
            return        
        await calendarEventHandler.FinishEventMessage()
        
        await asyncio.sleep(.15)            
        
        userTags = list(["<@" + str(user['userID']) + ">" for user in calendarEventHandler.attendees])
        
        firstUsersField = '\n'.join(userTags[0:max([self.maxAttendeesInRowToSplit, math.ceil(len(userTags) / 2)])])
        if len(calendarEventHandler.externalAttendees) > 0:
            firstUsersField += '\n\n**External Attendees**\n' + '\n'.join([user for user in calendarEventHandler.externalAttendees])
        embed.add_field(name="Attendees", value=firstUsersField, inline=True)
        
        if len(userTags) > self.maxAttendeesInRowToSplit:
            embed.add_field(name="\n\u200b", value='\n'.join(userTags[max([self.maxAttendeesInRowToSplit, math.ceil(len(userTags) / 2)]):]), inline=True)
            
        embed.set_footer(text="Finishing up event")
        await calendarDataMsg.edit(embed=embed)

        # Finish Event Creation ====================
        if not await calendarEventHandler.FinishEvent(): 
            await calendarDataMsg.delete(delay=5)
            await calendarEventHandler.stageMessage.delete()
            await ctx.send("Cancelled Event Creation!")
            return
        

        embed.set_footer(text="")
        await calendarDataMsg.edit(embed=embed)
        await calendarEventHandler.stageMessage.edit(content="Creating Event...")

        # API Calls ===============================================================
        async with ctx.channel.typing():         
            
            durationTimeObject = calendarEventHandler.duration.time()
            endDateTime = calendarEventHandler.time + timedelta(hours=durationTimeObject.hour, minutes=durationTimeObject.minute)
            
            registeredCalendarUsers = [{'email': user['email']} for user in calendarEventHandler.attendees]
            externalCalendarusers = [{'email': user} for user in calendarEventHandler.externalAttendees]
            
            # Get event create user name and email
            registeredUsers = await self.config.guild(ctx.guild).usersConverter()
            user = next((user for user in registeredUsers if user['userID'] == ctx.message.author.id), None)
            userName = ""
            userEmail = ""
            if not user:
                userName = ctx.message.author.nick
                if userName is None:
                    userName = ctx.message.author.name
            else:
                userName = user['name']
                userEmail = user['email']

            try:
                calendarId = await self.config.guild(ctx.guild).calendarId()
                if not calendarId:
                    return
                
                # Create The Google Calendar Event
                event = service.events().insert(calendarId=calendarId, body={
                    'summary': calendarEventHandler.name,
                    'description': 'Creator: ' + userName + " (" + userEmail + ")" + "\n\n" + calendarEventHandler.description + "\n\n##Generated Event from Discord Bot",
                    'start': {
                        'dateTime': calendarEventHandler.time.isoformat(),
                        'timeZone': 'Europe/Amsterdam',
                    },
                    'end': {
                        'dateTime': endDateTime.isoformat(),
                        'timeZone': 'Europe/Amsterdam',
                    },
                    'attendees': registeredCalendarUsers + externalCalendarusers,
                    'anyoneCanAddSelf': True,
                    'guestsCanModify': True
                }, sendUpdates='all').execute()

            except HttpError as e:
                await ctx.send("Error while creating the event. Code: " + str(e.resp.status) + " Message: " + e._get_reason())
                await calendarDataMsg.delete(delay=5)
                await calendarEventHandler.stageMessage.delete()
                await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Error, "Calendar", f"Error while creating calendar event. Code: `" + str(e.resp.status) + "` Message: `" + e._get_reason() + "`")
                return
            
        # API Call Success!
        await calendarEventHandler.stageMessage.edit(content="Successfully Created Your Event!")
        await calendarEventHandler.stageMessage.delete(delay=6)

        # Get link to send and add it to complete message
        eventLink = event.get('htmlLink')

        embed.set_author(name='Created Calendar Event', icon_url=ctx.message.author.avatar_url, url=eventLink)
        embed.add_field(name="Event ID", value=event.get('id'), inline=False)
        embed.add_field(name="Event Link", value=f"[Google Calendar Event Link]({eventLink} 'Link to the generated Google Calendar Event')", inline=False)
        await calendarDataMsg.edit(embed=embed)
        
        calendarEventChannelId = await self.config.guild(ctx.guild).calendarEventsChannel()
        calendarEventChannel = ctx.guild.get_channel(calendarEventChannelId)
        if not calendarEventChannel:
            calendarEventChannel = ctx.channel
            
        attendeesInEvent = event.get('attendees', list())
        attendeesInEventEmails = [event['email'] for event in attendeesInEvent]
        
        noResponseUsers = ["<@" + str(user['userID']) + ">" for user in registeredUsers if user['email'] in attendeesInEventEmails and next((attendee.get('responseStatus', 'needsAction') for attendee in attendeesInEvent if attendee['email'] == user['email']), 'needsAction') == 'needsAction']
        noResponseUsersText = "**" + str(len(noResponseUsers)) + " Left** - " + ' '.join(noResponseUsers)
        
        # Send message in calendar channel
        message = await calendarEventChannel.send(content=noResponseUsersText, embed=embed)
        # Add message to event converter
        eventMessagesConverter = await self.config.guild(ctx.guild).eventMessages()
        eventMessagesConverter.append({"eventId": event.get('id'), "messageId": message.id})
        await self.config.guild(ctx.guild).eventMessages.set(eventMessagesConverter)
        
        embed=discord.Embed(title="Your event and message have been created!!", description=f"[Click Here to go straight to your generated discord message]({message.jump_url} 'This link will take you straight to the generated discord event message :)') :ok_hand:", color=0x00b700)
        if random.randrange(10) == 0:
            embed.set_author(name="Woohoo,", url="https://www.youtube.com/watch?v=cBVeNQ-mtcY")
        await ctx.send(embed=embed)
        
        # Add possible message emotes 
        messageReactions = await self.config.guild(ctx.guild).eventMessageFunctionEmojis()
        if messageReactions:
            for reaction in messageReactions:
                await message.add_reaction(messageReactions[reaction])
                
        await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Info, "Calendar", f"`{ctx.author.name}` Created a new calendar event `{message.jump_url}`")
        
        await calendarDataMsg.delete(delay=60)
            
        #TODO: Feature: QOL: Send personal messages to people that have been invited? Only during project hours

    @calendar.command(aliases=['cancel', 'removeevent', 'delete', 'deleteevent'])
    async def remove(self, ctx: commands.Context, eventID: str, notify: str = "no"):
        service = self.get_calendar_service()
        if not service:
            await ctx.send("Invalid Calendar Credentials! Contact bot owner to add these.")
            return
        
        sendUpdates = 'none'
        if(notify == 'yes'):
            sendUpdates = 'all'
        elif(notify == 'external'):
            sendUpdates = 'externalOnly'
        
        # API Calls ===============================================================
        async with ctx.channel.typing():         
            # Remove The Google Calendar Event
            try:
                calendarId = await self.config.guild(ctx.guild).calendarId()
                if not calendarId:
                    return
                
                service.events().delete(calendarId=calendarId, eventId=eventID, sendUpdates=sendUpdates).execute()
                await asyncio.sleep(.3)
                await ctx.send("Removed calendar event!")
                
                if not await self.removeCalendarEventMessage(ctx.guild, eventID):
                    await ctx.send("We were unable to remove the discord message with this event. The event is still removed though :). You can remove the discord message manually if you want.")
                    await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Warning, "Calendar", f"`{ctx.author.name}` cancelled event `{eventID}`, but the discord message was not found.")
                else:
                    await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Info, "Calendar", f"`{ctx.author.name}` cancelled event `{eventID}` and removed discord message.")
                
            except HttpError as e:
                await asyncio.sleep(.3)
                await ctx.send("Error while removing the event. Code: " + str(e.resp.status) + " Message: " + e._get_reason())
                await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Error, "Calendar", f"Trying to cancel event `{eventID}` with error: `{str(e)}`")
                
    
    async def removeCalendarEventMessage(self, guild, calendarEventId) -> bool:
        eventMessagesConverter = await self.config.guild(guild).eventMessages()

        eventMessageId = next((eventMessage['messageId'] for eventMessage in eventMessagesConverter if eventMessage['eventId'] == calendarEventId), None)
        if not eventMessageId:
            return False
        
        calendarEventChannelId = await self.config.guild(guild).calendarEventsChannel()
        calendarEventChannel = guild.get_channel(calendarEventChannelId)
        if not calendarEventChannel:
            return False
        
        try:
            msg = await calendarEventChannel.fetch_message(eventMessageId)
            await msg.delete()
        except:
            return False
        finally:
            # Remove this event message converter from the list as it was not found
            listWithoutThisEventMessage = [eventMsg for eventMsg in eventMessagesConverter if eventMsg['eventId'] != calendarEventId]
            await self.config.guild(guild).eventMessages.set(listWithoutThisEventMessage)
        
        return True
                
    async def setUserResponseStatus(self, service, guild, event, userEmail, status):
        for attendee in event['attendees']:
            if attendee['email'] == userEmail:
                attendee['responseStatus'] = status
                
                calendarId = await self.config.guild(guild).calendarId()
                if not calendarId:
                    return False
                
                #update the google event
                return service.events().update(calendarId=calendarId, eventId=event.get('id'), body=event).execute()
            
    async def hasClientReactedWithEmote(self, reaction, user, emote) -> bool:
        if str(reaction) == emote:
            if user in await reaction.users().flatten():
                return True
            return False
            
    async def removeClientReactionOnMessage(self, message, user, emote, preventOnReactionRemoveEvent = True):
        for reaction in message.reactions:
            if str(reaction) == emote and await self.hasClientReactedWithEmote(reaction, user, emote):                
                if preventOnReactionRemoveEvent:
                    index = len(self.ignoreEmojiEvents)
                    self.ignoreEmojiEvents.append({"emoji": emote, "message": message.id, "userid": user.id, "exp": time.mktime(datetime.now().timetuple()) + 30})
                
                try:
                    await reaction.remove(user)
                except:
                    print('Unable to remove reaction')
                    if preventOnReactionRemoveEvent:
                        self.ignoreEmojiEvents.pop(index)
                return
            
    def hasRunningRequest(self, message, user):
        currentRunningEvents = [runningEvent for runningEvent in self.runningEventRequests if runningEvent['messageId'] == message.id and runningEvent['userId'] == user.id]
        if len(currentRunningEvents) <= 0:
            return None
        for event in currentRunningEvents:
            if time.mktime(datetime.now().timetuple()) < event["exp"]:
                return event['emoji']
        return None 
    def addRunningEvent(self, reaction, user):
        self.runningEventRequests.append({'messageId': reaction.message.id, 'userId': user.id, 'emoji': str(reaction), "exp": time.mktime(datetime.now().timetuple()) + 30})
    def removeRunningEvent(self, reaction, user):
        self.runningEventRequests = [runningEvent for runningEvent in self.runningEventRequests if runningEvent['messageId'] != reaction.message.id and runningEvent['userId'] != user.id]

    async def updateEventMessage(self, message, updated_event):
        attendeesInEvent = updated_event.get('attendees', list())
        updated_event_attendees_email = [event['email'] for event in attendeesInEvent]
        
        registeredUsers = await self.config.guild(message.guild).usersConverter()
        registeredUserEmails = [user['email'] for user in registeredUsers]
        
        eventMessageEmojis = await self.config.guild(message.guild).eventMessageFunctionEmojis()
        def getEmojiFromStatus(status):
            if not status:
                return ""
            if status == 'accepted':
                return eventMessageEmojis['AcceptEvent'] + " "
            if status == 'tentative':
                return eventMessageEmojis['MaybeEvent'] + " "
            if status == 'declined':
                return eventMessageEmojis['DenyEvent'] + " "
            return ""
        
        eventMessage = message.embeds[0]
        
        
        eventMessage.title = updated_event['summary']
        
        descriptionValues = re.findall(r'.*\)(?:\n|<br>)(?:\n|<br>)(.*)(?:\n|<br>)(?:\n|<br>)##Generated Event from Discord Bot', updated_event['description'])
        eventMessage.description = descriptionValues[0] if len(descriptionValues) >= 1 else ' '
        eventMessage.description = eventMessage.description.replace('<br>', '\n')
        eventMessage.description = eventMessage.description.strip()
        
        if self.colors and 'colorId' in updated_event:
            color = self.colors['event'][updated_event['colorId']]
            color = color.lstrip('#')
            rgbColor = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
            eventMessage.colour = discord.Colour().from_rgb(rgbColor[0], rgbColor[1], rgbColor[2])
            
        # =============
        
        eventMessage.clear_fields()            
        
        # =============
        
        eventStartDatetime = datetime.strptime(updated_event['start']['dateTime'], '%Y-%m-%dT%H:%M:%S%z')
        eventMessage.add_field(name="Start Time", value=eventStartDatetime.strftime("%A, %d. %B %Y %I:%M%p"), inline=False)
        
        # =============
        
        eventStartDatetime = datetime.strptime(updated_event['start']['dateTime'], '%Y-%m-%dT%H:%M:%S%z')
        eventEndDatetime = datetime.strptime(updated_event['end']['dateTime'], '%Y-%m-%dT%H:%M:%S%z')

        # Get the difference and convert timedelta back into datetime
        eventDuration = eventEndDatetime - eventStartDatetime
        eventDurationDatetime = datetime.utcfromtimestamp(eventDuration.total_seconds())
        eventMessage.add_field(name="Duration", value=eventDurationDatetime.strftime("%H:%M") + " Hours", inline=False)
        
        # =============
        
        userTags = list([getEmojiFromStatus(next((attendee.get('responseStatus', None) for attendee in attendeesInEvent if attendee['email'] == user['email']), None)) + "<@" + str(user['userID']) + "> " for user in registeredUsers if user['email'] in updated_event_attendees_email])

        firstUsersField = '\n'.join(userTags[0:max([self.maxAttendeesInRowToSplit, math.ceil(len(userTags) / 2)])])
        
        externalUsers = [user for user in updated_event_attendees_email if user not in registeredUserEmails]
        if len(externalUsers) > 0:
            firstUsersField += '\n\n**External Attendees:**\n' + '\n'.join([user for user in externalUsers])
        eventMessage.add_field(name="Attendees", value=firstUsersField, inline=True)
        
        if len(userTags) > self.maxAttendeesInRowToSplit:
            eventMessage.add_field(name="\n\u200b", value='\n'.join(userTags[max([self.maxAttendeesInRowToSplit, math.ceil(len(userTags) / 2)]):]), inline=True)
              
        # =============
            
        eventMessage.add_field(name="Event ID", value=updated_event.get('id'), inline=False)
        eventMessage.add_field(name="Event Link", value=f"[Google Calendar Event Link]({updated_event.get('htmlLink')} 'Link to the generated Google Calendar Event')", inline=False)
        
        # =============
        
        noResponseUsers = ["<@" + str(user['userID']) + ">" for user in registeredUsers if user['email'] in updated_event_attendees_email and next((attendee.get('responseStatus', 'needsAction') for attendee in attendeesInEvent if attendee['email'] == user['email']), 'needsAction') == 'needsAction']
        noResponseUsersText = '\n\u200b'
        if len(noResponseUsers) > 0:
            noResponseUsersText = "**" + str(len(noResponseUsers)) + " Left** - " + ' '.join(noResponseUsers)
            
        await message.edit(content=noResponseUsersText, embed=eventMessage)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if self.hasRunningRequest(reaction.message, user):
            await self.removeClientReactionOnMessage(reaction.message, user, reaction)
            return
        
        eventMessagesConverter = await self.config.guild(reaction.message.guild).eventMessages()
        eventIdFromMessage = next((event['eventId'] for event in eventMessagesConverter if event['messageId'] == reaction.message.id), None)
        if not eventIdFromMessage:
            return
        
        registeredUsers = await self.config.guild(reaction.message.guild).usersConverter()        
        userEmail = next((users['email'] for users in registeredUsers if users['userID'] == user.id), None)
        if not userEmail:
            # Unknown or unregistered
            return
        
        service = self.get_calendar_service()
        if not service:
            await reaction.message.channel.send("Invalid Calendar Credentials! Contact bot owner to add these.")
            return
        
        calendarId = await self.config.guild(reaction.message.guild).calendarId()
        if not calendarId:
            return
                
        event = service.events().get(calendarId=calendarId, eventId=eventIdFromMessage).execute()
        def IsAttendee(email):
            if 'attendees' in event:
                for attendee in event['attendees']:
                    if attendee['email'] == email:
                        return True
            return False
        userIsAttendeeOfEvent = IsAttendee(userEmail)
        
        messageReactions = await self.config.guild(reaction.message.guild).eventMessageFunctionEmojis()
        
        if str(reaction) == messageReactions['AddSelf']:
            if not userIsAttendeeOfEvent:
                self.addRunningEvent(reaction, user)
                
                # Remove emotes to make it feel snappy
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['RemoveSelf'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                # Make update
                event['attendees'] = event.get('attendees', list())
                event['attendees'].append({'email': userEmail})
                
                calendarId = await self.config.guild(reaction.message.guild).calendarId()
                if not calendarId:
                    return
                
                updated_event = service.events().update(calendarId=calendarId, eventId=eventIdFromMessage, body=event).execute()

                # Make sure the emotes are removed after update to ensure correct state
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['RemoveSelf'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                print("Added user to event")
                
                self.removeRunningEvent(reaction, user)
                
                await self.updateEventMessage(reaction.message, updated_event)
            else:
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AddSelf'])
            return
        if str(reaction) == messageReactions['RemoveSelf']:
            if userIsAttendeeOfEvent:
                self.addRunningEvent(reaction, user)
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AddSelf'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                event['attendees'].pop([attendee['email'] for attendee in event['attendees']].index(userEmail))
                
                calendarId = await self.config.guild(reaction.message.guild).calendarId()
                if not calendarId:
                    return
                
                updated_event = service.events().update(calendarId=calendarId, eventId=eventIdFromMessage, body=event).execute()
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AddSelf'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                print("Removed user from event")
                
                self.removeRunningEvent(reaction, user)
                
                await self.updateEventMessage(reaction.message, updated_event)
            else:
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['RemoveSelf'])
            return
        
        
        if str(reaction) == messageReactions['AcceptEvent']:
            if userIsAttendeeOfEvent:
                self.addRunningEvent(reaction, user)
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                updated_event = await self.setUserResponseStatus(service, reaction.message.guild, event, userEmail, 'accepted')
                print("Set State 'Accepted'")
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                self.removeRunningEvent(reaction, user)
                #Accept User to the event
                await self.updateEventMessage(reaction.message, updated_event)
            else:
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
            return
        if str(reaction) == messageReactions['MaybeEvent']:
            if userIsAttendeeOfEvent:
                self.addRunningEvent(reaction, user)
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                updated_event = await self.setUserResponseStatus(service, reaction.message.guild, event, userEmail, 'tentative')
                print("Set State 'Tentative'")
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                self.removeRunningEvent(reaction, user)
                #Maybe Accept User to the event
                await self.updateEventMessage(reaction.message, updated_event)
            else:
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
            return
        if str(reaction) == messageReactions['DenyEvent']:
            if userIsAttendeeOfEvent:
                self.addRunningEvent(reaction, user)
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                
                updated_event = await self.setUserResponseStatus(service, reaction.message.guild, event, userEmail, 'declined')
                print("Set State 'Declined'")
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                
                self.removeRunningEvent(reaction, user)
                #Deny the event request
                await self.updateEventMessage(reaction.message, updated_event)
            else:
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
            return
        
    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        ignoreEmoteEvent = next((ignoreEvent for ignoreEvent in self.ignoreEmojiEvents if ignoreEvent["emoji"] == str(reaction) and ignoreEvent["message"] == reaction.message.id and ignoreEvent["userid"] == user.id), None)
        if ignoreEmoteEvent:
            if time.mktime(datetime.now().timetuple()) < ignoreEmoteEvent["exp"]:
                self.ignoreEmojiEvents.remove(ignoreEmoteEvent)
                return
            self.ignoreEmojiEvents.remove(ignoreEmoteEvent)
        
        eventMessagesConverter = await self.config.guild(reaction.message.guild).eventMessages()
        eventIdFromMessage = next((event['eventId'] for event in eventMessagesConverter if event['messageId'] == reaction.message.id), None)
        if not eventIdFromMessage:
            return
        
        registeredUsers = await self.config.guild(reaction.message.guild).usersConverter()        
        userEmail = next((users['email'] for users in registeredUsers if users['userID'] == user.id), None)
        if not userEmail:
            # Unknown or unregistered user
            return
        
        service = self.get_calendar_service()
        if not service:
            await reaction.message.channel.send("Invalid Calendar Credentials! Contact bot owner to add these.")
            return
        
        calendarId = await self.config.guild(reaction.message.guild).calendarId()
        if not calendarId:
            return
        
        event = service.events().get(calendarId=calendarId, eventId=eventIdFromMessage).execute()
        def IsAttendee(email):
            if 'attendees' in event:
                for attendee in event['attendees']:
                    if attendee['email'] == email:
                        return True
            return False
        
        userIsAttendeeOfEvent = IsAttendee(userEmail)
        
        messageReactions = await self.config.guild(reaction.message.guild).eventMessageFunctionEmojis()
        
        if str(reaction) == messageReactions['AddSelf']:
            if userIsAttendeeOfEvent:
                self.addRunningEvent(reaction, user)
                
                # Remove emotes to make it feel snappy
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                calendarId = await self.config.guild(reaction.message.guild).calendarId()
                if not calendarId:
                    return
                
                # Make update
                event['attendees'].pop([attendee['email'] for attendee in event['attendees']].index(userEmail))
                updated_event = service.events().update(calendarId=calendarId, eventId=eventIdFromMessage, body=event).execute()
                
                # Make sure the emotes are removed after update to ensure correct state
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                self.removeRunningEvent(reaction, user)
                
                await self.updateEventMessage(reaction.message, updated_event)
                
                print("Removed user again from event")
            return
        if str(reaction) == messageReactions['RemoveSelf']:
            if not userIsAttendeeOfEvent:
                self.addRunningEvent(reaction, user)
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                calendarId = await self.config.guild(reaction.message.guild).calendarId()
                if not calendarId:
                    return
                
                event['attendees'] = event.get('attendees', list())
                event['attendees'].append({'email': userEmail})
                updated_event = service.events().update(calendarId=calendarId, eventId=eventIdFromMessage, body=event).execute()
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                self.removeRunningEvent(reaction, user)
                
                await self.updateEventMessage(reaction.message, updated_event)
                
                print("Added user back to event")
            return
        
        
        if str(reaction) == messageReactions['AcceptEvent']:
            if userIsAttendeeOfEvent:
                currentRequests = self.hasRunningRequest(reaction.message, user)
                if currentRequests:
                    if currentRequests is str(reaction):
                        await asyncio.sleep(.5)
                    else:
                        return
                
                self.addRunningEvent(reaction, user)
                
                updated_event = await self.setUserResponseStatus(service, reaction.message.guild, event, userEmail, 'needsAction')
                print("Set State 'Needs Action'")
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                self.removeRunningEvent(reaction, user)
                
                await self.updateEventMessage(reaction.message, updated_event)
                #Accept User to the event
            return
        if str(reaction) == messageReactions['MaybeEvent']:
            if userIsAttendeeOfEvent:
                currentRequests = self.hasRunningRequest(reaction.message, user)
                if currentRequests:
                    if currentRequests is str(reaction):
                        await asyncio.sleep(.5)
                    else:
                        return
                    
                self.addRunningEvent(reaction, user)
                
                updated_event = await self.setUserResponseStatus(service, reaction.message.guild, event, userEmail, 'needsAction')
                print("Set State 'Needs Action'")
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                self.removeRunningEvent(reaction, user)
                
                await self.updateEventMessage(reaction.message, updated_event)
                #Maybe Accept User to the event
            return
        if str(reaction) == messageReactions['DenyEvent']:
            if userIsAttendeeOfEvent:
                currentRequests = self.hasRunningRequest(reaction.message, user)
                if currentRequests:
                    if currentRequests is str(reaction):
                        await asyncio.sleep(.5)
                    else:
                        return
                
                self.addRunningEvent(reaction, user)
                
                updated_event = await self.setUserResponseStatus(service, reaction.message.guild, event, userEmail, 'needsAction')
                print("Set State 'Needs Action'")
                
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['AcceptEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['MaybeEvent'])
                await self.removeClientReactionOnMessage(reaction.message, user, messageReactions['DenyEvent'])
                
                self.removeRunningEvent(reaction, user)
                
                await self.updateEventMessage(reaction.message, updated_event)
                #Deny the event request
            return