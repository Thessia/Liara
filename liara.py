#!/usr/bin/env python3

from discord.ext import commands
from discord import utils as dutils
from cogs.utils.dataIO import dataIO
import argparse
import sys
import time
import asyncio
import traceback
import redis

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--description', type=str, help='modify the bot description shown in help',
                    default='Liara, an open-source Discord bot written by Pandentia\nhttps://github.com/Pandentia')
parser.add_argument('--selfbot', type=bool, help='enables selfbot mode', default=False)
parser.add_argument('token', type=str, help='sets the token')
shard_grp = parser.add_argument_group('sharding')
shard_grp.add_argument('--shard_id', type=int, help='the shard ID the bot should run on')
shard_grp.add_argument('--shard_count', type=int, help='the total number of shards you are planning to run')
redis_grp = parser.add_argument_group('redis')
redis_grp.add_argument('--host', type=str, help='the Redis host', default='localhost')
redis_grp.add_argument('--port', type=int, help='the Redis port', default=6379)
redis_grp.add_argument('--db', type=int, help='the Redis database', default=0)
redis_grp.add_argument('--password', type=str, help='the Redis password', default=None)
args = parser.parse_args()

# Make it clear that we're not doing any Windows support
if sys.platform == 'win32':
    print('There is absolutely NO support for Windows-based Operating Systems. Proceed with caution, '
          'because if you mess this up, no one will help you.')

if args.shard_id is not None:  # usability
    args.shard_id -= 1

try:
    redis_conn = redis.StrictRedis(host=args.host, port=args.port, db=args.db, password=args.password)
except redis.ConnectionError:
    print('Unable to connect to Redis...')
    exit(2)


class Liara(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.args = args
        self.boot_time = time.time()  # for uptime tracking, we'll use this later
        print('Liara is booting, please wait...')
        self.redis = redis.StrictRedis(host=args.host, port=args.port, db=args.db, password=args.password)
        self.stopped = False
        self.lockdown = True  # so we don't process any messages before on_ready
        self.settings = dataIO.load_json('settings')
        self.owner = None  # this gets updated in on_ready
        self.invite_url = None  # this too
        try:
            loader = self.settings['loader']
            self.load_extension('cogs.' + loader)
            print('Using third-party loader and core cog, {0}.'.format(loader))
        except KeyError:
            self.load_extension('cogs.core')

    async def on_ready(self):
        self.lockdown = False
        self.redis.set('__info__', 'This database is used by the Liara discord bot, logged in as user {0}.'
                       .format(self.user))
        print('Liara is connected!\nLogged in as {0}.'.format(self.user))
        if self.shard_id is not None:
            print('Shard {0} of {1}.'.format(self.shard_id + 1, self.shard_count))
        if self.user.bot:
            app_info = await self.application_info()
            self.invite_url = dutils.oauth_url(app_info.id)
            print('Invite URL: {0}'.format(self.invite_url))
            self.owner = app_info.owner
        else:
            self.owner = self.user

    async def on_message(self, message):
        pass

    @staticmethod
    async def send_cmd_help(ctx):
        await send_cmd_help(ctx)

    async def logout(self):
        self.stopped = True
        await super().logout()


async def send_cmd_help(ctx):
    if ctx.invoked_subcommand:
        _help = liara.formatter.format_help_for(ctx, ctx.invoked_subcommand)
    else:
        _help = liara.formatter.format_help_for(ctx, ctx.command)
    for page in _help:
        # noinspection PyUnresolvedReferences
        await liara.send_message(ctx.message.channel, page)


async def run_bot():
    await liara.login(args.token, bot=not args.selfbot)
    await liara.connect()


# noinspection PyBroadException
def run_app():
    loop = asyncio.get_event_loop()
    exit_code = 0
    try:
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        print('Shutting down threads and quitting. Thank you for using Liara.')
        loop.run_until_complete(liara.logout())
    except Exception:
        exit_code = 1
        print(traceback.format_exc())
        loop.run_until_complete(liara.logout())
    finally:
        loop.close()
        return exit_code

if __name__ == '__main__':
    # if we want to make an auto-reboot loop now, it would be a hell of a lot easier now
    liara = Liara('!', shard_id=args.shard_id, shard_count=args.shard_count, description=args.description,
                  self_bot=args.selfbot)
    exit(run_app())
