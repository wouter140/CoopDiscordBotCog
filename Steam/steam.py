from redbot.core import commands
from redbot.core import Config
from redbot.core import checks

import os
import asyncio
import discord

from steam.webapi import WebAPI
from steam.webapi import APIHost

class Steam(commands.Cog):
    """Calendar Cog for the Discord Bot.
       Implements Google Calendar Functionality with the bot."""

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=192837645)

        default_guild = {
            "steamWebAPIKey": None,
            "appid": None
        }
        self.config.register_guild(**default_guild)


    async def getSteamPartnerAPIInstance(self, ctx: commands.Context):
        steamKey = await self.config.guild(ctx.guild).steamWebAPIKey()
        if(steamKey == None):
            await ctx.send("No steam WebAPIKey set! Use the setSteamWebAPIKey <webapikey> command to set it!")
            return None

        return WebAPI(key=steamKey, apihost=APIHost.Partner)


    @commands.command()
    @checks.is_owner()
    async def setSteamWebAPIKey(self, ctx: commands.Context, new_value: str):
        await self.config.guild(ctx.guild).steamWebAPIKey.set(new_value)
        await ctx.send("Steam WebAPIKey has been updated!")

    @commands.command()
    @checks.is_owner()
    async def setSteamAppID(self, ctx: commands.Context, new_value: int):
        await self.config.guild(ctx.guild).appid.set(new_value)
        await ctx.send("Steam AppID has been updated!")

    
    @commands.command()
    async def push(self, ctx: commands.Context, branch: str, build_number: int):
        steamAPIInstance = await self.getSteamPartnerAPIInstance(ctx)
        if(steamAPIInstance == None):
            return

        appID = await self.config.guild(ctx.guild).appid()
        if(appID == None):
            await ctx.send("No AppID set! Use the setSteamAppID <apiId> command to set it!")
            return

        # instance.<interface>.<method>
        steamAPIInstance.ISteamApps.SetAppBuildLive(appid=appID, buildid=build_number, betakey=branch)
        response = steamAPIInstance.call('ISteamApps.SetAppBuildLive', appid=appID, buildid=build_number, betakey=branch)
        print(response)
        await ctx.send(response)

    @commands.command()
    async def getbetas(self, ctx: commands.Context):
        steamAPIInstance = await self.getSteamPartnerAPIInstance(ctx)
        if(steamAPIInstance == None):
            return

        appID = await self.config.guild(ctx.guild).appid()
        if(appID == None):
            await ctx.send("No AppID set! Use the setSteamAppID <apiId> command to set it!")
            return

        steamAPIInstance.ISteamApps.GetAppBetas(appid=appID)
        response = steamAPIInstance.call('ISteamApps.GetAppBetas', appid=appID)
        print(response)
        await ctx.send(response)

    @commands.command()
    async def getbuilds(self, ctx: commands.Context):
        steamAPIInstance = await self.getSteamPartnerAPIInstance(ctx)
        if(steamAPIInstance == None):
            return

        appID = await self.config.guild(ctx.guild).appid()
        if(appID == None):
            await ctx.send("No AppID set! Use the setSteamAppID <apiId> command to set it!")
            return

        steamAPIInstance.ISteamApps.GetAppBuilds(appid=appID)
        response = steamAPIInstance.call('ISteamApps.GetAppBuilds', appid=appID)
        print(response)
        await ctx.send(response)
    