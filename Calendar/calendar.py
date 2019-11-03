from redbot.core import commands

import os
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
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            ctx.send("Check the bot server for a google calendar login screen!")

            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        else:
            await ctx.send("Already Valid Credentials Available! Delete token.pickle in the bot to reset.")
 
    @commands.command()
    async def createevent(self, ctx):
        service = get_calendar_service()
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


        


        
