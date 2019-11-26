from redbot.core import commands
from redbot.core import Config
from redbot.core import checks

import os
import re
import asyncio
import discord
import datetime
from collections import deque

from steam.webapi import WebAPI, APIHost

# instance.<interface>.<method>
# https://partner.steamgames.com/doc/webapi/ISteamApps#SetAppBuildLive
# https://partner.steamgames.com/doc/webapi_overview/responses#status_codes

# https://steam.readthedocs.io/en/latest/user_guide.html#calling-an-endpoint
# https://github.com/ValvePython/steam/blob/master/steam/webapi.py

class Steam(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=200000002)

        default_guild = {
            "steamWebAPIKey": None,
            "appid": None,
            
            "steamBuilds": None,
            "buildsIdentifier": "Win64-Shipping"
        }
        self.config.register_guild(**default_guild)
        
        self.maxSteamBuildsRequestSize = 500
        self.maxSteamBuildStorageSize = 500
        
        # Init all the guilds steam builds
        loop = asyncio.get_event_loop()
        for guild in bot.guilds:
            loop.create_task(self.initializeSteamBuildsList(guild))
    
    async def getSteamPartnerAPIInstance(self, guild):
        steamKey = await self.config.guild(guild).steamWebAPIKey()
        if(steamKey is None):
            return None

        return WebAPI(key=steamKey, apihost=APIHost.Partner)
        
    async def initializeSteamBuildsList(self, guild):
        steamBuilds = await self.getUpdatedSteamBuilds(guild)
        if steamBuilds:
            print("Loaded " + str(len(steamBuilds)) + " Steam Builds")
        else:
            print("Unable to load steam builds!")
    
    async def getUpdatedSteamBuilds(self, guild):
        steamAPIInstance = await self.getSteamPartnerAPIInstance(guild)
        if steamAPIInstance is None:
            return None
        
        appID = await self.config.guild(guild).appid()
        if appID is None:
            return None

        steamAPIInstance.ISteamApps.GetAppBuilds(appid=appID, count=self.maxSteamBuildsRequestSize)
        response = steamAPIInstance.call('ISteamApps.GetAppBuilds', appid=appID, count=self.maxSteamBuildsRequestSize)
        
        buildIdentifier = await self.config.guild(guild).buildsIdentifier()
        steamBuildObjects = [response['response']['builds'][build] for build in response['response']['builds']]
        data = [{'build_number': build['BuildID'], 'time': build['CreationTime'], 'jenkins_build_number': int(next(iter(re.findall(r'\(Build (\d+).*\)', build['Description'])), 0)), 'description': build['Description']} for build in steamBuildObjects]
  
        storedSteamBuilds = await self.config.guild(guild).steamBuilds()
        if storedSteamBuilds:
            steamBuilds = deque(storedSteamBuilds, self.maxSteamBuildStorageSize)
            steamBuildsIdList = [build['build_number'] for build in steamBuilds]
            newUniqueSteamBuilds = [build for build in data if build['build_number'] not in steamBuildsIdList]
        
            # Add new steam builds to list and keep it to maxSteamBuildStorageSize
            steamBuilds.extendleft(newUniqueSteamBuilds)
        else:
            steamBuilds = deque(data, self.maxSteamBuildStorageSize)
            
        if steamBuilds:
            await self.config.guild(guild).steamBuilds.set(list(steamBuilds))
            
        return list(steamBuilds)

    async def getSteamBuildIDFromJenkinsBuildID(self, guild, jenkins_build_number: int, refreshIfUnavailable: bool = True):
        buildIdentifier = await self.config.guild(guild).buildsIdentifier()
        # Get Steam BuildId from a Jenkins BuildId
        storedSteamBuildObjects = await self.config.guild(guild).steamBuilds()
        build_number = next((int(build['build_number']) for build in storedSteamBuildObjects if build['description'].lower().find(buildIdentifier.lower()) != -1 and int(build['jenkins_build_number']) == jenkins_build_number))
        # If build number was not found, refresh the steam builds once and try again
        if not build_number and refreshIfUnavailable:
            self.getUpdatedSteamBuilds()
            return await self.getSteamBuildIDFromJenkinsBuildID(guild, jenkins_build_number, False)
        return build_number
    async def getJenkinsBuildIDFromSteamBuildID(self, guild, steam_build_number: int, refreshIfUnavailable: bool = True):
        buildIdentifier = await self.config.guild(guild).buildsIdentifier()
        # Get Jenkins BuildId from a Steam BuildId
        storedSteamBuildObjects = await self.config.guild(guild).steamBuilds()
        build_number = next((int(build['jenkins_build_number']) for build in storedSteamBuildObjects if build['description'].lower().find(buildIdentifier.lower()) != -1 and int(build['build_number']) == steam_build_number))
        # If build number was not found, refresh the steam builds once and try again
        if not build_number and refreshIfUnavailable:
            self.getUpdatedSteamBuilds()
            return await self.getSteamBuildIDFromJenkinsBuildID(guild, steam_build_number, False)
        return build_number
    
    async def getCurrentSteamBranchBuilds(self, guild):
        steamAPIInstance = await self.getSteamPartnerAPIInstance(guild)
        if steamAPIInstance is None:
            print("No Steam API Key Set. Use the !steam webAPIKey <webapikey> command to set it!")
            return None
        appID = await self.config.guild(guild).appid()
        if appID is None:
            print("No Steam AppID Set. Use the !steam setSteamAppID <apiId> command to set it!")
            return None

        steamAPIInstance.ISteamApps.GetAppBetas(appid=appID)
        response = steamAPIInstance.call('ISteamApps.GetAppBetas', appid=appID)
        
        if response['response']['result'] is 1:
            return response['response']['betas']
        else: 
            return None
        
    
    @commands.group()
    async def steam(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid steam command passed...')

    # =========== INITialization =====================
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
    @steam.command()
    @checks.is_owner()
    async def buildIdentifier(self, ctx: commands.Context, identifier: str):
        await ctx.message.delete(delay=3)
        await self.config.guild(ctx.guild).buildsIdentifier.set(identifier)
        await ctx.send("Steam Builds Identifier has been updated!")
        
        
    # Get the current build ID's on the steam branches
    @steam.command(aliases=['c', 'list', 'latest'])
    async def current(self, ctx: commands.Context):
        async with ctx.channel.typing():
            steamBranchBuilds = await self.getCurrentSteamBranchBuilds(ctx.guild)
            if not steamBranchBuilds:
                await ctx.send("An issue occurred while retrieving the Steam Branch Builds. Check output log for details!")
                return
            
            steamBuilds = await self.config.guild(ctx.guild).steamBuilds()
            
            embed = discord.Embed(type="rich", colour=0)

            for i, branch in enumerate(steamBranchBuilds):
                jenkinsID = next((build['jenkins_build_number'] for build in steamBuilds if build['build_number'] == steamBranchBuilds[branch]["BuildID"]), "unknown")
                embed.add_field(name=branch, value=steamBranchBuilds[branch]["BuildID"], inline=True)
                embed.add_field(name="Jenkins Build" if i is 0 else "\n\u200b", value=jenkinsID, inline=True)
                embed.add_field(name="\n\u200b", value="\n\u200b", inline=True)

            await ctx.send(embed=embed)
    
    @steam.command(aliases=['p', 'update', 'set'])
    async def push(self, ctx: commands.Context, branch: str, build_number: int):
        if branch is 'public' or branch is 'default':
                await ctx.send("Not allowed to update the public branch here! Discuss this to make sure to push to the public **(live)** branch and do this in the Steamworks page!")
                return

        async with ctx.channel.typing():
            steamAPIInstance = await self.getSteamPartnerAPIInstance(ctx.guild)
            if steamAPIInstance is None:
                await ctx.send("No steam WebAPIKey set! Use the !steam webAPIKey <webapikey> command to set it!")
                return
            appID = await self.config.guild(ctx.guild).appid()
            if appID is None:
                await ctx.send("No AppID set! Use the setSteamAppID <apiId> command to set it!")
                return
            
            steam_from_jenkins_build_number = await self.getSteamBuildIDFromJenkinsBuildID(ctx.guild, build_number)
            if steam_from_jenkins_build_number:
                build_number = steam_from_jenkins_build_number

            steamAPIInstance.ISteamApps.SetAppBuildLive(appid=appID, buildid=build_number, betakey=branch)
            response = steamAPIInstance.call('ISteamApps.SetAppBuildLive', appid=appID, buildid=build_number, betakey=branch)
            
            if response['response']['result'] is 1:
                await ctx.send(f"Updated **{branch}** to build **{build_number}**. Check Steam for the update!")
            else: 
                await ctx.send("Error: " + str(response['response']['message']))
                
    @steam.command(aliases=['u', 'up'])
    async def upgrade(self, ctx: commands.Context, branch: str):
        async with ctx.channel.typing():
            steamAPIInstance = await self.getSteamPartnerAPIInstance(ctx.guild)
            if steamAPIInstance is None:
                await ctx.send("No steam WebAPIKey set! Use the `!steam webAPIKey <webapikey>` command to set it!")
                return
            appID = await self.config.guild(ctx.guild).appid()
            if appID is None:
                await ctx.send("No AppID set! Use the `!steam setSteamAppID <apiId>` command to set it!")
                return

            branch_upgrader = {
                'development': 'stable',
                'stable': 'staging'
            }
            upgrade_branch = branch_upgrader.get(branch, None)
            if upgrade_branch is None:
                await ctx.send(f"No or Invalid target branch to upgrade **{branch}** to!")
                return
            
            steamBranchBuilds = await self.getCurrentSteamBranchBuilds(ctx.guild)
            if not steamBranchBuilds:
                await ctx.send("An issue occurred while retrieving the Steam Branch Builds. Check output log for details!")
                return
            
            build_number = None
            if steamBranchBuilds[upgrade_branch]['BuildID'] >= steamBranchBuilds[branch]['BuildID']:
                await ctx.send("Branch to upgrade to already has a higher or equal version! Use `!steam push <branch> <buildid>` to push a specific branch instead.")
                return
            else:
                build_number = steamBranchBuilds[branch]['BuildID']
            
            steamAPIInstance.ISteamApps.SetAppBuildLive(appid=appID, buildid=build_number, betakey=upgrade_branch)
            response = steamAPIInstance.call('ISteamApps.SetAppBuildLive', appid=appID, buildid=build_number, betakey=branch)
            
            if response['response']['result'] is 1:
                await ctx.send(f"Upgraded **{branch}** with build **{build_number}** to **{upgrade_branch}**. Check Steam for the update!")
            else: 
                await ctx.send("Error: " + str(response['response']['message']))


    @steam.command(aliases=['b', 'getbuilds'])
    async def builds(self, ctx: commands.Context):
        async with ctx.channel.typing():
            
            steamAPIInstance = await self.getSteamPartnerAPIInstance(ctx.guild)
            if steamAPIInstance is None:
                await ctx.send("No steam WebAPIKey set! Use the !steam webAPIKey <webapikey> command to set it!")
                return
            
            appID = await self.config.guild(ctx.guild).appid()
            if appID is None:
                await ctx.send("No AppID set! Use the setSteamAppID <apiId> command to set it!")
                return

            steamAPIInstance.ISteamApps.GetAppBuilds(appid=appID, count=25)
            response = steamAPIInstance.call('ISteamApps.GetAppBuilds', appid=appID, count=25)
            
            embed = discord.Embed(type="rich", colour=0)
            for build in reversed(list(response['response']['builds'].values())):
                embed.add_field(name=build['Description'], value="**" + str(build['BuildID']) + "**   *" + datetime.datetime.utcfromtimestamp(int(build['CreationTime'])).strftime('%d-%m-%Y %H:%M:%S') + "*", inline=False)

            await ctx.send(embed=embed)
    