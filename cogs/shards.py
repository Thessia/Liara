from discord.ext import commands
import threading
import json
import time
import datetime
import discord


class Shards:
    def __init__(self, liara):
        self.liara = liara
        self.redis = self.liara.redis
        self.die = False
        if liara.shard_id is not None:
            publish_loop = threading.Thread(target=self.publish_loop_thread)
            publish_loop.start()
            subscribe_loop = threading.Thread(target=self.subscribe_loop_thread)
            subscribe_loop.start()
        self.shards = {}

    def __unload(self):
        self.die = True

    def publish_loop_thread(self):
        while not self.die:
            self.redis.publish('shard.{0}'.format(self.liara.shard_id),
                               json.dumps({'servers': len(self.liara.servers),
                                           'members': len([x for x in self.liara.get_all_members()]),
                                           'boot_time': self.liara.boot_time}))
            time.sleep(1)

    def subscribe_loop_thread(self):
        pubsub = self.redis.pubsub()
        pubsub.psubscribe('shard.*')
        for i in pubsub.listen():
            if self.die:
                pubsub.close()
                return
            if i['type'] == 'pmessage':
                self.shards[i['channel'].decode()] = json.loads(i['data'].decode())

    @commands.command()
    async def shardinfo(self):
        """Gets Liara's shards' info."""
        if self.liara.shard_id is not None:
            embed = discord.Embed()
            for shard in sorted(self.shards):
                formatted = '**Servers:** {0}\n**Members:** {1}\n' \
                            '**Boot time:** {2}'.format(self.shards[shard]['servers'], self.shards[shard]['members'],
                                                        datetime.datetime.fromtimestamp(
                                                        self.shards[shard]['boot_time']))

                embed.add_field(name=shard, value=formatted)
            await self.liara.say('I am shard {} of {}.'.format(self.liara.shard_id + 1, self.liara.shard_count), embed=embed)
        else:
            await self.liara.say('I am not sharded.')


def setup(liara):
    liara.add_cog(Shards(liara))
