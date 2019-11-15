from redbot.core import commands

import re
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

    def convertMentionsToUserIDs(self, message):
        users = (mention.id for mention in message.mentions)
        for role in message.role_mentions:
            users = list(set().union(users, (member.id for member in role.members)))
        return users

    async def convertUserIdentificatorsToUsers(self, message):
        registeredUsers = await self.config.guild(self.ctx.guild).usersConverter()
        
        # Check if everyone was mentioned
        if message.mention_everyone:
            return (user for user in registeredUsers)

        # Get all the userIDs from the mentioned users
        mentionedUserIDs = self.convertMentionsToUserIDs(message)
        
        # Remove command group and command name
        userData = message.clean_content#.split(' ', 2)[1]

        # Get all values that are in quotes
        quotedValues = re.findall(r'"(.*?)"', userData)        
        # Remove quoted values from other data
        for val in quotedValues:
            userData = userData.replace('"' + val + '"', "")

        # Format all double spaces out of the content as we will be splitting on spaces
        userData = re.sub(r"\s+"," ", userData, flags = re.I)

        # Split on space
        userData = userData.split()
        
        userData.extend(quotedValues)

        def findUser(user):
            for registeredUser in registeredUsers:
                if str(user) == str(registeredUser['email']):
                    return registeredUser
                if registeredUser['name'].find(user) != -1:
                    return registeredUser
                if str(user) == str(registeredUser['studentID']):
                    return registeredUser
            return None
    
        users = []
        for user in userData:
            foundUser = findUser(user)
            if foundUser != None:
                users.append(foundUser)
     
        # Return list of unique users
        uniqueUsersIDs = list(set().union([user['userID'] for user in users], mentionedUserIDs))
        returnUsers = [user for user in registeredUsers if user['userID'] in uniqueUsersIDs]
        return returnUsers


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
            self.attendees = await self.convertUserIdentificatorsToUsers(message)
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