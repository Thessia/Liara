import aiohttp
import json
import asyncio
import datetime

import random
from discord.ext import commands

try:
    import tabulate
except ImportError:
    raise RuntimeError('tabulate and psutil are required for this cog')


def gather_info(liara):
    return {'status': 'online', 'guilds': len(liara.guilds), 'members': len(set(liara.get_all_members())),
            'up_since': liara.boot_time}


class Sharding:
    def __init__(self, liara):
        self.liara = liara
        self.lines = []

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
                shards[shard] = {'status': 'offline'}
            else:
                shards[shard] = await self.liara.run_on_shard(shard-1, gather_info)
        table = [['ID', 'Status', 'Guilds', 'Members', 'Up Since']]
        for shard, state in shards.items():
            table.append([str(shard) if shard-1 != self.liara.shard_id else str(shard)+'*', state['status'],
                          state.get('guilds', ''), state.get('members', ''),
                          datetime.datetime.fromtimestamp(state.get('up_since', 0)) if state['status'] == 'online' else
                          ''])
        table = '```prolog\n{}\n* Current Shard\n```'.format(tabulate.tabulate(table, tablefmt='grid'))
        task.cancel()
        await msg.edit(content=table)

    @shards.command()
    async def get(self, ctx):
        """Gets the current shard."""
        await ctx.send('I am shard {} of {}.'.format(self.liara.shard_id+1, self.liara.shard_count))


def setup(liara):
    if liara.shard_id is not None:
        liara.add_cog(Sharding(liara))
    else:
        raise RuntimeError('this cog requires your bot to be sharded')
