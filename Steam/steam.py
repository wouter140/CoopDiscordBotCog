from redbot.core import commands

import os
import asyncio
import discord

class Steam(commands.Cog):
    """Calendar Cog for the Discord Bot.
       Implements Google Calendar Functionality with the bot."""

    def __init__(self, bot):
        self.bot = bot

    