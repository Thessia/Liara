import threading
import time
import pickle
import json
# noinspection PyUnresolvedReferences
import __main__


class RedisDict(dict):
    def __init__(self, key, redis):
        super().__init__()
        self.key = key
        self.redis = redis
        self.die = False
        self._ready = threading.Event()
        self._modified = {}
        db = str(self.redis.connection_pool.connection_kwargs['db'])
        self.id = 'liara.{}.data.{}'.format(db, key)
        threading.Thread(target=self._initialize, name='dataIO init thread for {}'.format(key), daemon=True).start()
        threading.Thread(target=self._pubsub_listener, name='dataIO pubsub thread for {}'.format(key),
                         daemon=True).start()
        self.uuid = hex(int(time.time() * 10 ** 7))[2:]

    def _initialize(self):
        self._pull()
        self._ready.set()
        threading.Thread(target=self._loop, name='dataIO loop thread for {}'.format(self.key), daemon=True).start()

    def _set(self, key):
        _key = pickle.dumps(key)
        value = pickle.dumps(super().__getitem__(key))
        self.redis.hset(self.key, _key, value)
        self.redis.publish(self.id, json.dumps({
            'origin': self.uuid,
            'action': 'get',
            'key': repr(_key)
        }))

    def _get(self, key):
        out = self.redis.hget(self.key, pickle.dumps(key))
        return pickle.loads(out) if out is not None else None

    def _pull(self):
        redis_copy = {pickle.loads(k): pickle.loads(v) for k, v in self.redis.hgetall(self.key).items()}
        super().clear()
        super().update(redis_copy)

    def _loop(self):
        while not self.die:
            for item in list(self):
                new = pickle.loads(pickle.dumps(super().get(item)))
                old = self._modified.get(item)

                if new != old:
                    try:
                        self._set(item)
                        self._modified[item] = new
                    except pickle.PickleError:
                        self._modified.pop(item, None)
            time.sleep(0.01)

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
                key = pickle.loads(eval(message['key']))
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


class dataIO:
    @staticmethod
    def save_json(filename, content):
        pass  # "oops"

    @staticmethod
    def load_json(filename):
        return RedisDict(key=filename, redis=__main__.redis_conn)


load_json = dataIO.load_json
load = load_json
