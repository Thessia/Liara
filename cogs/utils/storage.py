import json
import threading
import time
import typing

import aredis
import dill


class _Nonexistant:
    pass


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
        try:
            value = dill.dumps(super().__getitem__(key))
        except KeyError:
            value = _Nonexistant
        if value == _Nonexistant:
            self.redis.hdel(self.key, _key)
            self.redis.publish(self.id, dill.dumps({
                'origin': self.uuid,
                'action': 'pop',
                'key': key
            }))
            return
        if self.redis.hget(self.key, _key) == value:
            return
        self.redis.hset(self.key, _key, value)
        self.redis.publish(self.id, dill.dumps({
            'origin': self.uuid,
            'action': 'get',
            'key': key
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
            message = dill.loads(message['data'])
            if message['origin'] == self.uuid:
                continue
            if message['action'] == 'get':
                super().__setitem__(message['key'], self._get(message['key']))
            if message['action'] == 'pop':
                super().pop(message['key'], None)
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


class RedisCollection:
    def __init__(self, redis: aredis.StrictRedis, key):
        self.redis = redis
        self.key = key

    async def get(self, key, default=None) -> typing.Any:
        """Gets a key from the collection."""
        out = await self.redis.hget(self.key, dill.dumps(key))
        if out is None:
            return default
        return dill.loads(out)

    async def set(self, key, value):
        """Sets a key in the collection."""
        await self.redis.hset(self.key, dill.dumps(key), dill.dumps(value))

    async def delete(self, key):
        """Removes a key. Does nothing if the key doesn't exist."""
        await self.redis.hdel(self.key, dill.dumps(key))

    async def keys(self) -> typing.List[typing.Any]:
        """Lists all keys."""
        _keys = await self.redis.hkeys()
        return [dill.loads(x) for x in _keys]

    async def to_dict(self) -> dict:
        """Returns the collection as a Python dictionary."""
        res = await self.redis.hgetall()
        out = {}
        for key, value in dict(res).items():
            out[dill.loads(key)] = dill.loads(value)
        return out
