import os

import redis
from rq import Worker, Queue, Connection

# listen = ['high', 'default', 'low']

listen = ['lookups']

conn = redis.from_url(os.environ.get("REDIS_URL"))


if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()
