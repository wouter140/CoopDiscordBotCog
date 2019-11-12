# CoopDiscordBotCog
Collection of plugins or cogs as they are known in RedBot for use with the Coop Gamedev team.

## Redbot
[Redbot Github Page](https://github.com/Cog-Creators/Red-DiscordBot)

### Redbot Installation
[Installing Red on Windows](https://red-discordbot.readthedocs.io/en/stable/install_windows.html)
```bash
python -m pip install -U Red-DiscordBot
```

[Installing Red on most Linux versions](https://red-discordbot.readthedocs.io/en/stable/install_linux_mac.html)

### Starting the bot in a terminal:
```bash
redbot-launcher
```

### In Discord:
```bash
# Add path to search for packages
!addpath <path to the root of this package /CoopDiscordBotCog>

# To load a package
!load <package name>
```
  
## Calendar Package:

Dependencies:
```bash
# Google Calendar API's
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

```

To load the Calendar package
```bash
!load Calendar

# Initial Setup
!initcalendar

# Commands
!createevent
```


## Steam Package:

Dependencies:
```bash
# ValvePython/steam python steamAPI helper
pip install -U steam

```

To load the Steam package
```bash
!load Steam

# Initial Setup
!steam webAPIKey <publisher webapikey>
!steam appID <appid>

# Commands
!steam list
!steam push <branch> <buildID>
!steam upgrade <branch>
```
