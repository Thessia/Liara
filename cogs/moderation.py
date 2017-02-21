from discord.ext import commands
from cogs.utils import checks
import discord
import datetime


class Moderation:
    def __init__(self, liara):
        self.liara = liara

    @commands.command(pass_context=True, no_pm=True)
    async def userinfo(self, ctx, user: discord.Member=None):
        """Shows you a user's info.

        Defaults to message author if user is not specified.
        """

        if user is None:
            member = ctx.message.author
        else:
            member = user

        # user-friendly status
        if member.status == discord.Status.online:
            status = '<:online:212789758110334977>'
        elif member.status == discord.Status.idle:
            status = '<:away:212789859071426561>'
        elif member.status == discord.Status.do_not_disturb:
            status = '<:do_not_disturb:236744731088912384>'
        else:
            status = '<:offline:212790005943369728>'

        embed = discord.Embed()
        embed.title = '{} {}'.format(status, member)
        avatar_url = member.avatar_url.replace('webp', 'png')
        embed.description = '**Display name**: {0.display_name}\n**ID**: {0.id}\n[Avatar]({1})'\
                            .format(member, avatar_url)

        if member.game is not None:
            embed.description += '\n**Game**: {}'.format(member.game.name)

        join_delta = datetime.datetime.utcnow() - member.joined_at
        created_delta = datetime.datetime.utcnow() - member.created_at
        embed.add_field(name='Join Dates', value='**This server**: {} ago ({})\n**Discord**: {} ago ({})'
                        .format(join_delta, member.joined_at, created_delta, member.created_at))

        roles = [x.mention for x in sorted(member.roles, key=lambda role: role.position) if not x.is_everyone]
        roles.reverse()  # just so it shows up like it does in the official Discord UI
        if roles:  # only show roles if the member has any
            if len(str(roles)) < 1025:  # deal with limits
                embed.add_field(name='Roles', value=', '.join(roles))
        embed.set_thumbnail(url=avatar_url.replace('size=1024', 'size=256'))
        try:
            await self.liara.say(embed=embed)
        except discord.HTTPException:
            await self.liara.say('Unable to post userinfo, please allow the Embed Links permission')

    @commands.command(pass_context=True, no_pm=True)
    async def serverinfo(self, ctx):
        """Shows you the server's info."""
        server = ctx.message.server

        if server.large:
            await self.liara.request_offline_members(server)

        embed = discord.Embed()
        embed.title = str(server)
        if server.icon_url is not None:
            embed.description = '**ID**: {0.id}\n[Icon URL]({0.icon_url})'.format(server)
            embed.set_thumbnail(url=server.icon_url)
        else:
            embed.description = '**ID**: {0.id}'.format(server)

        embed.add_field(name='Members', value=str(len(server.members)))

        roles = [x.mention for x in server.role_hierarchy if not x.is_everyone]
        if roles:  # only show roles if the server has any
            if len(str(roles)) < 1025:  # deal with limits
                embed.add_field(name='Roles', value=', '.join(roles))

        channels = [x[1] for x in sorted([(x.position, x.mention) for x in server.channels if x.type ==
                    discord.ChannelType.text])]
        if len(str(channels)) < 1025:
            embed.add_field(name='Text channels', value=', '.join(channels))

        if server.verification_level == discord.VerificationLevel.none:
            level = 'Off'
        elif server.verification_level == discord.VerificationLevel.low:
            level = 'Low'
        elif server.verification_level == discord.VerificationLevel.medium:
            level = 'Medium'
        else:
            level = '(╯°□°）╯︵ ┻━┻'

        embed.add_field(name='Other miscellaneous info', value='**AFK Channel**: {0.afk_channel}\n'
                                                               '**AFK Timeout**: {0.afk_timeout} seconds\n'
                                                               '**Owner**: {0.owner.mention}\n'
                                                               '**Verification level**: {1}'.format(server, level))

        embed.timestamp = server.created_at
        embed.set_footer(text='Created on')

        try:
            await self.liara.say(embed=embed)
        except discord.HTTPException:
            await self.liara.say('Unable to post serverinfo, please allow the Embed Links permission')

    @commands.command(no_pm=True)
    @checks.mod_or_permissions(ban_members=True)
    async def ban(self, member: discord.Member):
        """Bans a member."""
        try:
            await self.liara.ban(member)
            await self.liara.say('Done. Good riddance.')
        except discord.Forbidden:
            await self.liara.say('Sorry, I don\'t have permission to ban that person here.')

    @commands.command(no_pm=True)
    @checks.mod_or_permissions(kick_members=True)
    async def softban(self, member: discord.Member, days_to_clean: int=1):
        """Kicks a member, removing all their messages in the process."""
        if not 0 <= days_to_clean <= 7:
            await self.liara.say('Invalid clean value. Use a number from 0 to 7 (days).')
            return
        try:
            await self.liara.ban(member, days_to_clean)
            await self.liara.unban(member)
            await self.liara.say('Done. Good riddance.')
        except discord.Forbidden:
            await self.liara.say('Sorry, I don\'t have permission to ban that person here.')

    @commands.command(no_pm=True)
    @checks.mod_or_permissions(kick_members=True)
    async def kick(self, member: discord.Member):
        """Kicks a member."""
        try:
            await self.liara.ban(member)
            await self.liara.unban(member)
            await self.liara.say('Done. Good riddance.')
        except discord.Forbidden:
            await self.liara.say('Sorry, I don\'t have permission to kick that person here.')


def setup(liara):
    liara.add_cog(Moderation(liara))
