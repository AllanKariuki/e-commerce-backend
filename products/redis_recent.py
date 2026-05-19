import time
# import settings
from django_redis import get_redis_connection

# Initialize Redis connection
def get_redis():
    return get_redis_connection('default')

RECENT_VIEW_PREFIX = 'recently_viewed'
MAX_ITEMS = 20
TTL_SECONDS = 30 * 24 * 60 * 60 # 30 days

def log_view(user_identifier: str, product_id: int):
    """
    Add product id to a sorted set for the user with timestamp as seconds.
    Keeps only the most recent MAX_ITEMS and set TTL.
    """

    r = get_redis()
    key=f"{RECENT_VIEW_PREFIX}:{user_identifier}"
    ts = int(time.time())
    pipe = r.pipeline()
    pipe.zadd(key, {str(product_id): ts}) # Use string members
    """
    Trim the sorted set to keep only the most recent MAX_ITEMS (highest scores). We store increasing timestamp.
    zremrangebyrank with 0...-N-1 removes older ones if we want to keep the last MAX_ITEMS.
    We'll remove by rank: keep only the MAX_ITEMS highest scores => remove 0..-(MAX_ITEMS-1)
    """
    pipe.zremrangebyrank(key, 0, -MAX_ITEMS-1) # remove older items
    pipe.expire(key, TTL_SECONDS)
    pipe.execute()

def get_recent_ids(user_identifier: str, limit: int = 10):
    """
    Return a list of product ids in most-recent-finds order (strings)
    """

    r = get_redis()
    key=f"{RECENT_VIEW_PREFIX}:{user_identifier}"
    # zrevrange returns highest score first -> most recent finds
    raw_ids = r.zrevrange(key, 0, limit - 1)

    ids = []
    for i in raw_ids:
        # handle bytes or strings safely
        if isinstance(i, bytes):
            i = i.decode()
        try:
            ids.append(int(i))
        except ValueError:
            # fallback: keep as strign if not an integer
            ids.append(i)
    return ids

    # return [int((i) for i in raw_ids)] if raw_ids else []
