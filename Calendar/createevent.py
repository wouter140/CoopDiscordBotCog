from redbot.core import commands

from datetime import datetime
import asyncio
import discord

class CreateCalendarEvent():

    name = None
    time = None
    duration = None
    attendees = None

    stageMessage = None

    def __init__(self, ctx: commands.Context, bot, config):
        self.ctx = ctx
        self.bot = bot
        self.config = config

    # Check function if the user is equal to the person that started the command and its in the same channel
    def check(self, m):
        return m.author == self.ctx.author and m.channel == self.ctx.channel

    async def HandleNameMessage(self):
        await self.stageMessage.edit(content="**What are we calling this event?**")
    async def HandleName(self):
        try:
            # Get message
            message = await self.bot.wait_for('message', timeout=30.0, check=self.check)
            self.name = message.content
            await message.delete()
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def HandleDescriptionMessage(self):
        await self.stageMessage.edit(content="**Do you have a more detailed description?**")
    async def HandleDescription(self):
        try:
            # Get description
            message = await self.bot.wait_for('message', timeout=120.0, check=self.check)
            self.description = message.content
            await message.delete()
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def HandleTimeMessage(self):
        await self.stageMessage.edit(content="**When is this event going to take place?** *Format: DD-MM-YYYY HH:MM*")
    async def HandleTime(self):
        try:
            # Get start time
            message = await self.bot.wait_for('message', timeout=40.0, check=self.check)
            self.time = message.content #TODO: Validation of format
            await message.delete()
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def HandleDurationMessage(self):
        await self.stageMessage.edit(content="**How long is this event going to take?** *Format: HH:MM*")
    async def HandleDuration(self):
        try:
            # Get duration
            message = await self.bot.wait_for('message', timeout=40.0, check=self.check)
            self.duration = message.content #TODO: Validation of format
            await message.delete()
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def HandleAttendeesMessage(self):
        await self.stageMessage.edit(content="**Anyone that has to attend this meeting?**")
    async def HandleAttendees(self):
        try:
            # Get attendees
            message = await self.bot.wait_for('message', timeout=120.0, check=self.check)
            #TODO: Convert @'s, numbers and names to user emails
            self.attendees = message.content
            await message.delete()
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def FinishEventMessage(self):
        formattedDatetime = datetime.strptime(self.time, "%d-%m-%Y %H:%M").strftime("%A, %d. %B %Y %I:%M%p")
        await self.stageMessage.edit(content=f"Do you want to confirm this Event at **{formattedDatetime}** for **{self.duration}**?")
        await self.stageMessage.add_reaction(await self.config.guild(self.ctx.guild).successEmoji())
        await self.stageMessage.add_reaction(await self.config.guild(self.ctx.guild).cancelEmoji())
    async def FinishEvent(self):
        try:
            def check(reaction, user):
                return user == self.ctx.author
            # Get confirmation
            reaction, user = await self.bot.wait_for('reaction_add', timeout=20.0, check=check)
            confirm = (str(reaction) == await self.config.guild(self.ctx.guild).successEmoji())
            await self.stageMessage.clear_reactions()
            return confirm
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False