from discord.ext import commands
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
    async def invite(self):
        """Gets Liara's invite URL."""
        await self.liara.say('My invite URL is\n<{0}&permissions=8>.\n\n'
                             'You\'ll need the **Manage Server** permission to add me to a server.'
                             .format(self.liara.invite_url))


def setup(liara):
    liara.add_cog(Useful(liara))
