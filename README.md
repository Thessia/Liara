# Liara
##### A Discord bot written by Pandentia and contributors

[![Python](https://img.shields.io/badge/python-3.5-blue.svg)](https://python.org)
[![Discord](https://discordapp.com/api/guilds/247754180763189258/widget.png?style=shield)](https://discord.gg/JRJjMTy)
[![Waffle.io - Issues in progress](https://badge.waffle.io/Thessia/Liara.svg?label=in%20progress&title=In%20Progress)](http://waffle.io/Thessia/Liara)

### What is Liara, exactly?
Liara is a fully-modular, expandable and flexible framework for creating efficient Discord bots.

* Full modularity
    * In contrast to some other frameworks, Liara is completely modular. Everything is removeable and tweakable.
    * Liara lets you replace the bootloader and core cog, `core.py`, so you can make her work the way you want should 
    you feel inclined to do so.
    * Instead of using a settings.json file for settings, Liara uses command-line flags.
    * Environment variables can be used to substitute command-line flags, making bot hosting easier for hosting 
    providers.
* Multiple owner support
    * This lets you share Liara with friends and your hosting provider easily.
* Sharding support
    * Uses Redis as a backend, meaning you can easily hook third-party applications into the database and have them 
    update configuration settings on-the-fly.
    * Dedicated and built-in cog for managing shards.
    * Cross-shard communication and remote control using Redis Pub/Sub.
    * The entire system can be spanned across multiple hosts seamlessly.
        * This means if you wanted to build a Raspberry Pi cluster running Liara, there would be nothing stopping you.
* Selfbot mode
    * This lets you run Liara as a selfbot, so that you can take the benefits of a fully modular bot to any server 
    (within reason).
* No JSON files anywhere in sight.
* Logs are stored in a compressed format (`.bz2`), so that you don't have to waste any disk space.
* Modular message-processing preconditions.
    * This lets you change the message processing behavior to your liking. You can, for example, set up a whitelist of who can use Liara with this.
    * You can also set up a blacklist of people who should never be able to use Liara.

### Donations
No. I don't feel like making money off of my community would be morally correct, since it's fairly simple code for what it's worth.

However, if this project has helped you, feel free to :star: it.

### Join our Discord server!
[![Discord](https://discordapp.com/api/guilds/247754180763189258/widget.png?style=banner3)](https://discord.gg/JRJjMTy)

This is where you can ask for help setting Liara up, and we try to keep a friendly community. You can also discuss writing cogs for Liara.

### Final words
Of course, all these features come at a cost: Windows support.
We have chosen not to support Windows users, because setting up Liara on Windows usually proves to be difficult. This
doesn't mean it's impossible, but Liara's official support channel is only for Linux/UNIX support. You can, however,
ask in the `#windows-support` channel in the aforementioned Discord server for Windows support.

### Disclaimer
Liara is still in very active development, so things might change at any time without prior notice.
