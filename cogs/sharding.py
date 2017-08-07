import platform

import datetime
from discord.ext import commands

from cogs.utils import checks
from cogs.utils.runtime import CoreMode

try:
    import tabulate
    import psutil
except ImportError:
    raise RuntimeError('tabulate and psutil are required for this cog')


tabulate.MIN_PADDING = 0  # makes for a neater table


def gather_info(liara):
    return {'status': liara.settings[liara.instance_id]['mode'].value, 'guilds': len(liara.guilds),
            'members': len(set(liara.get_all_members())), 'up_since': liara.boot_time,
            'messages_seen': liara.get_cog('Sharding').messages, 'host': platform.node().lower(),
            'memory': psutil.Process().memory_full_info().uss / 1024**2,
            'host_uptime': psutil.boot_time()}


def set_mode(liara, mode):
    liara.settings[liara.instance_id]['mode'] = mode
    liara.settings.commit(liara.instance_id)


def _halt(liara, ignore=None):
    if liara.shard_id == ignore:
        return
    liara.loop.create_task(liara.get_cog('Core').halt_())


class Sharding:
    def __init__(self, liara):
        self.liara = liara
        self.lines = []
        self.messages = 0

    async def on_message(self, _):
        self.messages += 1

    @commands.group(invoke_without_command=True)
    async def shards(self, ctx):
        """A bunch of sharding-related commands."""
        await self.liara.send_command_help(ctx)

    @shards.command()
    async def list(self, ctx, mode='generic'):
        """Lists all shards.

        * mode: "generic" or "host"

        Arguments marked with * are optional.
        """
        if mode.lower() not in ('generic', 'host'):
            await ctx.send('Invalid mode.')
            return await self.liara.send_command_help(ctx)
        msg = await ctx.send('Fetching statistics, please wait...')
        shards = await self.liara.run_on_shard('all', gather_info)
        for shard, resp in dict(shards).items():
            print(shard, resp)
            if repr(resp) == '<NoResponse>':
                shards[shard] = {'status': CoreMode.down.value}

        table = []
        if mode == 'generic':
            table = [['Active', 'Shard', 'Status', 'Guilds', 'Members', 'Messages', ]]
            for shard, state in shards.items():
                line = ['*' if shard == self.liara.shard_id else '', shard+1, state['status'],
                        state.get('guilds', ''),
                        state.get('members', ''),
                        state.get('messages_seen', '')]
                table.append(line)
        if mode == 'host':
            table = [['Active', 'Shard', 'Status', 'Host', 'Memory', 'Up Since', 'Host Up Since']]
            for shard, state in shards.items():
                line = ['*' if shard - 1 == self.liara.shard_id else '', shard, state['status'],
                        state.get('host', ''),
                        state.get('memory', ''),
                        datetime.datetime.utcfromtimestamp(state.get('up_since', 0)) if state.get('up_since') else '',
                        datetime.datetime.utcfromtimestamp(state.get('host_uptime', 0)) if state.get('host_uptime')
                        else '']
                table.append(line)
        table = '```prolog\n{}\n```'.format(
            tabulate.tabulate(table, tablefmt='psql', headers='firstrow'))
        await msg.edit(content=table)

    @shards.command()
    async def get(self, ctx):
        """Gets the current shard."""
        await ctx.send('I am shard {} of {}.'.format(self.liara.shard_id+1, self.liara.shard_count))

    @shards.command()
    @checks.is_owner()
    async def set_mode(self, ctx, shard: int, mode: CoreMode):
        """Sets a shard's mode.

        - shard: The shard of which you want to set the mode
        - mode: The mode you want to set the shard to
        """
        active = await self.liara.ping_shard(shard-1)
        if not active:
            return await ctx.send('Shard not online.')
        if self.liara.shard_id == shard-1 and mode in (CoreMode.down, CoreMode.boot):
            return await ctx.send('This action would be too dangerous to perform on the current shard. Try running '
                                  'this command from a different shard targeting this one.')
        await self.liara.run_on_shard(shard-1, set_mode, mode)
        await ctx.send('Mode set.')

    @shards.command(aliases=['shutdown'])
    @checks.is_owner()
    async def halt(self, ctx, shard: int):
        """Halts a shard.

        - shard: The shard you want to halt
        """
        active = await self.liara.ping_shard(shard-1)
        if not active:
            return await ctx.send('Shard not online.')
        await self.liara.run_on_shard(shard-1, _halt)
        await ctx.send('Halt command sent.')

    @shards.command()
    @checks.is_owner()
    async def halt_all(self, ctx):
        """Halts all shards."""
        msg = await ctx.send('Sending command...')
        await self.liara.run_on_shard('all', _halt, self.liara.shard_id)
        await msg.edit(content='Thank you for using Liara.')
        await self.liara.get_cog('Core').halt_()


def setup(liara):
    if liara.shard_id is not None:
        liara.add_cog(Sharding(liara))
    else:
        raise RuntimeError('this cog requires your bot to be sharded')
