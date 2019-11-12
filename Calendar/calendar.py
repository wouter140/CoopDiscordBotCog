from redbot.core import commands, checks

import os
import asyncio
from datetime import timedelta, datetime
import pickle

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import discord

from .createevent import CreateCalendarEvent

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar']

class Calendar(commands.Cog):
    """Calendar Cog for the Discord Bot.
       Implements Google Calendar Functionality with the bot."""

    def __init__(self, bot):
        self.bot = bot

    def get_calendar_service(self):
        creds = None

        # Check and get the autorization data
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        else:
            return None

        if not creds or not creds.valid:
            # Refresh creds if possible!
            if creds and creds.expired and creds.refresh_token:
                #await ctx.send("Trying to refresh crendentials, you might have to check the bot host screen for google login!")
                creds.refresh(Request())

                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
            else:
                return None

        return build('calendar', 'v3', credentials=creds)


    @commands.group()
    async def calendar(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid steam command passed...')

    @calendar.command()
    @checks.is_owner()
    async def init(self, ctx: commands.Context):
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        creds = None

        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            # Check if we need ro refresh credentials or initialze them
            if creds and creds.expired and creds.refresh_token:
                await ctx.send("Trying to refresh crendentials, you might have to check the bot host screen for google login!")
                creds.refresh(Request())
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
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

            await ctx.send("Authenticated and saved google calendar information!")
            await ctx.send("Saved token file in " + os.path.dirname(os.path.realpath('token.pickle')))
        else:
            await ctx.send("Already Valid Credentials Available! Delete token.pickle in the bot to reset.")
            return
 
    @calendar.command()
    async def test(self, ctx):
        reaction = await self.bot.wait_for('reaction_add', timeout=40.0)
        await ctx.send(reaction)

    @calendar.command(aliases=['createevent', 'new', 'newevent'])
    async def create(self, ctx: commands.Context):
        service = self.get_calendar_service()
        if not service:
            await ctx.send("Invalid Calendar Credentials! Contact bot owner to add these.")
            return

        # Create the calendar event    
        calendarEventHandler = CreateCalendarEvent(ctx, self.bot)

        # Get event create user name 
        creatorName = ctx.message.author.nick
        if creatorName is None:
            creatorName = ctx.message.author.name

        # Create editable event data message
        embed = discord.Embed(type="rich", colour=100)
        embed.set_footer(text="Event name")
        embed.set_author(name="Calendar Event", icon_url=ctx.message.author.avatar_url)

        calendarDataMsg = await ctx.send(embed=embed)

        eventCreationStageMsg = await ctx.send("What are we calling this event?")
        calendarEventHandler.stageMessage = eventCreationStageMsg

        # Event Name ===============================
        await calendarEventHandler.HandleNameMessage()
        if not await calendarEventHandler.HandleName(): 
            return
        await calendarEventHandler.HandleTimeMessage()

        await asyncio.sleep(.3)

        embed.title = calendarEventHandler.name
        embed.set_footer(text="Event start datetime")
        await calendarDataMsg.edit(embed=embed)

        # Event Start Time
        if not await calendarEventHandler.HandleTime(): 
            return
        await calendarEventHandler.HandleDurationMessage()

        await asyncio.sleep(.3)

        formattedDatetime = datetime.strptime(calendarEventHandler.time, "%d-%m-%Y %H:%M").strftime("%A, %d. %B %Y %I:%M%p")
        embed.add_field(name="Start Time", value=formattedDatetime, inline=False)
        embed.set_footer(text="Event duration")
        await calendarDataMsg.edit(embed=embed)

        # Event Duration ===========================
        if not await calendarEventHandler.HandleDuration(): 
            return
        await calendarEventHandler.HandleDescriptionMessage()

        await asyncio.sleep(.3)

        embed.add_field(name="Duration", value=calendarEventHandler.duration + " Hours", inline=False)
        embed.set_footer(text="Event description")
        await calendarDataMsg.edit(embed=embed)

        # Event Description
        if not await calendarEventHandler.HandleDescription(): 
            return
        await calendarEventHandler.HandleAttendeesMessage()

        await asyncio.sleep(.3)

        embed.description += calendarEventHandler.description
        embed.set_footer(text="Event attendees")
        await calendarDataMsg.edit(embed=embed)

        # Event Attendees ==========================
        if not await calendarEventHandler.HandleAttendees(): 
            return        
        await calendarEventHandler.FinishEventMessage()

        await asyncio.sleep(.3)

        embed.add_field(name="Attendees", value=calendarEventHandler.attendees, inline=False)
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

        # API Calls ================================
        async with ctx.channel.typing():
            startDateTime = datetime.strptime(calendarEventHandler.time, "%d-%m-%Y %H:%M")

            durationTimeObject = datetime.strptime(calendarEventHandler.duration, "%H:%M").time()
            endDateTime = startDateTime + timedelta(hours=durationTimeObject.hour, minutes=durationTimeObject.minute)

            # Create The Google Calendar Event
            event = service.events().insert(calendarId='primary', body={
                'summary': calendarEventHandler.name,
                'description': calendarEventHandler.description,
                'start': {
                    'dateTime': startDateTime.isoformat(),
                    'timeZone': 'Europe/Amsterdam',
                },
                'end': {
                    'dateTime': endDateTime.isoformat(),
                    'timeZone': 'Europe/Amsterdam',
                },
                'attendees': calendarEventHandler.attendees
                    #[ {'email': 'lpage@example.com'} ]
            }).execute()

            print(event)

            await calendarEventHandler.stageMessage.edit(content="Successfully Created Your Event!")
            await calendarEventHandler.stageMessage.delete(delay=2)

            # Get link to send and add it to complete message
            eventLink = event.get('htmlLink')
            linkMsg = await ctx.send(f"You can find the event over at {eventLink}", delete_after=5)
            await linkMsg.edit(suppress=True)

            embed.set_author(name='Created Calendar Event (link)', icon_url=ctx.message.author.avatar_url, url=eventLink)
            embed.url=eventLink
            await calendarDataMsg.edit(embed=embed)

            '''
            {
                'kind': 'calendar#event', 
                'etag': '"3147191931698000"', 
                'id': 'jmr762ma2ja3bphruop04kta3o', 
                'status': 'confirmed', 
                'htmlLink': 'https://www.google.com/calendar/event?eid=am1yNzYybWEyamEzYnBocnVvcDA0a3RhM28gd291dGVyLmdydXR0ZXJAbQ', 
                'created': '2019-11-12T21:59:25.000Z', 
                'updated': '2019-11-12T21:59:25.849Z', 
                'summary': 'test', 
                'description': 'descripion', 
                'creator': {
                    'email': 'wouter.grutter@gmail.com', 
                    'self': True
                }, 
                'organizer': {
                    'email': 'wouter.grutter@gmail.com', 
                    'self': True
                }, 
                'start': {
                    'dateTime': '2019-11-13T12:00:00+01:00', 
                    'timeZone': 'Europe/Amsterdam'
                }, 
                'end': {
                    'dateTime': '2019-11-13T13:00:00+01:00', 
                    'timeZone': 'Europe/Amsterdam'
                }, 
                'iCalUID': 'jmr762ma2ja3bphruop04kta3o@google.com', 
                'sequence': 0, 
                'reminders': {
                    'useDefault': True
                }
            }
            '''


        


        
