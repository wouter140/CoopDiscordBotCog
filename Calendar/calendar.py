from redbot.core import commands

import os
import asyncio
import datetime
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
            return None

        return build('calendar', 'v3', credentials=creds)

    @commands.command()
    async def calendar(self, ctx):
        """This does stuff!"""
        # Your code will go here
        await ctx.send("I can do stuff!")
        await ctx.send("Hey!")

    @commands.command()
    async def initcalendar(self, ctx):
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
 
    @commands.command()
    async def createevent(self, ctx):
        service = self.get_calendar_service()
        if not service:
            await ctx.send("Invalid Calendar Credentials!")
            return

        #Create the calendar event    
        calendarEventHandler = CreateCalendarEvent(ctx)

        await calendarEventHandler.HandleName() #Event Name
        await calendarEventHandler.HandleDescription() #Event Description
        await calendarEventHandler.HandleTime() #Event Start Time
        await calendarEventHandler.HandleDuration() #Event Duration
        await calendarEventHandler.HandleAttendees() #Event Attendees

        if not await calendarEventHandler.FinishEvent(): #Finish Event Creation
            await ctx.send("Cancelled Event Creation!")
            return
        
        #Create The Google Calendar Event
        event = service.events().insert(calendarId='primary', body={
            'summary': calendarEventHandler.name,
            'description': '',
            'start': {
                'dateTime': calendarEventHandler.time,
                'timeZone': 'Europe/Netherlands',
            },
            'end': {
                'dateTime': calendarEventHandler.duration,
                'timeZone': 'Europe/Netherlands',
            },
            'attendees': calendarEventHandler.attendees
                #[ {'email': 'lpage@example.com'} ]
        }).execute()

        await ctx.send("Successfully Created Your Event!")

        eventLink = event.get('htmlLink')
        await ctx.send("You can find the event over at {eventLink}!")


        


        
