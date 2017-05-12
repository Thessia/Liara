import asyncio
import time
from datetime import datetime

from collections import Counter
from discord.ext import commands

from cogs.utils import checks


class Useful:
    def __init__(self, liara):
        self.liara = liara
        self.event_counter = Counter()

    @commands.command()
    async def ping(self, ctx):
        """Checks to see if Liara is responding.
        Also checks for reaction time in milliseconds by checking how long it takes for a "typing" status to go through.
        """
        before_typing = time.monotonic()
        await ctx.trigger_typing()
        after_typing = time.monotonic()
        ms = int((after_typing - before_typing) * 1000)
        await ctx.send('Pong. Pseudo-ping: `{0}ms`'.format(ms))

    @commands.command(hidden=True)
    @checks.is_owner()
    async def fullping(self, ctx, amount: int=10):
        """More intensive ping, gives debug info on reaction times"""
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
        """Gets Liara's invite URL."""
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
        """Gets Liara's uptime.
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
