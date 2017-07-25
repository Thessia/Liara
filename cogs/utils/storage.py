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

    def _set(self, key):
        _key = dill.dumps(key)
        value = dill.dumps(super().__getitem__(key))
        if self.redis.hget(self.key, _key) == value:
            return
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

    def _pubsub_listener(self):
        self._ready.wait()
        pubsub = self.redis.pubsub()
        pubsub.subscribe([self.id])
        for message in pubsub.listen():
            if self.die:
                break
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

    def _check_closed(self):
        if self.die:
            raise RuntimeError('Unable to access closed RedisDict')

    def _ready_check(self):
        self._ready.wait()
        self._check_closed()

    def __getitem__(self, key):
        self._ready_check()
        return super().__getitem__(key)

    def __contains__(self, item):
        self._ready_check()
        return super().__contains__(item)

    def __delitem__(self, key):
        self._ready_check()
        self.redis.hdel(self.key, key)
        return super().__delitem__(key)

    def get(self, *args):
        self._ready_check()
        return super().get(*args)

    def keys(self):
        self._ready_check()
        return super().keys()

    def values(self):
        self._ready_check()
        return super().values()

    def items(self):
        self._ready_check()
        return super().items()

    def clear(self):
        self._ready_check()
        self.redis.delete(self.key)
        self.redis.publish(self.id, json.dumps({
            'origin': self.uuid,
            'action': 'clear'
        }))
        return super().clear()

    def commit(self, *keys: str):
        """
        Commits keys.
        :param keys: The keys to commit, if blank selects all
        """
        self._ready_check()
        if not keys:
            keys = super().keys()
        for key in keys:
            self._set(key)

    def close(self):
        """
        Closes the RedisDict.
        """
        self.die = True
