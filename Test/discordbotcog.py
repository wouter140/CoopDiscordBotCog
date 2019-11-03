from redbot.core import commands

import discord

class DiscordBotCog(commands.Cog):
    """My custom cog"""

    @commands.command()
    async def test(self, ctx):
        """This does stuff!"""
        # Your code will go here
        await ctx.send("I can do stuff!")
        await ctx.send("Hey!")