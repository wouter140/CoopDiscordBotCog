from redbot.core import commands

import discord

class CreateCalendarEvent():

    client = None

    name = None
    time = None
    duration = None
    attendees = None

    def __init__(self, ctx):
        client = ctx
        client.send("===== We are making a new Calendar Event! =====")

    async def HandleName(self):
        await client.send("What are we calling this event?")

        message, user = await client.wait_for('message', timeout=120.0)
        self.name = message

    async def HandleDescription(self):
        await client.send("Do you have a more detailed description?")

        message, user = await client.wait_for('message', timeout=120.0)
        self.name = message

    async def HandleTime(self):
        await client.send("When is this event going to take place?")

        message, user = await client.wait_for('message', timeout=120.0)
        self.time = message

    async def HandleDuration(self):
        await client.send("How long is this event going to take?")

        message, user = await client.wait_for('message', timeout=120.0)
        self.duration = message

    async def HandleAttendees(self):
        await client.send("Anyone that has to attend this meeting?")

        message, user = await client.wait_for('message', timeout=120.0)
        #TODO: Convert @'s, numbers and names to user emails
        self.attendees = message

    async def FinishEvent(self):
        await client.send("Do you want to confirm this Event at {} for {}?")

        message, user = await client.wait_for('message', timeout=120.0)
        return (message.lower() == "yes" or message.lower() == "y")