import asyncio
import time
from collections import Counter
from datetime import datetime

from discord.ext import commands

from cogs.utils import checks


class Useful:
    def __init__(self, liara):
        self.liara = liara
        self.event_counter = Counter()

        for obj in dir(self):  # docstring formatting
            if obj.startswith('_'):
                continue
            obj = getattr(self, obj)
            if not isinstance(obj, commands.Command):
                continue
            if not obj.help:
                continue
            obj.help = obj.help.format(self.liara.name)

    @staticmethod
    async def timeit(coro):
        """Times a coroutine."""
        before = time.monotonic()
        coro_result = await coro
        after = time.monotonic()
        return after - before, coro_result

    @staticmethod
    def format_delta(delta):
        return round(delta * 1000)

    @commands.command()
    async def ping(self, ctx):
        """Checks to see if {} is responding.
        Also collects a bunch of other nerd stats.
        """
        before = time.monotonic()
        typing_delay = self.format_delta((await self.timeit(ctx.trigger_typing()))[0])
        message_delay, message = await self.timeit(ctx.send('..'))
        message_delay = self.format_delta(message_delay)
        edit_delay = self.format_delta((await self.timeit(message.edit(content='...')))[0])
        gateway_delay = self.format_delta((await self.timeit(await self.liara.ws.ping()))[0])
        after = time.monotonic()
        total_delay = self.format_delta(after - before)
        await message.edit(content='Pong.\n\n**Stats for nerds**:\nTyping delay: `{}ms`\nMessage send delay: `{}ms`\n'
                                   'Message edit delay: `{}ms`\nGateway delay: `{}ms`\nTotal: `{}ms`'
                                   .format(typing_delay, message_delay, edit_delay, gateway_delay, total_delay))

    @commands.command(hidden=True)
    @checks.is_owner()
    async def fullping(self, ctx, amount: int=10):
        """More intensive ping, gives debug info on reaction times.

        - amount (optional): The amount of pings to do
        """
        if not 1 < amount < 200:
            await ctx.send('Please choose a more reasonable amount of pings.')
            return
        please_wait_message = await ctx.send('Please wait, this will take a while...')
        await ctx.trigger_typing()
        values = []
        for i in range(0, amount):
            before = time.monotonic()
            await (await self.liara.ws.ping())
            after = time.monotonic()
            delta = (after - before) * 1000
            values.append(int(delta))
            await asyncio.sleep(0.5)
        await please_wait_message.delete()
        average = round(sum(values) / len(values))
        await ctx.send('Average ping time over {} pings: `{}ms`\nMin/Max ping time: `{}ms/{}ms`'
                       .format(amount, average, min(values), max(values)))

    @commands.command()
    @checks.is_bot_account()
    async def invite(self, ctx):
        """Gets {}'s invite URL."""
        await ctx.send('My invite URL is\n<{0}&permissions=8>.\n\n'
                       'You\'ll need the **Manage Server** permission to add me to a server.'
                       .format(self.liara.invite_url))

    @staticmethod
    def format_english(number, metric):  # just for the uptime command, but maybe we'll use this somewhere else
        if number is None:
            return
        if 0 < number < 2:
            return '{0} {1}'.format(number, metric)
        else:
            return '{0} {1}s'.format(number, metric)

    @commands.command()
    async def uptime(self, ctx):
        """Gets {}'s uptime.
        Modified R. Danny method (thanks Danny!)"""
        now = time.time()
        difference = int(now) - int(self.liara.boot_time)  # otherwise we're dealing with floats
        hours, remainder = divmod(difference, 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        if days:
            output = 'I\'ve been up for {d}, {h}, {m} and {s}.'
        else:
            output = 'I\'ve been up for {h}, {m} and {s}.'

        output = output.format(d=self.format_english(days, 'day'), h=self.format_english(hours, 'hour'),
                               m=self.format_english(minutes, 'minute'), s=self.format_english(seconds, 'second'))

        await ctx.send(output)

    async def on_socket_response(self, resp):
        self.event_counter.update([resp.get('t')])

    @commands.command(hidden=True)
    async def socketstats(self, ctx):
        boot_time = datetime.fromtimestamp(self.liara.boot_time)
        table = ''
        for k, v in self.event_counter.items():
            table += '\n`{}`: {}'.format(k, v)
        await ctx.send('{} socket events seen since {}.{}'.format(sum(self.event_counter.values()), boot_time, table))


def setup(liara):
    liara.add_cog(Useful(liara))
