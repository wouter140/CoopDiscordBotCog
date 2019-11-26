from redbot.core import commands

import discord


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
    
    