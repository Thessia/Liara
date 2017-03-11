from discord.ext import commands
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
import asyncio
import discord


class Welcome:
    def __init__(self, liara):
        self.liara = liara
        self.welcome = dataIO.load_json('pandentia.welcome')
        self.disabled = False

    def __unload(self):
        self.welcome.die = True

    def check_for_server(self, server_id):
        if server_id not in self.welcome:
            self.welcome[server_id] = {'status': False}
        if self.welcome[server_id]['status']:
            return True
        else:
            return False

    @commands.command()
    @checks.mod_or_permissions(administrator=True)
    async def welcomeset(self, ctx, channel, *, message: str):
        """Sets a welcome message for your current server."""
        if not isinstance(channel, discord.TextChannel):
            await self.liara.say('That\'s not a text channel!')
            return
        if len(message) > 750:
            await self.liara.say('That welcome message is too long. Try something under 750 characters.')
            return
        server = str(ctx.message.guild.id)
        self.check_for_server(server)
        self.welcome[server]['status'] = True
        self.welcome[server]['channel'] = str(channel.id)
        self.welcome[server]['message'] = message
        await ctx.send('Welcome message set.')

    @commands.command()
    @checks.mod_or_permissions(administrator=True)
    async def welcomeclear(self, ctx):
        """Clears the server's welcome message."""
        server = str(ctx.message.guild.id)
        if self.check_for_server(server):
            self.welcome.pop(server)
            await self.liara.say('Welcome message cleared.')
        else:
            await self.liara.say('This server doesn\'t have a welcome message.')

    async def on_member_join(self, member):
        server = str(member.guild.id)
        await asyncio.sleep(2)
        if self.disabled:
            return
        if self.check_for_server(server):
            channel = self.liara.get_channel(int(self.welcome[server]['channel']))
            if channel is None:
                self.welcome.pop(server)
                return
            permissions = channel.permissions_for(member.guild.me)
            message = self.welcome[server]['message'].replace('%m', member.mention).replace('%n', member.name)
            if not permissions.send_messages:
                self.welcome.pop(server)
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
