# Liara
##### A Discord bot written by Pandentia and contributors

[![Python](https://img.shields.io/badge/python-3.5-blue.svg)](https://python.org) [![Discord](https://discordapp.com/api/guilds/247754180763189258/widget.png?style=shield)](https://discord.gg/JRJjMTy)

### What is Liara, exactly?
Liara is a direct competitor to [Twentysix26's Red](https://github.com/Twentysix26/Red-DiscordBot), the key difference being actual modularity. In addition to being backwards-compatible with most of Red's cogs (plugins), Liara also has some additional features that might prove useful for bot hosting, such as

 * Actual modularity
   * Red isn't as fully modular as it's advertised, because the `owner.py` cog can't be unloaded, yet there are commands there that could've easily been moved to an additional cog (or multiple)
   * Liara lets you replace the bootloader and core cog, `core.py`, so you can make her work the way you want
 * Multiple owner support
 * Sharding support
   * Uses Redis as a backend, meaning you can easily hook third-party applications into the database and have them update configuration settings on-the-fly
 * Selfbot mode
 * No JSON files anywhere in sight

### Join our Discord server!
[![Discord](https://discordapp.com/api/guilds/247754180763189258/widget.png?style=banner3)](https://discord.gg/JRJjMTy)

This is where you can ask for help setting Liara up, and we try to keep a friendly community. You can also discuss writing cogs for Liara.

### Final words
Of course, all these features come at a cost: Windows support.
We have chosen not to support Windows users, because setting up Liara on Windows usually proves to be difficult. This doesn't mean it's impossible, but Liara's official support channel is only for Linux/UNIX support. You can, however, ask in the `#windows-support` channel in the aforementioned Discord server for Windows support.

### Disclaimer
Liara is still in very active development, so things might change at any time without prior notice.

### Sign-off for Twentysix
Hi. If you're reading this, you might wonder why I set up this project. And no, it's not to spite you. To be honest, I have no quarrel with you. I'm far past that. All I wanted a better Red, and Red was slipping further and further away from my idea of a "fully modular bot". I was faced with the difficult choice of having to put up with Red or make my own, and I chose the latter.

I hope you can respect my decision, and see why I chose to do this.

<sub>Sidenote: I enjoyed being a part of Red's community, even if it didn't last that long. At any rate, thank you for letting me help the community while I could. I'd like to go back some day. <sub><sup>[Contact information](https://api.pandentia.cf/discord/user/136900814408122368)</sup></sub></sub>