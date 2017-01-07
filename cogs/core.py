from cogs.utils.dataIO import dataIO
from cogs.utils import checks
from discord.ext import commands
from discord.ext.commands import errors as commands_errors
import importlib
import traceback
import inspect
import os
import datetime
import aiohttp
import discord.errors
import asyncio
import random
import json


class Core:
    def __init__(self, liara):
        self.liara = liara
        self.settings = dataIO.load_json('settings')
        self.ignore_db = False
        self.logger = self.liara.logger
        self.liara.loop.create_task(self.post())

    def __unload(self):
        self.settings.die = True
        self.loop.cancel()

    async def post(self):
        """Power-on self test. Beep boop."""
        if 'prefixes' in self.settings:
            self.liara.command_prefix = self.settings['prefixes']
            self.logger.info('Liara\'s prefixes are: ' + ', '.join(self.liara.command_prefix))
        else:
            prefix = random.randint(1, 2**8)
            self.liara.command_prefix = self.settings['prefixes'] = [str(prefix)]
            self.logger.info('Liara hasn\'t been started before, so her prefix has been set to "{0}".'.format(prefix))

        if 'cogs' in self.settings:
            for cog in self.settings['cogs']:
                if cog not in list(self.liara.extensions):
                    try:
                        self.liara.load_extension(cog)
                    except ImportError:
                        self.settings['cogs'].remove(cog)
                        self.logger.warn('{0} could not be loaded. This message will not be shown again.'.format(cog))
        else:
            self.settings['cogs'] = ['cogs.core']
        if 'roles' not in self.settings:
            self.settings['roles'] = {}
        if 'ignores' not in self.settings:
            self.settings['ignores'] = {}
        # noinspection PyAttributeOutsideInit
        self.loop = self.liara.loop.create_task(self.maintenance_loop())  # starts the loop

    async def maintenance_loop(self):
        while True:
            if not self.ignore_db:  # if you wanna use something else for database management, just set this to false
                # Loading cogs
                for cog in self.settings['cogs']:
                    if cog not in list(self.liara.extensions):
                        try:
                            self.liara.load_extension(cog)
                        except ImportError:
                            self.settings['cogs'].remove(cog)  # something went wrong here
                            self.logger.warn('{0} could not be loaded. This message will not be shown again.'
                                             .format(cog))
                # Unloading cogs
                for cog in list(self.liara.extensions):
                    if cog not in self.settings['cogs']:
                        self.liara.unload_extension(cog)
                # Prefix changing
                self.liara.command_prefix = self.settings['prefixes']
                # Setting owner
                if 'owners' not in self.settings:
                    self.settings['owners'] = []
                try:
                    if self.liara.owner.id not in self.settings['owners']:
                        self.settings['owners'].append(self.liara.owner.id)
                except AttributeError:
                    pass
                self.liara.owners = self.settings['owners']
            await asyncio.sleep(1)

    async def create_gist(self, content, filename='output.py'):
        github_file = {'files': {filename: {'content': str(content)}}}
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.github.com/gists', data=json.dumps(github_file)) as response:
                return await response.json()

    async def on_message(self, message):
        if not self.liara.lockdown:
            if message.author.id in self.liara.owners:  # *always* process owner and server owner commands
                await self.liara.process_commands(message)
                return
            if isinstance(message.author, discord.Member):
                if message.server.owner == message.author:
                    await self.liara.process_commands(message)
                    return
                try:
                    roles = [x.name.lower() for x in message.author.roles]
                    if self.liara.settings['roles'][message.server.id]['admin_role'].lower() in roles:
                        await self.liara.process_commands(message)
                        return
                except KeyError or AttributeError:
                    pass
                if message.server.id in self.settings['ignores']:
                    if self.settings['ignores'][message.server.id]['server_ignore']:
                        return
                    if message.channel.id in self.settings['ignores'][message.server.id]['ignored_channels']:
                        return
            await self.liara.process_commands(message)

    async def on_command_error(self, exception, context):
        if isinstance(exception, commands_errors.MissingRequiredArgument):
            await self.liara.send_cmd_help(context)
        elif isinstance(exception, commands_errors.CommandInvokeError):
            exception = exception.original
            _traceback = traceback.format_tb(exception.__traceback__)
            _traceback = ''.join(_traceback)
            error = '`{0}` in command `{1}`: ```py\n{2}```'\
                .format(type(exception).__name__, context.command.qualified_name, _traceback)
            await self.liara.send_message(context.message.channel, error)
        elif isinstance(exception, commands_errors.CommandNotFound):
            pass

    @commands.group(name='set', pass_context=True, invoke_without_command=True)
    @checks.admin_or_permissions()
    async def set_cmd(self, ctx):
        """Sets Liara's settings."""
        await self.liara.send_cmd_help(ctx)

    @set_cmd.command(pass_context=True)
    @checks.is_owner()
    async def prefix(self, ctx, *prefixes: str):
        """Sets Liara's prefixes."""
        prefixes = list(prefixes)

        if not prefixes:
            await self.liara.send_cmd_help(ctx)
            return

        self.liara.command_prefix = prefixes
        self.settings['prefixes'] = prefixes
        await self.liara.say('Prefix(es) set.')

    @set_cmd.command()
    @checks.is_owner()
    async def name(self, username: str):
        """Changes Liara's username."""
        await self.liara.edit_profile(username=username)
        await self.liara.say('Username changed. Please call me {0} from now on.'.format(username))

    @set_cmd.command()
    @checks.is_owner()
    async def avatar(self, url: str):
        """Changes Liara's avatar."""
        session = aiohttp.ClientSession()
        response = await session.get(url)
        avatar = await response.read()
        response.close()
        await session.close()
        try:
            await self.liara.edit_profile(avatar=avatar)
            await self.liara.say('Avatar changed.')
        except discord.errors.InvalidArgument:
            await self.liara.say('That image type is unsupported.')

    @set_cmd.command()
    @checks.is_owner()
    @checks.is_bot_account()
    async def owner(self, *owners: discord.User):
        """Sets Liara's owners."""
        self.settings['owners'] = [x.id for x in list(owners)]
        if len(list(owners)) == 1:
            await self.liara.say('Owner set.')
        else:
            await self.liara.say('Owners set.')

    @set_cmd.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions()
    @checks.is_bot_account()
    async def admin(self, ctx, role: str=None):
        """Sets Liara's admin role.
        Roles are non-case sensitive."""
        server = ctx.message.server.id
        if server not in self.settings['roles']:
            self.settings['roles'][server] = {}
        if role is not None:
            self.settings['roles'][server]['admin_role'] = role
            await self.liara.say('Admin role set to `{0}` successfully.'.format(role))
        else:
            if 'admin_role' in self.settings['roles'][server]:
                self.settings['roles'][server].pop('admin_role')
            await self.liara.say('Admin role cleared.\n'
                                 'If you didn\'t intend to do this, use `{0}help set admin` for help.'
                                 .format(ctx.prefix))

    @set_cmd.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions()
    @checks.is_bot_account()
    async def moderator(self, ctx, role: str=None):
        """Sets Liara's moderator role.
        Roles are non-case sensitive."""
        server = ctx.message.server.id
        if server not in self.settings['roles']:
            self.settings['roles'][server] = {}
        if role is not None:
            self.settings['roles'][server]['mod_role'] = role
            await self.liara.say('Moderator role set to `{0}` successfully.'.format(role))
        else:
            if 'mod_role' in self.settings['roles'][server]:
                self.settings['roles'][server].pop('mod_role')
            await self.liara.say('Moderator role cleared.\n'
                                 'If you didn\'t intend to do this, use `{0}help set moderator` for help.'
                                 .format(ctx.prefix))

    def _ignore_check(self, ctx):
        server = ctx.message.server.id
        if server not in self.settings['ignores']:
            self.settings['ignores'][server] = {'server_ignore': False, 'ignored_channels': []}

    @set_cmd.group(name='ignore', pass_context=True, invoke_without_command=True)
    @checks.admin_or_permissions()
    @checks.is_bot_account()
    async def ignore_cmd(self, ctx):
        """Helps you ignore/unignore servers/channels."""
        await self.liara.send_cmd_help(ctx)

    @ignore_cmd.command(pass_context=True)
    @checks.admin_or_permissions()
    @checks.is_bot_account()
    async def channel(self, ctx, state: bool):
        """Ignores/unignores the current channel."""
        self._ignore_check(ctx)
        channel = ctx.message.channel.id
        server = ctx.message.server.id
        if state:
            if channel not in self.settings['ignores'][server]['ignored_channels']:
                self.settings['ignores'][server]['ignored_channels'].append(channel)
            await self.liara.say('Channel ignored.')
        else:
            if channel in self.settings['ignores'][server]['ignored_channels']:
                self.settings['ignores'][server]['ignored_channels'].remove(channel)
            await self.liara.say('Channel unignored.')

    @ignore_cmd.command(pass_context=True)
    @checks.admin_or_permissions()
    @checks.is_bot_account()
    async def server(self, ctx, state: bool):
        """Ignores/unignores the current server."""
        self._ignore_check(ctx)
        server = ctx.message.server.id
        if state:
            self.settings['ignores'][server]['server_ignore'] = True
            await self.liara.say('Server ignored.')
        else:
            self.settings['ignores'][server]['server_ignore'] = False
            await self.liara.say('Server unignored.')

    @commands.command(aliases=['shutdown'])
    @checks.is_owner()
    async def halt(self):
        """Shuts Liara down."""
        await self.liara.say(':wave:')
        await self.liara.logout()

    @commands.command()
    @checks.is_owner()
    async def load(self, name: str):
        """Loads a cog."""
        cog_name = 'cogs.{0}'.format(name)
        if cog_name not in list(self.liara.extensions):
            try:
                cog = importlib.import_module(cog_name)
                importlib.reload(cog)
                self.liara.load_extension(cog.__name__)
                self.settings['cogs'].append(cog_name)
                await self.liara.say('`{0}` loaded successfully.'.format(name))
            except Exception as e:
                _traceback = traceback.format_tb(e.__traceback__)
                _traceback = ''.join(_traceback[2:])
                await self.liara.say('Unable to load; the cog caused a `{0}`:\n```py\n{1}\n```'
                                     .format(type(e).__name__, _traceback))
        else:
            await self.liara.say('Unable to load; that cog is already loaded.')

    @commands.command()
    @checks.is_owner()
    async def unload(self, name: str):
        """Unloads a cog."""
        if name == 'core':
            await self.liara.say('Sorry, I can\'t let you do that. '
                                 'If you want to install a custom loader, look into the documentation.')
            return
        cog_name = 'cogs.{0}'.format(name)
        if cog_name in list(self.liara.extensions):
            self.liara.unload_extension(cog_name)
            self.settings['cogs'].remove(cog_name)
            await self.liara.say('`{0}` unloaded successfully.'.format(name))
        else:
            await self.liara.say('Unable to unload; that cog isn\'t loaded.')

    @commands.command()
    @checks.is_owner()
    async def reload(self, name: str):
        """Reloads a cog."""
        cog_name = 'cogs.{0}'.format(name)
        if cog_name in list(self.liara.extensions):
            cog = importlib.import_module(cog_name)
            importlib.reload(cog)
            self.liara.unload_extension(cog_name)
            self.liara.load_extension(cog_name)
            await self.liara.say('`{0}` reloaded successfully.\nLast modified at: `{1}`'
                                 .format(name, datetime.datetime.fromtimestamp(os.path.getmtime(cog.__file__))))
        else:
            await self.liara.say('Unable to reload, that cog isn\'t loaded.')

    # noinspection PyUnusedLocal
    @commands.command(pass_context=True, hidden=True, aliases=['debug'])
    @checks.is_owner()
    async def eval(self, ctx, *, code: str):
        """Evaluates Python code."""
        message = ctx.message
        author = ctx.message.author
        channel = ctx.message.channel
        server = ctx.message.server
        client = ctx.bot
        bot = ctx.bot

        output = eval(code)
        if inspect.isawaitable(output):
            output = await output

        try:
            await self.liara.say('```py\n{0}\n```'.format(output))
        except discord.HTTPException:
            gist = await self.create_gist(output)
            await self.liara.say('Sorry, that output was too large, so I uploaded it to gist instead.\n'
                                 '{0}'.format(gist['html_url']))


def setup(liara):
    liara.add_cog(Core(liara))
