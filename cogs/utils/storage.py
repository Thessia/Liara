import typing

import aredis
import dill


class _Nonexistant:
    pass


class RedisCollection:
    __slots__ = ('redis', 'key')

    def __init__(self, redis: aredis.StrictRedis, key):
        self.redis = redis
        self.key = key

    async def __aiter__(self):
        keys = await self.keys()
        for key in keys:
            yield key

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
        _keys = await self.redis.hkeys(self.key)
        return [dill.loads(x) for x in _keys]

    async def to_dict(self) -> dict:
        """Returns the collection as a Python dictionary."""
        res = await self.redis.hgetall(self.key)
        out = {}
        for key, value in dict(res).items():
            out[dill.loads(key)] = dill.loads(value)
        return out
