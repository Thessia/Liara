import redis_collections
import threading
import time
import json
import pickle
# noinspection PyUnresolvedReferences
import __main__


class RedisDict(redis_collections.Dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.die = False
        self.thread = threading.Thread(target=self.update_loop, daemon=True, name=kwargs['key'])
        self.thread.start()
        self.rthread = threading.Thread(target=self.refresh_loop, daemon=True, name=kwargs['key'])
        self.rthread.start()
        self.prev = None
        self.id = str(int(time.time() * 10000))  # make it unlikely that dataIO instances will collide
        db = str(self.redis.connection_pool.connection_kwargs['db'])
        self.pubsub_format = 'liara.{}.data.{}'.format(db, kwargs['key'])

    def update_loop(self):
        time.sleep(2)
        while not self.die:
            if self.prev != pickle.dumps(self.cache):
                self.prev = pickle.dumps(self.cache)
                self.sync()
                self.redis.publish(self.pubsub_format, json.dumps({
                    'instance': self.id, 'msg': 'update!'}))
                time.sleep(0.01)
            else:
                time.sleep(0.01)

    def refresh_loop(self):
        time.sleep(2)
        pubsub = self.redis.pubsub()
        pubsub.subscribe([self.pubsub_format])
        for message in pubsub.listen():
            if message['type'] != 'message':
                continue
            data = json.loads(message['data'].decode())
            if data['instance'] == self.id:
                continue
            if data['msg'] != 'update!':
                continue
            self.cache.clear()
            self.cache = dict(self)
            self.prev = pickle.dumps(self.cache)

    def __getitem__(self, item):
        try:
            return self.cache.__getitem__(item)
        except KeyError:
            return super().__getitem__(item)


class dataIO:
    @staticmethod
    def save_json(filename, content):
        pass  # "oops"

    @staticmethod
    def load_json(filename):
        return RedisDict(key=filename, redis=__main__.redis_conn, writeback=True)


load_json = dataIO.load_json
load = load_json
