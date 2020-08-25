from redbot.core import commands, checks

import discord
import asyncio

import os
import importlib.util
spec = importlib.util.spec_from_file_location("module.name", os.path.dirname(os.path.realpath(__file__)) + "/../Logger/logger.py")
foo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(foo)


class Utils(commands.Cog):
    """Utilities Cog for the Discord Bot.
       Implements some ease of use and QOL commands."""

    def __init__(self, bot):
        self.bot = bot
        
    # Commands grouper
    @commands.group()
    async def utils(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid command passed...')
    
    # Command that pins the last send message
    @commands.command()
    async def pin(self, ctx: commands.Context):
        if ctx.channel.last_message:
            ctx.channel.last_message.pin()
            
    @utils.command()
    @checks.is_owner()
    async def setLoggingChannel(self, ctx, channel: discord.TextChannel):
        await foo.Logger().setLoggingChannel(ctx.guild, channel.id)
        await ctx.send("Updated Logging Channel")
        await foo.Logger().logEventMessage(ctx.guild, foo.Logger.Type.Info, 'Logger', 'Updated Logging Channel')
            
    @utils.command()
    @checks.is_owner()
    async def getCachedMessages(self, ctx):
        messages = list()
        for index in range(0, len(self.bot.cached_messages)):
            messages.append(self.bot.cached_messages.__getitem__(index))
        
        await ctx.send("**The bot currently has " + str(len(self.bot.cached_messages)) + " Cached Messages**")
        startIndex = 0
        while True:
            currMessages = messages[startIndex:startIndex+8]
            await ctx.send(("\n".join(["**MessageID:** " + str(message.id) + " | **Guild:** " + message.guild.name + " | **Channel:** " + message.channel.name + " | **User:** " + str(message.author.display_name) + " | **Message:** " + ((discord.utils.escape_markdown(message.clean_content[:60]).replace('\n', "") + '..') if len(message.clean_content) > 60 else discord.utils.escape_markdown(message.clean_content).replace('\n', '')) for message in currMessages])) + "\u200b")
            startIndex+=8
            if startIndex >= len(self.bot.cached_messages):
                return
            
            await asyncio.sleep(.3)
        
        
    
    