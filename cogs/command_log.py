import logging


class CommandLog:
    """A simple cog to log commands executed."""
    def __init__(self):
        self.log = logging.getLogger('liara.command_log')

    async def on_command(self, ctx):
        self.log.info('{0.author} ({0.author.id}) executed command "{0.command}" in {0.guild}'.format(ctx))


def setup(liara):
    liara.add_cog(CommandLog())
