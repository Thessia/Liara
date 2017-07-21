import copy
import json
import threading
import time

import dill


class RedisDict(dict):
    def __init__(self, key, redis, pubsub_namespace='liara'):
        super().__init__()
        self.key = key
        self.redis = redis
        self.die = False
        self._ready = threading.Event()
        self._modified = {}
        db = str(self.redis.connection_pool.connection_kwargs['db'])
        self.id = '{}.{}.data.{}'.format(pubsub_namespace, db, key)
        self.uuid = hex(int(time.time() * 10 ** 7))[2:]
        threading.Thread(target=self._initialize, name='dataIO init thread for {}'.format(key), daemon=True).start()
        threading.Thread(target=self._pubsub_listener, name='dataIO pubsub thread for {}'.format(key),
                         daemon=True).start()

    def _initialize(self):
        self._pull()
        self._ready.set()
        threading.Thread(target=self._loop, name='dataIO loop thread for {}'.format(self.key), daemon=True).start()

    def _set(self, key):
        _key = dill.dumps(key)
        value = dill.dumps(super().__getitem__(key))
        self.redis.hset(self.key, _key, value)
        self.redis.publish(self.id, json.dumps({
            'origin': self.uuid,
            'action': 'get',
            'key': repr(_key)
        }))

    def _get(self, key):
        out = self.redis.hget(self.key, dill.dumps(key))
        return dill.loads(out) if out is not None else None

    def _pull(self):
        redis_copy = {dill.loads(k): dill.loads(v) for k, v in self.redis.hgetall(self.key).items()}
        super().clear()
        super().update(redis_copy)

    def _loop(self):
        while not self.die:
            for item in list(self):
                old = self._modified.get(item)
                try:
                    new = copy.deepcopy(super().get(item))
                except copy.Error:
                    new = super().get(item)

                if new != old:
                    try:
                        self._set(item)
                        self._modified[item] = new
                    except dill.PicklingError:
                        self._modified.pop(item, None)
            time.sleep(0.1)

    def _pubsub_listener(self):
        self._ready.wait()
        pubsub = self.redis.pubsub()
        pubsub.subscribe([self.id])
        for message in pubsub.listen():
            if message['type'] != 'message':
                continue
            message = json.loads(message['data'].decode())
            if message['origin'] == self.uuid:
                continue
            if message['action'] == 'get':
                key = dill.loads(eval(message['key']))
                super().__setitem__(key, self._get(key))
            if message['action'] == 'pull':
                self._pull()
            if message['action'] == 'clear':
                super().clear()

    def __del__(self):
        self.die = True

    def __getitem__(self, key):
        self._ready.wait()
        return super().__getitem__(key)

    def __contains__(self, item):
        self._ready.wait()
        return super().__contains__(item)

    def __setitem__(self, key, value):
        out = super().__setitem__(key, value)
        threading.Thread(target=lambda: self._set(key), name='dataIO setter thread for {}'.format(self.key),
                         daemon=True).start()
        return out

    def __delitem__(self, key):
        self._ready.wait()
        self.redis.hdel(self.key, key)
        return super().__delitem__(key)

    def get(self, *args):
        self._ready.wait()
        return super().get(*args)

    def clear(self):
        self._ready.wait()
        self.redis.delete(self.key)
        self.redis.publish(self.id, json.dumps({
            'origin': self.uuid,
            'action': 'clear'
        }))
        return super().clear()
