from discord.ext import commands
from cogs.utils import checks
from cogs.utils import dataIO
import asyncio
import discord


class Welcome:
    def __init__(self, liara):
        self.liara = liara
        self.welcome = dataIO.load('pandentia.welcome')
        self.disabled = False

    def __unload(self):
        self.welcome.die = True

    def check_for_guild(self, guild_id):
        if self.welcome.get(guild_id, {'status': False})['status']:
            return True
        else:
            return False

    @commands.command()
    @checks.mod_or_permissions(administrator=True)
    async def welcomeset(self, ctx, channel: discord.TextChannel, *, message: str):
        """Sets a welcome message for your current server.
        - channel: A text channel
        - message: A markdown-formatted text message. use the %n and %m placeholders for
        names and mentions respectively."""
        if len(message) > 750:
            await ctx.send('That welcome message is too long. Try something under 750 characters.')
            return
        guild = str(ctx.message.guild.id)
        welcome_obj = {'status': True, 'channel': str(channel.id), 'message': message}
        self.welcome[guild] = welcome_obj
        await ctx.send('Welcome message set.')

    @commands.command()
    @checks.mod_or_permissions(administrator=True)
    async def welcomeclear(self, ctx):
        """Clears the server's welcome message."""
        guild = str(ctx.message.guild.id)
        if self.check_for_guild(guild):
            self.welcome.pop(guild)
            await ctx.send('Welcome message cleared.')
        else:
            await ctx.send('This server doesn\'t have a welcome message.')

    async def on_member_join(self, member):
        guild = str(member.guild.id)
        await asyncio.sleep(2)
        if self.disabled:
            return
        if not self.check_for_guild(guild):
            return
        channel = self.liara.get_channel(int(self.welcome[guild]['channel']))
        if channel is None:
            self.welcome.pop(guild)
            return
        permissions = channel.permissions_for(member.guild.me)
        message = self.welcome[guild]['message'].replace('%m', member.mention).replace('%n', member.name)
        if not permissions.send_messages:
            self.welcome.pop(guild)
            return
        elif not permissions.embed_links:
            await self.liara.send_message(channel, message)
        else:
            embed = discord.Embed()
            embed.set_author(name=str(member), icon_url=member.avatar_url)
            embed.description = message
            await channel.send(embed=embed)


def setup(liara):
    liara.add_cog(Welcome(liara))
