from discord.ext import commands
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
import discord
import asyncio


class TemporaryVoice:
    """A cog to create TeamSpeak-like voice channels."""
    def __init__(self, liara):
        self.liara = liara
        self.config = dataIO.load_json('pandentia.tempvoice')
        self.config_default = {'channel': None, 'limit': 0}

    @staticmethod
    def filter(channels):
        _channels = []
        for channel in channels:
            if channel.name.startswith('\U0001d173' * 3):
                _channels.append(channel)
        return _channels

    @staticmethod
    async def create_channel(member: discord.Member):
        guild = member.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False),
            member: discord.PermissionOverwrite(connect=True, manage_roles=True)
        }
        channel = await guild.create_voice_channel(('\U0001d173' * 3 + '{}\'s Channel'.format(member.name))[0:32],
                                                   overwrites=overwrites)
        await member.move_to(channel)

    async def on_voice_state_update(self, member, *_):
        guild = member.guild
        if guild is None:
            return  # /shrug
        if self.config.get(guild.id) is None:
            return
        # lobby processing
        channel = self.liara.get_channel(self.config[guild.id]['channel'])
        if channel is None:
            return
        for member in channel.members:
            try:
                await self.create_channel(member)
            except discord.Forbidden:
                pass
        # empty channel cleanup
        await asyncio.sleep(1)  # wait for the dust to settle
        channels = self.filter(guild.voice_channels)
        for channel in channels:
            if len(channel.members) == 0:
                try:
                    await channel.delete()
                except discord.NotFound:
                    pass

    @commands.command()
    @checks.mod_or_permissions(manage_channels=True)
    async def create_lobby(self, ctx):
        """Creates a temporary voice lobby."""
        config = self.config.get(ctx.guild.id, self.config_default)
        if config['channel'] is not None:
            channel = self.liara.get_channel(config['channel'])
            if channel is not None:
                await ctx.send('You need to remove the original lobby before creating another one.')
                return
        try:
            channel = await ctx.guild.create_voice_channel('Lobby', overwrites={
                ctx.guild.default_role: discord.PermissionOverwrite(speak=False)})
            if self.config.get(ctx.guild.id) is None:
                config['channel'] = channel.id
                self.config[ctx.guild.id] = config
            else:
                self.config[ctx.guild.id]['channel'] = channel.id
            await ctx.send('Channel created! You can rename it to whatever you want now.')
        except discord.Forbidden:
            await ctx.send('It would appear that I don\'t have permissions to create channels.')


def setup(liara):
    liara.add_cog(TemporaryVoice(liara))
