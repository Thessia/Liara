import datetime

import discord
from discord.ext import commands

from cogs.utils import checks


class MemberIDConverter(commands.MemberConverter):
    async def convert(self, ctx, argument):
        try:
            return await super().convert(ctx, argument)
        except commands.BadArgument:
            try:
                return int(argument)
            except ValueError:
                raise commands.BadArgument()


class Moderation:
    def __init__(self, liara):
        self.liara = liara

    @commands.command()
    @commands.guild_only()
    async def userinfo(self, ctx, user: discord.Member=None):
        """Shows you a user's info.

        Defaults to message author if user is not specified.

        * user: The user of which you want to get the info of

        Arguments marked with * are optional.
        """

        if user is None:
            member = ctx.message.author
        else:
            member = user

        # user-friendly status
        if member.status == discord.Status.online:
            status = '<:online:314049328459022338>'
        elif member.status == discord.Status.idle:
            status = '<:away:314049477218664450>'
        elif member.status == discord.Status.do_not_disturb:
            status = '<:do_not_disturb:314049576850161664>'
        else:
            status = '<:offline:314049612086509568>'

        embed = discord.Embed()
        embed.title = '{} {}'.format(status, member)
        avatar_url = member.avatar_url.replace('webp', 'png')
        embed.description = '**Display name**: {0.display_name}\n**ID**: {0.id}\n[Avatar]({1})'\
                            .format(member, avatar_url)

        if isinstance(member.activity, discord.Game):
            embed.description += '\n**Game**: {}'.format(member.activity)

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

    @commands.command()
    @commands.guild_only()
    async def serverinfo(self, ctx):
        """Shows you the server's info."""
        guild = ctx.guild

        embed = discord.Embed()
        embed.title = str(guild)
        if guild.icon_url is not None:
            embed.description = '**ID**: {0.id}\n[Icon URL]({0.icon_url})'.format(guild)
            embed.set_thumbnail(url=guild.icon_url)
        else:
            embed.description = '**ID**: {0.id}'.format(guild)

        if guild.me.permissions_in(ctx.channel).kick_members and ctx.author.permissions_in(ctx.channel).kick_members:
            dead_members = await ctx.guild.estimate_pruned_members(days=7)
            members = '{} members, {} of which were active in the past 7 days'.format(guild.member_count,
                                                                                      guild.member_count - dead_members)
        else:
            members = guild.member_count

        embed.add_field(name='Members', value=members)

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
            verification_level = 'None'
        elif guild.verification_level == discord.VerificationLevel.low:
            verification_level = 'Low'
        elif guild.verification_level == discord.VerificationLevel.medium:
            verification_level = 'Medium'
        elif guild.verification_level == discord.VerificationLevel.high:
            verification_level = '(╯°□°）╯︵ ┻━┻'
        else:
            verification_level = '┻━┻ ﾐヽ(ಠ益ಠ)ノ彡┻━┻'

        if guild.explicit_content_filter == discord.ContentFilter.disabled:
            explicit_level = 'Don\'t scan any messages'
        elif guild.explicit_content_filter == discord.ContentFilter.no_role:
            explicit_level = 'Scan messages from members without a role'
        else:
            explicit_level = 'Scan messages sent by all members'

        info = '**AFK channel**: {0.afk_channel}\n**AFK timeout**: {0.afk_timeout} seconds\n' \
               '**Owner**: {0.owner.mention}\n**Region**: `{0.region.value}`\n' \
               '**Verification level**: {1}\n**Explicit content filter**: {2}'.format(guild, verification_level,
                                                                                      explicit_level)

        embed.add_field(name='Other miscellaneous info', value=info)

        embed.timestamp = guild.created_at
        embed.set_footer(text='Created on')

        if ctx.channel.permissions_for(ctx.guild.me).embed_links:
            if ctx.author.id == self.liara.user.id:
                await ctx.message.edit(embed=embed)
            else:
                await ctx.send(embed=embed)
        else:
            await ctx.send('Unable to post serverinfo, please allow the Embed Links permission.')

    @commands.command()
    @commands.guild_only()
    @checks.mod_or_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, days_to_clean: int=1, reason: str=None):
        """Bans a member.

        - member: The member to ban
        * days_to_clean: The amount of days of message history from the member to clean
        * reason: The ban reason

        Arguments marked with * are optional.
        """
        if not 0 <= days_to_clean <= 7:
            await ctx.send('Invalid clean value. Use a number from 0 to 7.')
            return

        _reason = 'Initiated by {}'.format(ctx.author)
        if reason is not None:
            _reason += ', for reason "{}"'.format(reason)

        try:
            await member.ban(delete_message_days=days_to_clean, reason=_reason)
            await ctx.send('Done. Good riddance.')
        except discord.Forbidden:
            await ctx.send('Sorry, I don\'t have permission to ban that person here.')

    @commands.command()
    @commands.guild_only()
    @checks.mod_or_permissions(ban_members=True)
    async def hackban(self, ctx, user_id: int):
        """Bans a member by their ID.

        - user_id: The user ID to ban
        """
        try:
            await self.liara.http.ban(str(user_id), str(ctx.guild.id))
            await ctx.send('Done. Good riddance.')
        except discord.NotFound:
            await ctx.send('That user doesn\'t exist.')
        except discord.Forbidden:
            await ctx.send('Sorry, I don\'t have permission to ban that person here.')
        except discord.HTTPException:
            await ctx.send('That ID is invalid.')

    @commands.command()
    @commands.guild_only()
    @checks.mod_or_permissions(kick_members=True)
    async def softban(self, ctx, member: discord.Member, days_to_clean: int=1, reason: str=None):
        """Kicks a member, removing all their messages in the process.

        - member: The member to softban
        * days_to_clean: The amount of days of message history from the member to clean

        Arguments marked with * are optional.
        """
        if not 0 <= days_to_clean <= 7:
            await ctx.send('Invalid clean value. Use a number from 0 to 7.')
            return

        _reason = 'Initiated by {}'.format(ctx.author)
        if reason is not None:
            _reason += ', for reason "{}"'.format(reason)

        try:
            await member.ban(delete_message_days=days_to_clean, reason=_reason)
            await member.unban(reason=_reason)
            await ctx.send('Done. Good riddance.')
        except discord.Forbidden:
            await ctx.send('Sorry, I don\'t have permission to ban that person here.')

    @commands.command()
    @commands.guild_only()
    @checks.mod_or_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, reason: str=None):
        """Kicks a member.

        - member: The member to kick
        * reason: The reason for kicking this user

        Arguments marked with * are optional.
        """

        _reason = 'Initiated by {}'.format(ctx.author)
        if reason is not None:
            _reason += ', for reason "{}"'.format(reason)

        try:
            await member.kick(reason=_reason)
            self.liara.dispatch('kick', member)  # yay for implementing on_kick
            await ctx.send('Done. Good riddance.')
        except discord.Forbidden:
            await ctx.send('Sorry, I don\'t have permission to kick that person here.')

    @commands.command()
    @commands.guild_only()
    @checks.mod_or_permissions(mute_members=True)
    async def voicekick(self, ctx, member: discord.Member, reason: str=None):
        """Kicks a member from voice.

        - member: The member to kick
        * reason: The reason for kicking this user from voice

        Arguments marked with * are optional.
        """
        if not (member.voice is not None and member.voice.channel is not None):
            return await ctx.send('That user is not in a voice channel.')
        overwrite = discord.PermissionOverwrite(connect=False)
        overwrite = {ctx.guild.default_role: overwrite}
        _reason = 'Voice kick initiated by {}'.format(ctx.author)
        if reason is not None:
            _reason += ', for reason "{}"'.format(reason)
        try:
            channel = await ctx.guild.create_voice_channel('Voice Kick', overwrites=overwrite, reason=_reason)
            await member.move_to(channel, reason=_reason)
            await channel.delete(reason=_reason)
            await ctx.send('Done.')
        except discord.Forbidden:
            await ctx.send('Sorry, I don\'t have permission to voice kick that person.')

    @commands.group('clean', aliases=['cleanup', 'purge'], invoke_without_command=True)
    @commands.guild_only()
    @checks.mod_or_permissions(manage_messages=True)
    async def clean_cmd(self, ctx):
        """Message clean up command group."""
        await self.liara.send_command_help(ctx)

    @clean_cmd.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_messages=True)
    async def member(self, ctx, member: MemberIDConverter, limit: int=100, channel: discord.TextChannel=None):
        """Cleans up a member's messages.

        - member: A member or ID to clean up
        * limit: How many messages to scan for the specified member
        * channel: The channel to scan the messages from (defaults to current channel)

        Arguments marked with * are optional.
        """
        if channel is None:
            channel = ctx.channel

        if isinstance(member, discord.Member):
            def predicate(message):
                return message.author == member
        else:
            def predicate(message):
                return message.author.id == member

        # noinspection PyUnresolvedReferences
        messages = await channel.purge(limit=limit, check=predicate)
        messages = len(messages)

        plural = '' if messages == 1 else 's'

        await ctx.send('Purged {} message{}.'.format(messages, plural), delete_after=10)

    @clean_cmd.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_messages=True)
    async def channel(self, ctx, limit: int=100, channel: discord.TextChannel=None):
        """Cleans up the specified channel.

        * limit: How many messages to clean up
        * channel: The channel to delete the messages from (defaults to the current channel)

        Arguments marked with * are optional.
        """

        if channel is None:
            channel = ctx.channel

        # noinspection PyUnresolvedReferences
        messages = await channel.purge(limit=limit)
        messages = len(messages)

        plural = '' if messages == 1 else 's'

        await ctx.send('Purged {} message{}.'.format(messages, plural), delete_after=10)


def setup(liara):
    liara.add_cog(Moderation(liara))
