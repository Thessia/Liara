from discord.ext import commands
from cogs.utils import checks
import discord
import datetime


class Moderation:
    def __init__(self, liara):
        self.liara = liara

    @commands.command(no_pm=True)
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
            embed.description += '\n**Game**: {}'.format(member.game)

        join_delta = datetime.datetime.utcnow() - member.joined_at
        created_delta = datetime.datetime.utcnow() - member.created_at
        embed.add_field(name='Join Dates', value='**This server**: {} ago ({})\n**Discord**: {} ago ({})'
                        .format(join_delta, member.joined_at, created_delta, member.created_at))

        roles = [x.mention for x in sorted(member.roles, key=lambda role: role.position) if not x.is_default()]
        roles.reverse()  # just so it shows up like it does in the official Discord UI
        if roles:  # only show roles if the member has any
            if len(str(roles)) < 1025:  # deal with limits
                embed.add_field(name='Roles', value=', '.join(roles))
        embed.set_thumbnail(url=avatar_url.replace('size=1024', 'size=256'))

        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            if ctx.author.id == self.liara.user.id:
                await ctx.message.edit(embed=embed)
            else:
                await ctx.send(embed=embed)
        else:
            await ctx.send('Unable to post userinfo, please allow the Embed Links permission.')

    @commands.command(no_pm=True)
    async def serverinfo(self, ctx):
        """Shows you the server's info."""
        guild = ctx.guild

        if guild.large:
            await self.liara.request_offline_members(guild)

        embed = discord.Embed()
        embed.title = str(guild)
        if guild.icon_url is not None:
            embed.description = '**ID**: {0.id}\n[Icon URL]({0.icon_url})'.format(guild)
            embed.set_thumbnail(url=guild.icon_url)
        else:
            embed.description = '**ID**: {0.id}'.format(guild)

        embed.add_field(name='Members', value=str(len(guild.members)))

        roles = [x.mention for x in guild.role_hierarchy if not x.is_default()]
        if roles:  # only show roles if the server has any
            roles = ', '.join(roles)
            if len(roles) <= 1024:  # deal with limits
                embed.add_field(name='Roles', value=roles)

        channels = [x[1] for x in sorted([(x.position, x.mention) for x in guild.channels if
                                          isinstance(x, discord.TextChannel)])]
        channels = ', '.join(channels)
        if len(channels) <= 1024:
            embed.add_field(name='Text channels', value=channels)

        if guild.verification_level == discord.VerificationLevel.none:
            level = 'Off'
        elif guild.verification_level == discord.VerificationLevel.low:
            level = 'Low'
        elif guild.verification_level == discord.VerificationLevel.medium:
            level = 'Medium'
        else:
            level = '(╯°□°）╯︵ ┻━┻'

        embed.add_field(name='Other miscellaneous info', value='**AFK Channel**: {0.afk_channel}\n'
                                                               '**AFK Timeout**: {0.afk_timeout} seconds\n'
                                                               '**Owner**: {0.owner.mention}\n'
                                                               '**Region**: `{0.region.value}`\n'
                                                               '**Verification level**: {1}'.format(guild, level))

        embed.timestamp = guild.created_at
        embed.set_footer(text='Created on')

        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            if ctx.author.id == self.liara.user.id:
                await ctx.message.edit(embed=embed)
            else:
                await ctx.send(embed=embed)
        else:
            await ctx.send('Unable to post serverinfo, please allow the Embed Links permission.')

    @commands.command(no_pm=True)
    @checks.mod_or_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, days_to_clean: int=1):
        """Bans a member."""
        if not 0 <= days_to_clean <= 7:
            await ctx.send('Invalid clean value. Use a number from 0 to 7.')
            return
        try:
            await member.ban(delete_message_days=days_to_clean)
            await ctx.send('Done. Good riddance.')
        except discord.Forbidden:
            await ctx.send('Sorry, I don\'t have permission to ban that person here.')

    @commands.command(no_pm=True)
    @checks.mod_or_permissions(kick_members=True)
    async def softban(self, ctx, member: discord.Member, days_to_clean: int=1):
        """Kicks a member, removing all their messages in the process."""
        if not 0 <= days_to_clean <= 7:
            await ctx.send('Invalid clean value. Use a number from 0 to 7.')
            return
        try:
            await member.ban(delete_message_days=days_to_clean)
            await member.unban()
            await ctx.send('Done. Good riddance.')
        except discord.Forbidden:
            await ctx.send('Sorry, I don\'t have permission to ban that person here.')

    @commands.command(no_pm=True)
    @checks.mod_or_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member):
        """Kicks a member."""
        try:
            await member.kick()
            self.liara.dispatch('kick', member)  # yay for implementing on_kick
            await ctx.send('Done. Good riddance.')
        except discord.Forbidden:
            await ctx.send('Sorry, I don\'t have permission to kick that person here.')

    # @commands.command(no_pm=True)
    # @checks.is_not_bot_account()
    # @checks.is_owner()
    # async def block(self, ctx, member: discord.Member):
    #     """Blocks a member."""
    #     if member.is_blocked():
    #         await ctx.send('That user is already blocked.')
    #         return
    #     await member.block()
    #     await ctx.send('Goodbye, {}.'.format(member.mention))
    #
    # @commands.command(no_pm=True)
    # @checks.is_not_bot_account()
    # @checks.is_owner()
    # async def unblock(self, ctx, member: discord.Member):
    #     """Unblocks a member."""
    #     if not member.is_blocked():
    #         await ctx.send('That user isn\'t blocked.')
    #         return
    #     await member.unblock()
    #     await ctx.send('Welcome back, {}.'.format(member.mention))


def setup(liara):
    liara.add_cog(Moderation(liara))
