from redbot.core import commands

import asyncio
import discord

class CreateCalendarEvent():

    name = None
    time = None
    duration = None
    attendees = None

    def __init__(self, ctx: commands.Context, bot):
        self.ctx = ctx
        self.bot = bot
        ctx.send("===== We are making a new Calendar Event! =====")

    # Check function if the user is equal to the person that started the command and its in the same channel
    def check(self, m):
        return m.author == self.ctx.author and m.channel == self.ctx.channel

    async def HandleName(self):
        await self.ctx.send("What are we calling this event?")

        try:
            # Get message
            message = await self.bot.wait_for('message', timeout=60.0, check=self.check)
            self.name = message.content
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def HandleDescription(self):
        await self.ctx.send("Do you have a more detailed description?")

        try:
            # Get description
            message = await self.bot.wait_for('message', timeout=60.0, check=self.check)
            self.description = message.content
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def HandleTime(self):
        await self.ctx.send("When is this event going to take place? Format: DD-MM-YYYY HH:MM")

        try:
            # Get start time
            message = await self.bot.wait_for('message', timeout=60.0, check=self.check)
            self.time = message.content
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def HandleDuration(self):
        await self.ctx.send("How long is this event going to take?")

        try:
            # Get duration
            message = await self.bot.wait_for('message', timeout=60.0, check=self.check)
            self.duration = message.content
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def HandleAttendees(self):
        await self.ctx.send("Anyone that has to attend this meeting?")

        try:
            # Get attendees
            message = await self.bot.wait_for('message', timeout=60.0, check=self.check)
            #TODO: Convert @'s, numbers and names to user emails
            self.attendees = message.content
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def FinishEvent(self):
        await self.ctx.send("Do you want to confirm this Event at {} for {}?")

        try:
            # Get confirmation
            message = await self.bot.wait_for('message', timeout=60.0, check=self.check)
            return (message.content.lower() == "yes" or message.content.lower() == "y")
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return True