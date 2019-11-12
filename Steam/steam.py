from redbot.core import commands
from redbot.core import Config
from redbot.core import checks

import os
import asyncio
import discord

from steam.webapi import WebAPI, APIHost


class Steam(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=192837645)

        default_guild = {
            "steamWebAPIKey": None,
            "appid": None
        }
        self.config.register_guild(**default_guild)

    @commands.group()
    async def steam(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid steam command passed...')

    async def getSteamPartnerAPIInstance(self, ctx: commands.Context):
        steamKey = await self.config.guild(ctx.guild).steamWebAPIKey()
        if(steamKey is None):
            await ctx.send("No steam WebAPIKey set! Use the setSteamWebAPIKey <webapikey> command to set it!")
            return None

        return WebAPI(key=steamKey, apihost=APIHost.Partner)


    @steam.command()
    @checks.is_owner()
    async def webAPIKey(self, ctx: commands.Context, new_value: str):
        await ctx.message.delete(delay=3)
        await self.config.guild(ctx.guild).steamWebAPIKey.set(new_value)
        await ctx.send("Steam WebAPIKey has been updated!")

    @steam.command()
    @checks.is_owner()
    async def appID(self, ctx: commands.Context, new_value: int):
        await ctx.message.delete(delay=3)
        await self.config.guild(ctx.guild).appid.set(new_value)
        await ctx.send("Steam AppID has been updated!")


    # Get the current build ID's on the steam branches
    @steam.command(aliases=['list', 'latest'])
    async def current(self, ctx: commands.Context):
        async with ctx.channel.typing():
            steamAPIInstance = await self.getSteamPartnerAPIInstance(ctx)
            if steamAPIInstance is None:
                return
            appID = await self.config.guild(ctx.guild).appid()
            if appID is None:
                await ctx.send("No AppID set! Use the setSteamAppID <apiId> command to set it!")
                return

            steamAPIInstance.ISteamApps.GetAppBetas(appid=appID)
            response = steamAPIInstance.call('ISteamApps.GetAppBetas', appid=appID)

            embed = discord.Embed(type="rich", colour=0)

            for branch in response['response']['betas']:
                embed.add_field(name=branch, value=response['response']['betas'][branch]["BuildID"], inline=False)

            await ctx.send(embed=embed)
    
    @steam.command(aliases=['update', 'set'])
    async def push(self, ctx: commands.Context, branch: str, build_number: int):
        if branch is 'public' or branch is 'default':
                await ctx.send("Not allowed to update the public branch here! Discuss this to make sure to push to the public **(live)** branch and do this in the Steamworks page!")
                return

        async with ctx.channel.typing():
            steamAPIInstance = await self.getSteamPartnerAPIInstance(ctx)
            if steamAPIInstance is None:
                return
            appID = await self.config.guild(ctx.guild).appid()
            if appID is None:
                await ctx.send("No AppID set! Use the setSteamAppID <apiId> command to set it!")
                return

            steamAPIInstance.ISteamApps.SetAppBuildLive(appid=appID, buildid=build_number, betakey=branch)
            response = steamAPIInstance.call('ISteamApps.SetAppBuildLive', appid=appID, buildid=build_number, betakey=branch)
            
            if response['response']['result'] is 1:
                await ctx.send(f"Updated **{branch}** to build **{build_number}**. Check Steam for the update!")
            else: 
                await ctx.send("Error: " + str(response['response']['message']))
                
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
    