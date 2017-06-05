#!/usr/bin/env python3

import argparse
import asyncio
import bz2
import datetime
import json
import logging
import sys
import threading
import time
import traceback

import os
import redis
from discord import utils as dutils
from discord.ext import commands

from cogs.utils import dataIO


class Liara(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.redis = kwargs.pop('redis', None)
        if self.redis is None:
            raise AssertionError('No redis instance specified')
        self.test = kwargs.pop('test', False)
        self.args = kwargs.pop('cargs', None)  # not used in most code, just a nice thing to have (optional)
        self.boot_time = time.time()  # for uptime tracking, we'll use this later
        self.logger = logging.getLogger('liara')
        self.logger.info('Liara is booting, please wait...')
        self.lockdown = True  # so we don't process any messages before on_ready
        self.settings = dataIO.load('settings')
        self.owner = None  # this gets updated in on_ready
        self.invite_url = None  # this too
        self.send_cmd_help = send_cmd_help
        self.send_command_help = send_cmd_help  # seems more like a method name discord.py would choose
        self.self_bot = kwargs.get('self_bot', False)
        self.pubsub = None
        threading.Thread(name='pubsub', target=self.pubsub_loop, daemon=True).start()
        super().__init__(*args, **kwargs)
        try:
            loader = self.settings['loader']
            self.load_extension('cogs.' + loader)
            self.logger.warning('Using third-party loader and core cog, {0}.'.format(loader))
        except KeyError:
            self.load_extension('cogs.core')

    def pubsub_loop(self):
        self.pubsub = self.redis.pubsub()
        db = str(self.redis.connection_pool.connection_kwargs['db'])
        self.pubsub.subscribe('liara.{}.pubsub'.format(db))
        for event in self.pubsub.listen():
            if event['type'] != 'message':
                continue
            try:
                _json = json.loads(event['data'].decode())
                self.dispatch('liara_pubsub_raw_receive', _json)
                if _json.get('shard_id', self.shard_id) == self.shard_id:
                    continue
                if _json.get('payload') is None:
                    continue
                self.dispatch('liara_pubsub_receive', _json['payload'])
            except json.decoder.JSONDecodeError:
                continue

    def publish(self, payload):
        db = str(self.redis.connection_pool.connection_kwargs['db'])
        self.redis.publish('liara.{}.pubsub'.format(db), json.dumps({'shard_id': self.shard_id, 'payload': payload}))

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
        if self.test:
            self.logger.info('Test complete, logging out...')
            await self.logout()
            exit(0)  # jenkins' little helper

    async def on_message(self, message):
        pass


async def send_cmd_help(ctx):
    if ctx.invoked_subcommand:
        _help = await ctx.bot.formatter.format_help_for(ctx, ctx.invoked_subcommand)
    else:
        _help = await ctx.bot.formatter.format_help_for(ctx, ctx.command)
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

    shard_id = os.environ.get('LIARA_SHARD_ID', None)
    shard_count = os.environ.get('LIARA_SHARD_COUNT', None)
    try:
        if shard_id is not None:
            shard_id = int(shard_id)
        if shard_count is not None:
            shard_count = int(shard_count)
    except ValueError:
        print('Error parsing environment variables LIARA_SHARD_ID or LIARA_SHARD_COUNT\n'
              'Please check that these can be converted to integers')
        exit(4)

    message_cache = os.environ.get('LIARA_MESSAGE_CACHE_COUNT', 5000)
    try:
        if message_cache is not None:
            message_cache = int(message_cache)
    except ValueError:
        print('Error parsing environment variable LIARA_MESSAGE_CACHE_COUNT\n'
              'Please check that this can be converted to an integer')
        exit(4)

    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--description', type=str, help='modify the bot description shown in the help command',
                        default=help_description)
    parser.add_argument('--selfbot', help='enables selfbot mode', action='store_true')
    parser.add_argument('--userbot', help='enables userbot mode, with the specified owner ID', type=int, default=None)
    parser.add_argument('--debug', help=argparse.SUPPRESS, action='store_true')
    parser.add_argument('--test', help=argparse.SUPPRESS, action='store_true')
    parser.add_argument('--message_cache_count', help='sets the maximum amount of messages to cache in liara.messages',
                        default=message_cache, type=int)
    parser.add_argument('--uvloop', help='enables uvloop mode', action='store_true')
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
    cargs = parser.parse_args()

    if cargs.token is None:
        exit(parser.print_usage())

    if cargs.userbot is None:
        userbot = False
    else:
        userbot = True

    if cargs.selfbot and userbot:
        exit(parser.print_usage())

    if cargs.uvloop:
        try:
            # noinspection PyUnresolvedReferences
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        except ImportError:
            print('uvloop is not installed!')
            exit(1)

    # Logging starts here
    # Create directory for logs if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')

    # Compress logfiles that were left over from the last run
    os.chdir('logs')
    if not os.path.exists('old'):
        os.mkdir('old')
    for item in os.listdir('.'):
        if item.endswith('.log'):
            with bz2.open(item + '.bz2', 'w') as f:
                f.write(open(item, 'rb').read())
            os.remove(item)
    for item in os.listdir('.'):
        if item.endswith('.gz') or item.endswith('.bz2'):
            os.rename(item, 'old/' + item)
    os.chdir('..')

    # Define a format
    now = str(datetime.datetime.now()).replace(' ', '_').replace(':', '-').split('.')[0]
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')

    # Setting up loggers
    logger = logging.getLogger('liara')
    if cargs.debug:
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
    if cargs.debug:
        discord_logger.setLevel(logging.DEBUG)
    else:
        discord_logger.setLevel(logging.INFO)

    handler = logging.FileHandler('logs/discord_{}.log'.format(now))
    handler.setFormatter(formatter)
    discord_logger.addHandler(handler)

    # Make it clear that we're not doing any Windows support
    def warn_win():
        logger.warning('There is absolutely NO support for Windows-based operating systems. Proceed with caution, '
                       'because if you mess this up, no one will help you.')

    if sys.platform == 'win32':
        warn_win()
    if sys.platform == 'linux':
        if os.path.exists('/dev/lxss'):  # go away, Linux subsystem, you're not real
            warn_win()

    if cargs.shard_id is not None:  # usability
        cargs.shard_id -= 1

    # Redis connection attempt
    try:
        redis_conn = redis.StrictRedis(host=cargs.host, port=cargs.port, db=cargs.db, password=cargs.password)
    except redis.ConnectionError:
        logger.critical('Unable to connect to Redis, exiting...')
        exit(2)

    # if we want to make an auto-reboot loop now, it would be a hell of a lot easier now
    # noinspection PyUnboundLocalVariable
    liara = Liara('!', shard_id=cargs.shard_id, shard_count=cargs.shard_count, description=cargs.description,
                  self_bot=cargs.selfbot, pm_help=None, max_messages=message_cache,
                  redis=redis_conn, cargs=cargs, test=cargs.test)  # liara-specific args

    async def run_bot():
        await liara.login(cargs.token, bot=not (cargs.selfbot or userbot))
        await liara.connect()

    # noinspection PyBroadException
    def run_app():
        loop = asyncio.get_event_loop()
        exit_code = 0
        if cargs.test:
            logger.info('Liara is in test mode, flushing database...')
            liara.redis.flushdb()
        try:
            loop.run_until_complete(run_bot())
        except KeyboardInterrupt:
            logger.info('Shutting down threads and quitting. Thank you for using Liara.')
            loop.run_until_complete(liara.logout())
        except Exception:
            exit_code = 1
            logger.exception()
            loop.run_until_complete(liara.logout())
        finally:
            loop.close()
            if cargs.test:
                liara.redis.flushdb()
            return exit_code

    exit(run_app())
