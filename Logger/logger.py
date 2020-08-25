from redbot.core import Config, utils

import discord

from enum import Enum

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    
class Logger(metaclass=Singleton):
    
    class Type(Enum):
        Info = 1
        Warning = 2
        Error = 3
    
    def __init__(self):
        self.config = Config.get_conf(self, identifier=500000005)
        
        default_guild = {
            "loggingChannel": None
        }
        self.config.register_guild(**default_guild)
    
    @staticmethod 
    def TypeToString(type: Type) -> str:
        if type is Logger.Type.Warning:
            return "**Warning**"
        if type is Logger.Type.Error:
            return "**Error**"
        return "**Info**"
    
    @staticmethod 
    def TypeToColor(type: Type) -> discord.Colour:
        if type is Logger.Type.Warning:
            return discord.Colour.dark_orange()
        if type is Logger.Type.Error:
            return discord.Colour.red()
        return discord.Colour.lighter_grey()
    
    @staticmethod 
    def ConvertMessagWithStatus(type: Type, message: str) -> str:
        if type is Logger.Type.Warning:
            return utils.chat_formatting.warning(Logger.TypeToString(type).upper() + ": " + message)
        if type is Logger.Type.Error:
            return utils.chat_formatting.error(Logger.TypeToString(type).upper() + ": " + message)
        return utils.chat_formatting.info(Logger.TypeToString(type).upper() + ": " + message)
    

    async def setLoggingChannel(self, guild: discord.Guild, channel: discord.TextChannel):
        await self.config.guild(guild).loggingChannel.set(channel)
        return True

    
    async def logMessage(self, guild: discord.Guild, type: Type, message: str):
        logChannelID = await self.config.guild(guild).loggingChannel()
        logChannel: dicord.TextChannel = guild.get_channel(logChannelID)
        if logChannel:
            await logChannel.send(Logger.ConvertMessagWithStatus(type, message))
            return True
        return False
    
    async def logEmbed(self, guild: discord.Guild, embed: discord.Embed, type: Type.Info, message: str = None):
        logChannelID = await self.config.guild(guild).loggingChannel()
        logChannel: dicord.TextChannel = guild.get_channel(logChannelID)
        embed.color = Logger.TypeToColor(type)
        if logChannel:
            if message:
                await logChannel.send(content=Logger.ConvertMessagWithStatus(type, message), embed=embed)
            else:
                await logChannel.send(embed=embed)
            return True
        return False


    async def logEventMessage(self, guild: discord.Guild, type: Type, event: str, message: str = ''):
        logChannelID = await self.config.guild(guild).loggingChannel()
        logChannel: dicord.TextChannel = guild.get_channel(logChannelID)
        if logChannel:
            await logChannel.send(Logger.ConvertMessagWithStatus(type, event.upper() + ': ' + message))
            return True
        return False
    
    async def logEventMessageEmbed(self, guild: discord.Guild, type: Type, event: str, embed: discord.Embed, message: str = ''):
        logChannelID = await self.config.guild(guild).loggingChannel()
        logChannel: dicord.TextChannel = guild.get_channel(logChannelID)
        embed.color = Logger.TypeToColor(type)
        if logChannel:
            if message:
                await logChannel.send(content=Logger.ConvertMessagWithStatus(type, event.upper() + ': ' + message), embed=embed)
            else:
                await logChannel.send(embed=embed)
            
            return True
        return False