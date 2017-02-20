from cogs.utils.dataIO import dataIO
from cogs.utils import checks
from raven import Client as SentryClient
from raven.exceptions import InvalidDsn
from discord.ext.commands import errors as commands_errors
from discord.ext import commands


class Sentry:
    """A simple cog for bug reports."""
    def __init__(self, liara):
        self.liara = liara
        self.settings = dataIO.load_json('sentry')
        if 'dsn' not in self.settings:
            self.settings['dsn'] = None
        self.client = SentryClient(site=liara.user.id)

    async def on_command_error(self, exception, context):
        if isinstance(exception, commands_errors.MissingRequiredArgument):
            return
        if isinstance(exception, commands_errors.CommandNotFound):
            return
        if self.settings['dsn'] is None:
            return
        try:
            self.client.set_dsn(self.settings['dsn'])
        except InvalidDsn:
            self.settings['dsn'] = None
            self.client.set_dsn(None)

        self.client.user_context({'id': context.message.author.id})
        _exception = exception.original
        message = context.message
        # noinspection PyBroadException
        try:
            raise _exception
        except:
            self.client.captureException(data={'message': message.content}, extra={'server_id': message.server.id,
                                                                                   'channel_id': message.channel.id,
                                                                                   'message_id': message.id})

    @commands.command()
    @checks.is_owner()
    async def set_sentry(self, dsn=None):
        """Sets the DSN for Sentry."""
        try:
            self.client.set_dsn(dsn)
        except InvalidDsn:
            await self.liara.say('That DSN is invalid.')
            return
        self.settings['dsn'] = dsn
        if dsn is None:
            await self.liara.say('DSN cleared.')
        else:
            await self.liara.say('DSN successfully set! All your exceptions will now be logged to Sentry.')
            self.client.captureMessage('Hello, world!')


def setup(liara):
    liara.add_cog(Sentry(liara))
