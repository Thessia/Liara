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

from cogs.utils import checks
from cogs.utils.storage import RedisCollection
from cogs.utils.runtime import CoreMode


def reload_core(liara):
    liara.loop.create_task(liara.get_cog('Core').reload_self())


class Core:
    def __init__(self, liara):
        self.liara = liara

        self.ignore_db = False
        self.verbose_errors = False  # tracebacks?
        self.informative_errors = True  # info messages based on error

        self.settings = RedisCollection(self.liara.redis, 'settings')
        self.logger = self.liara.logger
        self.liara.loop.create_task(self._post())
        self.global_preconditions = [self._ignore_preconditions]  # preconditions to message processing
        self.global_preconditions_overrides = [self._ignore_overrides]  # overrides to the preconditions
        self._eval = {}
        self.loop = None  # make pycharm stop complaining

        for obj in dir(self):  # docstring formatting
            if obj.startswith('_'):
                continue
            obj = getattr(self, obj)
            if not isinstance(obj, commands.Command):
                continue
            if not obj.help:
                continue
            obj.help = obj.help.format(self.liara.name)

    def __unload(self):
        self.loop.cancel()

    async def _cog_loop(self):
        cogs: list = await self.settings.get('cogs', [])
        edited = False
        for cog in cogs:
            if cog not in list(self.liara.extensions):
                # noinspection PyBroadException
                try:
                    self.load_cog(cog)
                except Exception:
                    cogs.remove(cog)
                    edited = True
                    self.logger.warning('{!r} could not be loaded. This message will not be shown again.'.format(cog))
        if edited:
            await self.settings.set('cogs', cogs)

        for cog in list(self.liara.extensions):
            if cog == 'cogs.core':
                continue
            if cog not in cogs:
                self.liara.unload_extension(cog)

    async def _get_guild_setting(self, guild_id, attribute, default=None):
        guild = await self.settings.get('guilds:{}'.format(guild_id), {})
        return guild.get(attribute, default)

    async def _set_guild_setting(self, guild_id, attribute, value):
        guild = await self.settings.get('guilds:{}'.format(guild_id), {})
        guild[attribute] = value
        await self.settings.set('guilds:{}'.format(guild_id), guild)

    async def _post(self):
        """Power-on self test. Beep boop."""
        self.liara.owners = []

        # set prefixes
        prefix = str(random.randint(1, 2**8))
        prefixes = await self.settings.get('prefixes')
        if prefixes is None:
            prefixes = [prefix]
            await self.settings.set('prefixes', prefixes)
        self.liara.command_prefix = prefixes
        self.logger.info('{}\'s prefixes are: {}'.format(self.liara.name, ', '.join(map(repr, prefixes))))

        # Load cogs
        await self._cog_loop()

        # Mess with the instance's mode
        instance = await self.settings.get(self.liara.instance_id, {'mode': CoreMode.boot})
        if not self.liara.ready:
            if instance['mode'] == CoreMode.up:
                instance['mode'] = CoreMode.boot
                await self.settings.set(self.liara.instance_id, instance)

        await self.liara.wait_until_ready()
        self.liara.ready = True
        if instance['mode'] == CoreMode.boot:
            instance['mode'] = CoreMode.up
            await self.settings.set(self.liara.instance_id, instance)

        # migration
        keys = await self.settings.keys()
        for key in keys:
            if key == 'roles':
                roles = await self.settings.get('roles')
                for guild in roles:
                    self._set_guild_setting(int(guild), 'roles', roles[guild])
            # TODO: account for other shit

        # start the loop
        self.loop = self.liara.loop.create_task(self._maintenance_loop())

    async def _maintenance_loop(self):
        app_info = await self.liara.application_info()
        while True:
            if not self.ignore_db:
                # Loading cogs / Unloading cogs
                await self._cog_loop()
                # Prefix changing
                self.liara.command_prefix = await self.settings.get('prefixes')
                # Owner checks
                owners = await self.settings.get('owners', [])
                owners = list(map(int, owners))
                if app_info.owner.id not in owners:
                    owners.append(app_info.owner.id)
                    await self.settings.set('owners', owners)
                self.liara.owners = owners
            await asyncio.sleep(1)

    async def _ignore_overrides(self, message):
        if isinstance(message.author, discord.Member):
            if message.guild.owner == message.author:
                return True
            guild = str(message.guild.id)
            try:
                roles = [x.name.lower() for x in message.author.roles]
                if self.settings['roles'][guild]['admin_role'].lower() in roles:
                    return True
            except KeyError or AttributeError:
                pass

    async def _ignore_preconditions(self, message):
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

    @staticmethod
    def get_traceback(exception, limit=None, chain=True):
        return ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__, limit=limit,
                                                  chain=chain))

    async def reload_self(self):
        self.liara.unload_extension('cogs.core')
        self.load_cog('cogs.core')

    # make IDEA stop acting like a baby
    # noinspection PyShadowingBuiltins
    async def load_cog(self, name):
        self.logger.debug('Attempting to load cog {}'.format(name))

        if name in self.liara.extensions:
            return

        self.liara.load_extension(name)

        cogs = await self.settings.get('cogs')
        if name not in cogs:
            cogs.append(name)
            await self.settings.set('cogs', cogs)

        self.logger.debug('Cog {} loaded sucessfully'.format(name))

    async def on_message(self, message):
        instance = await self.settings.get(self.liara.instance_id, {})
        mode = instance.get('mode', CoreMode.down)
        if mode in (CoreMode.down, CoreMode.boot):
            return
        if str(message.author.id) in self.liara.owners:  # *always* process owner commands
            await self.liara.process_commands(message)
            return
        if mode == CoreMode.maintenance:
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
            except Exception:
                self.logger.warning('Removed precondition override "{}", it was malfunctioning.'
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
            except Exception:
                self.logger.warning('Removed precondition "{}", it was malfunctioning.'
                                    .format(precondition.__name__))
                self.global_preconditions.remove(precondition)

        await self.liara.process_commands(message)

    async def on_command_error(self, context, exception):
        try:
            if isinstance(exception, commands.CommandInvokeError):
                exception = exception.original

                if isinstance(exception, discord.Forbidden):
                    if self.informative_errors:
                        return await context.send('I don\'t have permission to perform the action you requested.')
                    else:
                        return  # don't care, don't log

                error = '`{}` in command `{}`: ```py\n{}\n```'.format(type(exception).__name__,
                                                                      context.command.qualified_name,
                                                                      self.get_traceback(exception))
                self.logger.error(error)
                if self.informative_errors:
                    if self.verbose_errors:
                        await context.send(error)
                    else:
                        await context.send('An error occured while running that command.')
            if not self.informative_errors:  # everything beyond this point is purely informative
                return
            if isinstance(exception, commands.CommandNotFound):
                return  # be nice to other bots
            if isinstance(exception, commands.MissingRequiredArgument):
                return await self.liara.send_command_help(context)
            if isinstance(exception, commands.BadArgument):
                await context.send('Bad argument.')
                await self.liara.send_command_help(context)
            if isinstance(exception, commands.NoPrivateMessage):
                # returning to avoid CheckFailure
                return await context.send('That command is not available in direct messages.')
            if isinstance(exception, commands.CommandOnCooldown):
                await context.send('That command is cooling down.')
            if isinstance(exception, commands.CheckFailure):
                await context.send('You do not have access to that command.')
            if isinstance(exception, commands.DisabledCommand):
                await context.send('That command is disabled.')
        except discord.HTTPException:
            pass

    @commands.group(name='set', invoke_without_command=True)
    @checks.admin_or_permissions()
    async def set_cmd(self, ctx):
        """Sets {}'s settings."""
        await self.liara.send_command_help(ctx)

    @set_cmd.command()
    @checks.is_owner()
    async def prefix(self, ctx, *prefixes: str):
        """Sets {}'s prefixes.

        - prefixes: A list of prefixes to use
        """
        if not prefixes:
            await self.liara.send_command_help(ctx)
            return

        self.liara.command_prefix = prefixes
        self.settings.set('prefixes', prefixes)
        await ctx.send('Prefix(es) set.')

    @set_cmd.command()
    @checks.is_owner()
    async def name(self, ctx, username: str):
        """Changes {}'s username.

        - username: The username to use
        """
        await self.liara.user.edit(username=username)
        await ctx.send('Username changed. Please call me {} from now on.'.format(username))

    @set_cmd.command()
    @checks.is_owner()
    async def avatar(self, ctx, url: str):
        """Changes {0}'s avatar.

        - url: The URL to set {0}'s avatar to
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
        """Sets {}'s owners.

        - owners: A list of owners to use
        """
        await self.settings.set('owners', [x.id for x in list(owners)])
        if len(list(owners)) == 1:
            await ctx.send('Owner set.')
        else:
            await ctx.send('Owners set.')

    @set_cmd.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.is_not_selfbot()
    async def admin(self, ctx, *, role: str=None):
        """Sets {}'s admin role.
        Roles are non-case sensitive.

        - role: The name of the role to use as the admin role
        """
        server = str(ctx.message.guild.id)
        if server not in self.settings['roles']:
            self.settings['roles'][server] = {}
            self.settings.commit('roles')
        if role is not None:
            self.settings['roles'][server]['admin_role'] = role
            self.settings.commit('roles')
            await ctx.send('Admin role set to `{}` successfully.'.format(role))
        else:
            if 'admin_role' in self.settings['roles'][server]:
                self.settings['roles'][server].pop('admin_role')
                self.settings.commit('roles')
            await ctx.send('Admin role cleared.\n'
                           'If you didn\'t intend to do this, use `{}help set admin` for help.'
                           .format(ctx.prefix))

    @set_cmd.command()
    @commands.guild_only()
    @checks.admin_or_permissions()
    @checks.is_not_selfbot()
    async def moderator(self, ctx, *, role: str=None):
        """Sets {}'s moderator role.
        Roles are non-case sensitive.

        - role: The name of the role to use as the moderator role
        """
        server = str(ctx.message.guild.id)
        if server not in self.settings['roles']:
            self.settings['roles'][server] = {}
            self.settings.commit('roles')
        if role is not None:
            self.settings['roles'][server]['mod_role'] = role
            self.settings.commit('roles')
            await ctx.send('Moderator role set to `{}` successfully.'.format(role))
        else:
            if 'mod_role' in self.settings['roles'][server]:
                self.settings['roles'][server].pop('mod_role')
                self.settings.commit('roles')
            await ctx.send('Moderator role cleared.\n'
                           'If you didn\'t intend to do this, use `{}help set moderator` for help.'
                           .format(ctx.prefix))

    def _ignore_check(self, ctx):
        server = str(ctx.message.guild.id)
        if server not in self.settings['ignores']:
            self.settings['ignores'][server] = {'server_ignore': False, 'ignored_channels': []}
            self.settings.commit('ignores')

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
                self.settings.commit('ignores')
            await ctx.send('Channel ignored.')
        else:
            if channel in self.settings['ignores'][server]['ignored_channels']:
                self.settings['ignores'][server]['ignored_channels'].remove(channel)
                self.settings.commit('ignores')
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
            self.settings.commit('ignores')
            await ctx.send('Server ignored.')
        else:
            self.settings['ignores'][server]['server_ignore'] = False
            self.settings.commit('ignores')
            await ctx.send('Server unignored.')

    async def halt_(self):
        self.ignore_db = True
        for cog in list(self.liara.extensions):
            self.liara.unload_extension(cog)
        await asyncio.sleep(2)  # to let some functions clean up their mess
        await self.liara.logout()

    @commands.command(aliases=['shutdown'])
    @checks.is_owner()
    async def halt(self, ctx, skip_confirm=False):
        """Shuts {} down.

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
        await self.halt_()

    @commands.command()
    @checks.is_owner()
    async def load(self, ctx, name: str):
        """Loads a cog.

        - name: The name of the cog to load
        """
        cog_name = 'cogs.{}'.format(name)

        if cog_name in self.liara.extensions:
            return await ctx.send('Unable to load; the cog is already loaded.')

        try:
            await self.load_cog(cog_name)
            await ctx.send('`{}` loaded sucessfully.'.format(name))
        except Exception as e:
            await ctx.send('Unable to load; the cog caused a `{}`:\n```py\n{}\n```' \
                           .format(type(e).__name__, self.get_traceback(e)))

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
        cog_name = 'cogs.{}'.format(name)
        if cog_name in list(self.liara.extensions):
            self.liara.unload_extension(cog_name)
            self.settings['cogs'].remove(cog_name)
            self.settings.commit('cogs')
            await ctx.send('`{}` unloaded successfully.'.format(name))
        else:
            await ctx.send('Unable to unload; that cog isn\'t loaded.')

    @commands.command()
    @checks.is_owner()
    async def reload(self, ctx, name: str):
        """Reloads a cog."""
        if name == 'core':
            await self.liara.run_on_shard(None if self.liara.shard_id is None else 'all', reload_core)
            await ctx.send('Command dispatched, reloading core on all shards now.')
            return
        cog_name = 'cogs.{}'.format(name)
        if cog_name in list(self.liara.extensions):
            msg = await ctx.send('`{}` reloading...'.format(name))
            self.liara.unload_extension(cog_name)
            self.settings['cogs'].remove(cog_name)
            self.settings.commit('cogs')
            await asyncio.sleep(2)
            resp = await self.liara.run_on_shard(None if self.liara.shard_id is None else 0, load_cog, cog_name)
            if resp is not None:
                _msg = '`{}` reloaded unsuccessfully on the main shard due to a `{}`:\n```py\n{}\n```\n' \
                      .format(name, type(resp).__name__, self.get_traceback(resp))
                _msg += 'Aborting reload on other shards...'
                await msg.edit(content=_msg)
                return
            await msg.edit(content='`{}` reloaded successfully on main shard, waiting for others to catch up...'
                           .format(name))
            await asyncio.sleep(2)
            if cog_name in list(self.liara.extensions):
                await msg.edit(content='`{}` reloaded successfully.'.format(name))
            else:
                await msg.edit(content='`{}` reloaded unsuccessfully on a non-main shard. Check your shard\'s logs for '
                                       'more details. The cog has not been loaded on the main shard.'.format(name))
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
            output = '\n'+self.get_traceback(e, 0)
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
                           '{}'.format(gist['html_url']))


def setup(liara):
    liara.add_cog(Core(liara))
