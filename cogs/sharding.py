import aiohttp
import json
import asyncio
import datetime

import random
from discord.ext import commands

from cogs.core import CoreMode
from cogs.utils import checks

try:
    import tabulate
except ImportError:
    raise RuntimeError('tabulate and psutil are required for this cog')


tabulate.MIN_PADDING = 0  # makes for a neater table


def gather_info(liara):
    return {'status': liara.settings[liara.instance_id]['mode'].value, 'guilds': len(liara.guilds),
            'members': len(set(liara.get_all_members())), 'up_since': liara.boot_time,
            'messages_seen': liara.get_cog('Sharding').messages}


def set_mode(liara, mode):
    liara.settings[liara.instance_id]['mode'] = mode


def _halt(liara):
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

    async def get_line(self):
        if not self.lines:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://gist.githubusercontent.com/Pandentia/373f23a4443e4c363b653777f296301e/'
                                       'raw/0fd0a31891bf9e3ea59c1a5d9e739579d6dab714/sims_loading_lines.json') as resp:
                    self.lines = json.loads(await resp.text())
        return '*{}...*'.format(random.choice(self.lines))

    async def edit_task(self, message):
        while True:
            await asyncio.sleep(random.randint(2, 4))
            await message.edit(content=await self.get_line())

    @shards.command()
    async def list(self, ctx):
        """Lists all shards."""
        msg = await ctx.send(await self.get_line())
        task = self.liara.loop.create_task(self.edit_task(msg))
        shards = {}
        for shard in range(0, self.liara.shard_count):
            status = await self.liara.ping_shard(shard)
            shards[shard+1] = status
        for shard, status in dict(shards).items():
            if not status:
                shards[shard] = {'status': CoreMode.down.value}
            else:
                shards[shard] = await self.liara.run_on_shard(shard-1, gather_info)
        table = [['Active', 'Shard', 'Status', 'Guilds', 'Members', 'Up Since', 'Messages']]
        for shard, state in shards.items():
            line = ['*' if shard - 1 == self.liara.shard_id else '', shard, state['status'], state.get('guilds', ''),
                    state.get('members', ''),
                    datetime.datetime.fromtimestamp(state.get('up_since', 0)) if state.get('up_since') else '',
                    state.get('messages_seen', '')]
            table.append(line)
        table = '```prolog\n{}\n```'.format(
            tabulate.tabulate(table, tablefmt='psql', headers='firstrow'))
        task.cancel()
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


def setup(liara):
    if liara.shard_id is not None:
        liara.add_cog(Sharding(liara))
    else:
        raise RuntimeError('this cog requires your bot to be sharded')
