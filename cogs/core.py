import asyncio
import datetime
import importlib
import inspect
import json
import random
import sys
import textwrap
import time
import traceback
import types

import aiohttp
import discord
from discord.ext import commands
from discord.ext.commands import errors as commands_errors

from cogs.utils import checks
from cogs.utils import dataIO


class Core:
    def __init__(self, liara):
        self.liara = liara
        self.settings = dataIO.load('settings')
        self.ignore_db = False
        self.logger = self.liara.logger
        self.liara.loop.create_task(self.post())
        self.global_preconditions = [self.ignore_preconditions]  # preconditions to message processing
        self.global_preconditions_overrides = [self.ignore_overrides]  # overrides to the preconditions
        self._eval = {}
        self.loop = None  # make pycharm stop complaining

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
                    # noinspection PyBroadException
                    try:
                        self.load_cog(cog)
                    except:
                        self.settings['cogs'].remove(cog)
                        self.logger.warning('{0} could not be loaded. This message will not be shown again.'
                                            .format(cog))
        else:
            self.settings['cogs'] = ['cogs.core']
        if 'roles' not in self.settings:
            self.settings['roles'] = {}
        if 'ignores' not in self.settings:
            self.settings['ignores'] = {}
        await self.liara.wait_until_ready()
        self.loop = self.liara.loop.create_task(self.maintenance_loop())  # starts the loop

    async def maintenance_loop(self):
        while True:
            if not self.ignore_db:  # if you wanna use something else for database management, just set this to false
                # Loading cogs
                for cog in self.settings['cogs']:
                    if cog not in list(self.liara.extensions):
                        # noinspection PyBroadException
                        try:
                            self.load_cog(cog)
                        except:
                            self.settings['cogs'].remove(cog)  # something went wrong here
                            self.logger.warning('{0} could not be loaded. This message will not be shown again.'
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
                    if str(self.liara.owner.id) not in self.settings['owners']:
                        self.settings['owners'].append(str(self.liara.owner.id))
                except AttributeError:
                    pass
                self.liara.owners = self.settings['owners']
            await asyncio.sleep(1)

    async def ignore_overrides(self, message):
        if isinstance(message.author, discord.Member):
            if message.guild.owner == message.author:
                return True
            guild = str(message.guild.id)
            try:
                roles = [x.name.lower() for x in message.author.roles]
                if self.liara.settings['roles'][guild]['admin_role'].lower() in roles:
                    return True
            except KeyError or AttributeError:
                pass

    async def ignore_preconditions(self, message):
        if isinstance(message.author, discord.Member):
            guild = str(message.guild.id)
            if guild in self.settings['ignores']:
                if self.settings['ignores'][guild]['server_ignore']:
                    return False
                if str(message.channel.id) in self.settings['ignores'][guild]['ignored_channels']:
                    return False

    @staticmethod
    async def create_gist(content, filename='output.py'):
        github_file = {'files': {filename: {'content': str(content)}}}
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.github.com/gists', data=json.dumps(github_file)) as response:
                return await response.json()

    # make IDEA stop acting like a baby
    # noinspection PyShadowingBuiltins,PyUnresolvedReferences
    def load_cog(self, name):
        if name in self.liara.extensions:
            return

        redis_name = 'cogfiles.{}'.format(name)

        try:
            if self.liara.shard_id is None or self.liara.shard_id == 0:
                module = importlib.import_module(name)
                importlib.reload(module)
                del sys.modules[name]
                if hasattr(module, '__file__'):
                    path = module.__file__
                    with open(path, 'rb') as f:
                        self.liara.redis.set('cogfiles.{}'.format(name), f.read())
                else:
                    raise discord.ClientException('Extension is not a file')
                del module
        except ImportError:
            assert self.liara.redis.exists(redis_name), 'Module not found on disk or in Redis'

        file_contents = self.liara.redis.get(redis_name)
        if file_contents is None:
            raise IOError('Redis appears to be improperly configured')
        module = types.ModuleType(name)
        exec(file_contents, module.__dict__)

        if not hasattr(module, 'setup'):
            del module
            raise discord.ClientException('Extension does not have a setup function')

        module.setup(self.liara)
        self.liara.extensions[name] = module
        if name not in self.settings['cogs']:
            self.settings['cogs'].append(name)
        sys.modules[name] = module

    async def on_message(self, message):
        if self.liara.lockdown:
            return
        if str(message.author.id) in self.liara.owners:  # *always* process owner commands
            await self.liara.process_commands(message)
            return
        # Overrides start here (yay)
        for override in self.global_preconditions_overrides:
            # noinspection PyBroadException
            try:
                out = override(message)
                if inspect.isawaitable(out):
                    out = await out
                if out is True:
                    await self.liara.process_commands(message)
                    return
            except:
                self.logger.warning('Removed precondition override "{0}", it was malfunctioning.'
                                    .format(override.__name__))
                self.global_preconditions_overrides.remove(override)
        # Preconditions
        for precondition in self.global_preconditions:
            # noinspection PyBroadException
            try:
                out = precondition(message)
                if inspect.isawaitable(out):
                    out = await out
                if out is False:
                    return
            except:
                self.logger.warning('Removed precondition "{0}", it was malfunctioning.'
                                    .format(precondition.__name__))
                self.global_preconditions.remove(precondition)

        await self.liara.process_commands(message)

    async def on_command_error(self, context, exception):
        if isinstance(exception, commands_errors.MissingRequiredArgument):
            await self.liara.send_command_help(context)
        elif isinstance(exception, commands_errors.BadArgument):
            await context.send('Bad argument.')
            await self.liara.send_command_help(context)
        elif isinstance(exception, commands_errors.CommandInvokeError):
            exception = exception.original
            _traceback = traceback.format_tb(exception.__traceback__)
            _traceback = ''.join(_traceback)
            error = '`{0}` in command `{1}`: ```py\nTraceback (most recent call last):\n{2}{0}: {3}\n```'\
                .format(type(exception).__name__, context.command.qualified_name, _traceback, exception)
            await context.send(error)
        elif isinstance(exception, commands_errors.CommandNotFound):
            pass

    async def on_liara_pubsub_receive(self, data):
        if self.liara.shard_id != 0:
            return
        if data.get('type') != 'cog-load':
            return
        self.load_cog(data['cog'])

    @commands.group(name='set', invoke_without_command=True)
    @checks.admin_or_permissions()
    async def set_cmd(self, ctx):
        """Sets Liara's settings."""
        await self.liara.send_command_help(ctx)

    @set_cmd.command()
    @checks.is_owner()
    async def prefix(self, ctx, *prefixes: str):
        """Sets Liara's prefixes.

        - prefixes: A list of prefixes to use
        """
        prefixes = list(prefixes)

        if not prefixes:
            await self.liara.send_command_help(ctx)
            return

        self.liara.command_prefix = prefixes
        self.settings['prefixes'] = prefixes
        await ctx.send('Prefix(es) set.')

    @set_cmd.command()
    @checks.is_owner()
    async def name(self, ctx, username: str):
        """Changes Liara's username.

        - username: The username to use
        """
        await self.liara.user.edit(username=username)
        await ctx.send('Username changed. Please call me {0} from now on.'.format(username))

    @set_cmd.command()
    @checks.is_owner()
    async def avatar(self, ctx, url: str):
        """Changes Liara's avatar.

        - url: The URL to set Liara's avatar to
        """
        session = aiohttp.ClientSession()
        response = await session.get(url)
        avatar = await response.read()
        response.close()
        await session.close()
        try:
            await self.liara.user.edit(avatar=avatar)
            await ctx.send('Avatar changed.')
        except discord.errors.InvalidArgument:
            await ctx.send('That image type is unsupported.')

    # noinspection PyTypeChecker
    @set_cmd.command()
    @checks.is_owner()
    @checks.is_not_selfbot()
    async def owner(self, ctx, *owners: discord.Member):
        """Sets Liara's owners.

        - owners: A list of owners to use
        """
        self.settings['owners'] = [str(x.id) for x in list(owners)]
        if len(list(owners)) == 1:
            await ctx.send('Owner set.')
        else:
            await ctx.send('Owners set.')

    @set_cmd.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.is_not_selfbot()
    async def admin(self, ctx, *, role: str=None):
        """Sets Liara's admin role.
        Roles are non-case sensitive.

        - role: The name of the role to use as the admin role
        """
        server = str(ctx.message.guild.id)
        if server not in self.settings['roles']:
            self.settings['roles'][server] = {}
        if role is not None:
            self.settings['roles'][server]['admin_role'] = role
            await ctx.send('Admin role set to `{0}` successfully.'.format(role))
        else:
            if 'admin_role' in self.settings['roles'][server]:
                self.settings['roles'][server].pop('admin_role')
            await ctx.send('Admin role cleared.\n'
                           'If you didn\'t intend to do this, use `{0}help set admin` for help.'
                           .format(ctx.prefix))

    @set_cmd.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.is_not_selfbot()
    async def moderator(self, ctx, *, role: str=None):
        """Sets Liara's moderator role.
        Roles are non-case sensitive.

        - role: The name of the role to use as the moderator role
        """
        server = str(ctx.message.guild.id)
        if server not in self.settings['roles']:
            self.settings['roles'][server] = {}
        if role is not None:
            self.settings['roles'][server]['mod_role'] = role
            await ctx.send('Moderator role set to `{0}` successfully.'.format(role))
        else:
            if 'mod_role' in self.settings['roles'][server]:
                self.settings['roles'][server].pop('mod_role')
            await ctx.send('Moderator role cleared.\n'
                           'If you didn\'t intend to do this, use `{0}help set moderator` for help.'
                           .format(ctx.prefix))

    def _ignore_check(self, ctx):
        server = str(ctx.message.guild.id)
        if server not in self.settings['ignores']:
            self.settings['ignores'][server] = {'server_ignore': False, 'ignored_channels': []}

    @set_cmd.group(name='ignore', invoke_without_command=True)
    @checks.admin_or_permissions()
    @checks.is_not_selfbot()
    async def ignore_cmd(self, ctx):
        """Helps you ignore/unignore servers/channels."""
        await self.liara.send_command_help(ctx)

    @ignore_cmd.command()
    @checks.admin_or_permissions()
    @checks.is_not_selfbot()
    async def channel(self, ctx, state: bool):
        """Ignores/unignores the current channel.

        - state: Whether or not to ignore the current channel
        """
        self._ignore_check(ctx)
        channel = str(ctx.message.channel.id)
        server = str(ctx.message.guild.id)
        if state:
            if channel not in self.settings['ignores'][server]['ignored_channels']:
                self.settings['ignores'][server]['ignored_channels'].append(channel)
            await ctx.send('Channel ignored.')
        else:
            if channel in self.settings['ignores'][server]['ignored_channels']:
                self.settings['ignores'][server]['ignored_channels'].remove(channel)
            await ctx.send('Channel unignored.')

    @ignore_cmd.command()
    @checks.admin_or_permissions()
    @checks.is_not_selfbot()
    async def server(self, ctx, state: bool):
        """Ignores/unignores the current server.

        - state: Whether or not to ignore the current server
        """
        self._ignore_check(ctx)
        server = str(ctx.message.guild.id)
        if state:
            self.settings['ignores'][server]['server_ignore'] = True
            await ctx.send('Server ignored.')
        else:
            self.settings['ignores'][server]['server_ignore'] = False
            await ctx.send('Server unignored.')

    @commands.command(aliases=['shutdown'])
    @checks.is_owner()
    async def halt(self, ctx, skip_confirm=False):
        """Shuts Liara down.

        - skip_confirm: Whether or not to skip halt confirmation.
        """
        if not skip_confirm:
            def check(_msg):
                if _msg.author == ctx.message.author and _msg.channel == ctx.message.channel and _msg.content:
                    return True
                else:
                    return False
            await ctx.send('Are you sure? I have been up since {}.'.format(datetime.datetime.fromtimestamp
                                                                           (self.liara.boot_time)))
            message = await self.liara.wait_for('message', check=check)
            if message.content.lower() not in ['yes', 'yep', 'i\'m sure']:
                return await ctx.send('Halt aborted.')
        await ctx.send(':wave:')
        self.ignore_db = True
        for cog in list(self.liara.extensions):
            self.liara.unload_extension(cog)
        await asyncio.sleep(2)  # to let some functions clean up their mess
        await self.liara.logout()

    @commands.command()
    @checks.is_owner()
    async def load(self, ctx, name: str):
        """Loads a cog.

        - name: The name of the cog to load
        """
        cog_name = 'cogs.{0}'.format(name)
        if cog_name not in list(self.liara.extensions):
            if self.liara.shard_id == 0 or self.liara.shard_id is None:
                try:
                    self.load_cog(cog_name)
                    await ctx.send('`{0}` loaded successfully.'.format(name))
                except Exception as e:
                    _traceback = traceback.format_tb(e.__traceback__)
                    _traceback = ''.join(_traceback[2:])
                    await ctx.send('Unable to load; the cog caused a `{0}`:\n```py\nTraceback '
                                   '(most recent call last):\n{1}{0}: {2}\n```'
                                   .format(type(e).__name__, _traceback, e))
            else:
                msg = 'Dispatching command to the root shard...'
                message = await ctx.send(msg)
                self.liara.publish({'type': 'cog-load', 'cog': 'cogs.moderation'})
                msg += ' Done!\nThe cog should be loaded on this shard momentarily.'
                await message.edit(content=msg)
        else:
            await ctx.send('Unable to load; that cog is already loaded.')

    @commands.command()
    @checks.is_owner()
    async def unload(self, ctx, name: str):
        """Unloads a cog.

        - name: The name of the cog to unload
        """
        if name == 'core':
            await ctx.send('Sorry, I can\'t let you do that. '
                           'If you want to install a custom loader, look into the documentation.')
            return
        cog_name = 'cogs.{0}'.format(name)
        if cog_name in list(self.liara.extensions):
            self.liara.unload_extension(cog_name)
            self.settings['cogs'].remove(cog_name)
            await ctx.send('`{0}` unloaded successfully.'.format(name))
        else:
            await ctx.send('Unable to unload; that cog isn\'t loaded.')

    @commands.command()
    @checks.is_owner()
    @checks.is_main_shard()
    async def reload(self, ctx, name: str):
        """Reloads a cog."""
        cog_name = 'cogs.{}'.format(name)
        if cog_name in list(self.liara.extensions):
            msg = await ctx.send('`{}` reloading...'.format(name))
            self.liara.unload_extension(cog_name)
            self.load_cog(cog_name)
            await asyncio.sleep(2)
            if cog_name in list(self.liara.extensions):
                await msg.edit(content='`{}` reloaded successfully.'.format(name))
            else:
                await msg.edit(content='`{}` reloaded unsuccessfully. Check your logs for more details.'.format(name))
        else:
            await ctx.send('Unable to reload, that cog isn\'t loaded.')

    @commands.command(hidden=True, aliases=['debug'])
    @checks.is_owner()
    async def eval(self, ctx, *, code: str):
        """Evaluates Python code

        - code: The Python code to run
        """
        if self._eval.get('env') is None:
            self._eval['env'] = {}
        if self._eval.get('count') is None:
            self._eval['count'] = 0

        self._eval['env'].update({
            'bot': self.liara,
            'client': self.liara,
            'liara': self.liara,
            'ctx': ctx,
            'message': ctx.message,
            'channel': ctx.message.channel,
            'guild': ctx.message.guild,
            'author': ctx.message.author,
        })

        # let's make this safe to work with
        code = code.replace('```py\n', '').replace('```', '').replace('`', '')

        _code = 'async def func(self):\n  try:\n{}\n  finally:\n    self._eval[\'env\'].update(locals())'\
            .format(textwrap.indent(code, '    '))

        before = time.monotonic()
        # noinspection PyBroadException
        try:
            exec(_code, self._eval['env'])

            func = self._eval['env']['func']
            output = await func(self)

            if output is not None:
                output = repr(output)
        except Exception as e:
            output = '{}: {}'.format(type(e).__name__, e)
        after = time.monotonic()
        self._eval['count'] += 1
        count = self._eval['count']

        code = code.split('\n')
        if len(code) == 1:
            _in = 'In [{}]: {}'.format(count, code[0])
        else:
            _first_line = code[0]
            _rest = code[1:]
            _rest = '\n'.join(_rest)
            _countlen = len(str(count)) + 2
            _rest = textwrap.indent(_rest, '...: ')
            _rest = textwrap.indent(_rest, ' ' * _countlen)
            _in = 'In [{}]: {}\n{}'.format(count, _first_line, _rest)

        message = '```py\n{}'.format(_in)
        if output is not None:
            message += '\nOut[{}]: {}'.format(count, output)
        ms = int(round((after - before) * 1000))
        if ms > 100:  # noticeable delay
            message += '\n# {} ms\n```'.format(ms)
        else:
            message += '\n```'

        try:
            if ctx.author.id == self.liara.user.id:
                await ctx.message.edit(content=message)
            else:
                await ctx.send(message)
        except discord.HTTPException:
            await ctx.trigger_typing()
            gist = await self.create_gist(message, filename='message.md')
            await ctx.send('Sorry, that output was too large, so I uploaded it to gist instead.\n'
                           '{0}'.format(gist['html_url']))


def setup(liara):
    liara.add_cog(Core(liara))
