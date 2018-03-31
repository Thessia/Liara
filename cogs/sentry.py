from asyncio import Lock

import discord
from discord.ext import commands
from discord.ext.commands import errors as commands_errors
from raven import Client as SentryClient
from raven.exceptions import InvalidDsn

from cogs.utils import checks
from cogs.utils.storage import RedisCollection


class Sentry:
    """A simple cog for bug reports."""
    def __init__(self, liara):
        self.liara = liara
        self.settings = RedisCollection(liara.redis, 'redis')
        self.client = None
        self.client_lock = Lock(loop=self.liara.loop)

    async def on_command_error(self, context, exception):
        # raven setup
        if self.client is None:
            self.client = SentryClient(site=self.liara.user.id)
        dsn = await self.settings.get('dsn', None)
        if dsn is None:
            return
        try:
            self.client.set_dsn(dsn)
        except InvalidDsn:
            await self.settings.delete('dsn')
            return

        if isinstance(exception, commands_errors.MissingRequiredArgument):
            return
        if isinstance(exception, commands_errors.CommandNotFound):
            return
        if isinstance(exception, commands_errors.BadArgument):
            return

        _exception = exception.original
        if isinstance(_exception, discord.Forbidden):
            return  # not my problem

        message = context.message
        async with self.client_lock:
            self.client.user_context({'id': message.author.id})
            # noinspection PyBroadException
            try:
                raise _exception
            except Exception:
                self.client.captureException(
                    data={'message': message.content},
                    extra={
                        'guild_id': message.guild.id,
                        'channel_id': message.channel.id,
                        'message_id': message.id
                    }
                )

    @commands.command()
    @checks.is_owner()
    async def set_sentry(self, ctx, dsn=None):
        """Sets the DSN for Sentry."""
        if self.client is None:
            self.client = SentryClient(site=self.liara.user.id)
        try:
            self.client.set_dsn(dsn)
        except InvalidDsn:
            await ctx.send('That DSN is invalid.')
            return
        await self.settings.set('dsn', dsn)
        if dsn is None:
            await ctx.send('DSN cleared.')
        else:
            await ctx.send('DSN successfully set! All your exceptions will now be logged to Sentry.')
            self.client.captureMessage('Sentry for Liara successfully set up.')


def setup(liara):
    liara.add_cog(Sentry(liara))
