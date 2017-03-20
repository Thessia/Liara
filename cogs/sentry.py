from cogs.utils import dataIO
from cogs.utils import checks
from raven import Client as SentryClient
from raven.exceptions import InvalidDsn
from discord.ext.commands import errors as commands_errors
from discord.ext import commands


class Sentry:
    """A simple cog for bug reports."""
    def __init__(self, liara):
        self.liara = liara
        self.settings = dataIO.load('sentry')
        if 'dsn' not in self.settings:
            self.settings['dsn'] = None
        self.client = None

    async def on_command_error(self, exception, context):
        if self.client is None:
            self.client = SentryClient(site=self.liara.user.id)
        if isinstance(exception, commands_errors.MissingRequiredArgument):
            return
        if isinstance(exception, commands_errors.CommandNotFound):
            return
        if isinstance(exception, commands_errors.BadArgument):
            return
        if self.settings['dsn'] is None:
            return
        if context.command is self.liara.get_command('eval'):
            return
        try:
            self.client.set_dsn(self.settings['dsn'])
        except InvalidDsn:
            self.settings['dsn'] = None
            self.client.set_dsn(None)

        _exception = exception.original
        message = context.message
        self.client.user_context({'id': message.author.id})
        # noinspection PyBroadException
        try:
            raise _exception
        except:
            self.client.captureException(data={'message': message.content}, extra={'guild_id': message.guild.id,
                                                                                   'channel_id': message.channel.id,
                                                                                   'message_id': message.id})

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
        self.settings['dsn'] = dsn
        if dsn is None:
            await ctx.send('DSN cleared.')
        else:
            await ctx.send('DSN successfully set! All your exceptions will now be logged to Sentry.')
            self.client.captureMessage('Hello, world!')


def setup(liara):
    liara.add_cog(Sentry(liara))
