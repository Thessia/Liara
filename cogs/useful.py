from discord.ext import commands
from cogs.utils import checks
import time


class Useful:
    def __init__(self, liara):
        self.liara = liara

    @commands.command()
    async def ping(self):
        """Checks to see if Liara is responding.
        Also checks for reaction time in milliseconds by checking how long it takes for a "typing" status to go through.
        """
        before_typing = time.time()
        await self.liara.type()
        after_typing = time.time()
        ms = int((after_typing - before_typing) * 1000)
        await self.liara.say('Pong. Pseudo-ping: `{0}ms`'.format(ms))

    @commands.command()
    @checks.is_bot_account()
    async def invite(self):
        """Gets Liara's invite URL."""
        await self.liara.say('My invite URL is\n<{0}&permissions=8>.\n\n'
                             'You\'ll need the **Manage Server** permission to add me to a server.'
                             .format(self.liara.invite_url))

    def format_english(self, number, metric):  # just for the uptime command, but maybe we'll use this somewhere else
        if number is None:
            return
        if 0 < number < 2:
            return '{0} {1}'.format(number, metric)
        else:
            return '{0} {1}s'.format(number, metric)

    @commands.command()
    async def uptime(self):
        """Gets Liara's uptime.
        Modified R. Danny method (thanks Danny!)"""
        now = time.time()
        difference = int(now) - int(self.liara.boot_time)  # otherwise we're dealing with floats
        hours, remainder = divmod(difference, 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        if days:
            output = 'Liara has been up for {d}, {h}, {m} and {s}.'
        else:
            output = 'Liara has been up for {h}, {m} and {s}.'

        output = output.format(d=self.format_english(days, 'day'), h=self.format_english(hours, 'hour'),
                               m=self.format_english(minutes, 'minute'), s=self.format_english(seconds, 'second'))

        await self.liara.say(output)


def setup(liara):
    liara.add_cog(Useful(liara))
