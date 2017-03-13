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
import logging
import os.path
import tarfile
import datetime


class Liara(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.args = args
        self.boot_time = time.time()  # for uptime tracking, we'll use this later
        self.logger = logger
        self.logger.info('Liara is booting, please wait...')
        self.redis = redis_conn
        self.lockdown = True  # so we don't process any messages before on_ready
        self.settings = dataIO.load_json('settings')
        self.owner = None  # this gets updated in on_ready
        self.invite_url = None  # this too
        self.send_cmd_help = send_cmd_help
        self.send_command_help = send_cmd_help  # seems more like a method name discord.py would choose
        self.self_bot = options.get('self_bot', False)
        try:
            loader = self.settings['loader']
            self.load_extension('cogs.' + loader)
            self.logger.warning('Using third-party loader and core cog, {0}.'.format(loader))
        except KeyError:
            self.load_extension('cogs.core')

    async def on_ready(self):
        self.lockdown = False
        self.redis.set('__info__', 'This database is used by the Liara discord bot, logged in as user {0}.'
                       .format(self.user))
        self.logger.info('Liara is connected!')
        self.logger.info('Logged in as {0}.'.format(self.user))
        if self.shard_id is not None:
            self.logger.info('Shard {0} of {1}.'.format(self.shard_id + 1, self.shard_count))
        if self.user.bot:
            app_info = await self.application_info()
            self.invite_url = dutils.oauth_url(app_info.id)
            self.logger.info('Invite URL: {0}'.format(self.invite_url))
            self.owner = app_info.owner
        elif self.self_bot:
            self.owner = self.user
        else:
            self.owner = self.get_user(self.args.userbot)

    async def on_message(self, message):
        pass


async def send_cmd_help(ctx):
    if ctx.invoked_subcommand:
        _help = await liara.formatter.format_help_for(ctx, ctx.invoked_subcommand)
    else:
        _help = await liara.formatter.format_help_for(ctx, ctx.command)
    for page in _help:
        # noinspection PyUnresolvedReferences
        await ctx.send(page)


if __name__ == '__main__':
    # Kick out old users who are still on stable
    if 'clean_content' not in dir(commands):
        raise ImportError('Liara now runs on the discord.py rewrite!\nPlease update your discord.py to rewrite.')

    # Get defaults for argparse
    help_description = os.environ.get('LIARA_HELP', 'Liara, an open-source Discord bot written by Pandentia and '
                                                    'contributors\n'
                                                    'https://github.com/Thessia/Liara')
    token = os.environ.get('LIARA_TOKEN', None)
    redis_host = os.environ.get('LIARA_REDIS_HOST', 'localhost')
    redis_pass = os.environ.get('LIARA_REDIS_PASSWORD', None)
    try:
        redis_port = int(os.environ.get('LIARA_REDIS_PORT', 6379))
        redis_db = int(os.environ.get('LIARA_REDIS_DB', 0))
    except ValueError:
        print('Error parsing environment variables LIARA_REDIS_PORT or LIARA_REDIS_DB\n'
              'Please check that these can be converted to integers')
        exit(4)

    try:
        shard_id = os.environ.get('LIARA_SHARD_ID', None)
        if shard_id is not None:
            shard_id = int(shard_id)
        shard_count = os.environ.get('LIARA_SHARD_COUNT', None)
        if shard_count is not None:
            shard_count = int(shard_count)
    except ValueError:
        print('Error parsing environment variables LIARA_SHARD_ID or LIARA_SHARD_COUNT\n'
              'Please check that these can be converted to integers')
        exit(4)

    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--description', type=str, help='modify the bot description shown in the help command',
                        default=help_description)
    parser.add_argument('--selfbot', help='enables selfbot mode', action='store_true')
    parser.add_argument('--userbot', help='enables userbot mode, with the specified owner ID', type=int, default=None)
    parser.add_argument('--debug', help=argparse.SUPPRESS, action='store_true')
    parser.add_argument('token', type=str, help='sets the token', default=token, nargs='?')
    shard_grp = parser.add_argument_group('sharding')
    # noinspection PyUnboundLocalVariable
    shard_grp.add_argument('--shard_id', type=int, help='the shard ID the bot should run on', default=shard_id)
    # noinspection PyUnboundLocalVariable
    shard_grp.add_argument('--shard_count', type=int, help='the total number of shards you are planning to run',
                           default=shard_count)
    redis_grp = parser.add_argument_group('redis')
    redis_grp.add_argument('--host', type=str, help='the Redis host', default=redis_host)
    # noinspection PyUnboundLocalVariable
    redis_grp.add_argument('--port', type=int, help='the Redis port', default=redis_port)
    # noinspection PyUnboundLocalVariable
    redis_grp.add_argument('--db', type=int, help='the Redis database', default=redis_db)
    redis_grp.add_argument('--password', type=str, help='the Redis password', default=redis_pass)
    args = parser.parse_args()

    if args.token is None:
        exit(parser.print_usage())

    if args.userbot is None:
        userbot = False
    else:
        userbot = True

    if args.selfbot and userbot:
        exit(parser.print_usage())

    # Logging starts here
    # Create directory for logs if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')

    # Compress logfiles that were left over from the last run
    os.chdir('logs')
    for item in os.listdir('.'):
        if item.endswith('.log'):
            with tarfile.open(item + '.tar.gz', mode='w:gz') as tar:
                tar.add(item)
            os.remove(item)
    os.chdir('..')

    # Define a format
    now = str(datetime.datetime.now()).replace(' ', '_').replace(':', '-').split('.')[0]
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')

    # Setting up loggers
    logger = logging.getLogger('liara')
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    handler = logging.FileHandler('logs/liara_{}.log'.format(now))
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.INFO)

    handler = logging.FileHandler('logs/discord_{}.log'.format(now))
    handler.setFormatter(formatter)
    discord_logger.addHandler(handler)

    # Make it clear that we're not doing any Windows support
    if sys.platform == 'win32':
        logger.warning('There is absolutely NO support for Windows-based Operating Systems. Proceed with caution, '
                       'because if you mess this up, no one will help you.')

    if args.shard_id is not None:  # usability
        args.shard_id -= 1

    # Redis connection attempt
    try:
        redis_conn = redis.StrictRedis(host=args.host, port=args.port, db=args.db, password=args.password)
    except redis.ConnectionError:
        logger.critical('Unable to connect to Redis, exiting...')
        exit(2)

    async def run_bot():
        await liara.login(args.token, bot=not (args.selfbot or userbot))
        await liara.connect()

    # noinspection PyBroadException
    def run_app():
        loop = asyncio.get_event_loop()
        exit_code = 0
        try:
            loop.run_until_complete(run_bot())
        except KeyboardInterrupt:
            logger.info('Shutting down threads and quitting. Thank you for using Liara.')
            loop.run_until_complete(liara.logout())
        except Exception:
            exit_code = 1
            logger.critical(traceback.format_exc())
            loop.run_until_complete(liara.logout())
        finally:
            loop.close()
            return exit_code

    # if we want to make an auto-reboot loop now, it would be a hell of a lot easier now
    liara = Liara('!', shard_id=args.shard_id, shard_count=args.shard_count, description=args.description,
                  self_bot=args.selfbot, pm_help=None)
    exit(run_app())
