import logging


class CommandLog:
    """A simple cog to log commands executed."""
    def __init__(self):
        self.log = logging.getLogger('liara.command_log')

    async def on_command(self, ctx):
        kwargs = ', '.join(['{}={}'.format(k, repr(v)) for k, v in ctx.kwargs.items()])
        args = 'with arguments {} '.format(kwargs) if kwargs else ''
        msg = '{0.author} ({0.author.id}) executed command "{0.command}" {1}in {0.guild} ({0.guild.id})' \
            .format(ctx, args)
        if ctx.bot.shard_id is not None:
            msg += ' on shard {}'.format(ctx.bot.shard_id+1)
        self.log.info(msg)


def setup(liara):
    liara.add_cog(CommandLog())
