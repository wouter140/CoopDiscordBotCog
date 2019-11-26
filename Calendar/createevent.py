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
    externalAttendees = None

    stageMessage = None

    def __init__(self, ctx: commands.Context, bot, config):
        self.ctx = ctx
        self.bot = bot
        self.config = config

    # Check function if the user is equal to the person that started the command and its in the same channel
    def check(self, m):
        return m.author == self.ctx.author and m.channel == self.ctx.channel

    def convertMentionsToUserIDs(self, message):
        users = [message.author.id]
        users = list(set().union(users, (mention.id for mention in message.mentions)))
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
        userData = re.sub(r'<@&?\d+>', '', message.content)

        # Get all values that are in quotes
        quotedValues = re.findall(r'"(.*?)"', userData)
            
        # Remove quoted values from other data
        userData = re.sub(r'"(.*?)"', '', userData)

        # Format all double spaces out of the content as we will be splitting on spaces
        userData = re.sub(r"\s+"," ", userData, flags = re.I)

        # Split on space
        userData = userData.split()
        
        userData.extend(quotedValues)

        def findUser(user):
            for registeredUser in registeredUsers:
                if str(user).lower() == str(registeredUser['email']).lower():
                    return registeredUser
                if registeredUser['name'].lower().find(user.lower()) != -1:
                    return registeredUser
                if str(user) == str(registeredUser['studentID']):
                    return registeredUser
            return None
    
        users = self.attendees
        externalUsers = []
        unknownUsers = []
        for user in userData:
            foundUser = findUser(user)
            if foundUser != None: # Check for user found in registered users
                users.append(foundUser)
            elif re.search(r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$", user): # Check for email adress to make an external user
                externalUsers.append(user)
            else: # otherwise its an unknown user.
                unknownUsers.append(user)
     
        # Return list of unique users
        uniqueUsersIDs = list(set().union(set(), [user['userID'] for user in users], mentionedUserIDs))
        returnUsers = [user for user in registeredUsers if user['userID'] in uniqueUsersIDs]
        return {
            "users": returnUsers,
            "external": externalUsers,
            "unknown": unknownUsers
        }


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
            retry = True
            while retry:
                retry = False
                
                # Get start time
                message = await self.bot.wait_for('message', timeout=40.0, check=self.check)
                try:
                    startDateTime = datetime.strptime(message.content, "%d-%m-%Y %H:%M")
                except ValueError:
                    retry = True
                    await self.stageMessage.edit(content="**Thats an invalid Date and/or Time!** When is this event going to take place? ***Format: DD-MM-YYYY HH:MM***")
                finally:
                    await message.delete()
                
            self.time = startDateTime
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def HandleDurationMessage(self):
        await self.stageMessage.edit(content="**How long is this event going to take?** *Format: HH:MM*")
    async def HandleDuration(self):
        try:
            retry = True
            while retry:
                retry = False
                
                # Get start time
                message = await self.bot.wait_for('message', timeout=40.0, check=self.check)
                try:
                    durationTime = datetime.strptime(message.content, "%H:%M")
                except ValueError:
                    retry = True
                    await self.stageMessage.edit(content="**Thats an invalid Duration!** How long is this event going to take? ***Format: HH:MM***")
                finally:
                    await message.delete()
                
            self.duration = durationTime
            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def HandleAttendeesMessage(self):
        await self.stageMessage.edit(content="**Anyone that has to attend this meeting?** *Discord Tag, studentID, email or Name works (full name in quotes)*")
    async def HandleAttendees(self):
        try:
            retry = True
            unknownRetry = False
            self.attendees = list()
            self.externalAttendees = list()

            while retry:
                retry = False

                # Get attendees
                message = await self.bot.wait_for('message', timeout=120.0, check=self.check)

                convertedAttendees = await self.convertUserIdentificatorsToUsers(message)
                await message.delete()
                
                self.attendees = convertedAttendees['users']

                if len(convertedAttendees['external']) > 0:
                    self.externalAttendees.extend(convertedAttendees['external'])

                if len(convertedAttendees['unknown']) > 0 and not unknownRetry:
                    await self.stageMessage.edit(content="**Unknown Users:** ``" + ', '.join(convertedAttendees['unknown']) + '``. Enter these users or "continue" to skip.')
                    unknownRetry = True
                    retry = True
                elif len(self.attendees) <= 0 and len(self.externalAttendees) <= 0:
                    await self.stageMessage.edit(content="**No users entered!** ***Discord Tag, studentID, email or Name works (full name in quotes).***")
                    retry = True
                    unknownRetry = False

            return True
        except asyncio.TimeoutError:
            await self.ctx.send("Timed out, stopped creating event!")
            return False

    async def FinishEventMessage(self):
        formattedDatetime = self.time.strftime("%A, %d. %B %Y %I:%M%p")
        formattedDuration = self.duration.strftime("%H:%M")
        await self.stageMessage.edit(content=f"Do you want to confirm this Event at **{formattedDatetime}** for **{formattedDuration}**?")
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