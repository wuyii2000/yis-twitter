from friendships.services import FriendshipService
from newsfeeds.models import NewsFeed, HBaseNewsFeed
from utils.redis_helper import RedisHelper
from twitter.cache import USER_NEWSFEEDS_PATTERN
from newsfeeds.tasks import fanout_newsfeeds_main_task
from gatekeeper.models import GateKeeper
from utils.redis_serializer import DjangoModelSerializer, HBaseModelSerializer


def lazy_load_newsfeeds(user_id):
    def _lazy_load(limit):
        if GateKeeper.is_switch_on('switch_newsfeed_to_hbase'):
            return HBaseNewsFeed.filter(prefix=(user_id, ), limit=limit, reverse=True)
        return NewsFeed.objects.filter(user_id=user_id).order_by('-created_at')[:limit]
    return _lazy_load


class NewsFeedService(object):

    @classmethod
    def fanout_to_followers(cls, tweet):
        # 这句话的作用是，在 celery 配置的 message queue 中创建一个 fanout 的任务
        # 参数是 tweet。任意一个在监听 message queue 的 worker 进程都有机会拿到这个任务
        # worker 进程中会执行 fanout_newsfeeds_task 里的代码来实现一个异步的任务处理
        # 如果这个任务需要处理 10s 则这 10s 会花费在 worker 进程上，而不是花费在用户发 tweet
        # 的过程中。所以这里 .delay 操作会马上执行马上结束从而不影响用户的正常操作。
        # （因为这里只是创建了一个任务，把任务信息放在了 message queue 里，并没有真正执行这个函数）
        # 要注意的是，delay 里的参数必须是可以被 celery serialize 的值，因为 worker 进程是一个独立
        # 的进程，甚至在不同的机器上，没有办法知道当前 web 进程的某片内存空间里的值是什么。所以
        # 我们只能把 tweet.id 作为参数传进去，而不能把 tweet 传进去。因为 celery 并不知道
        # 如何 serialize Tweet。
        if not GateKeeper.is_switch_on('switch_newsfeed_to_hbase'):
            created_at = tweet.created_at
        else:
            created_at = tweet.timestamp
        fanout_newsfeeds_main_task.delay(tweet.id, created_at, tweet.user_id)

    @classmethod
    def get_cached_newsfeeds(cls, user_id):
        if GateKeeper.is_switch_on('switch_newsfeed_to_hbase'):
            serializer = HBaseModelSerializer
        else:
            serializer = DjangoModelSerializer
        key = USER_NEWSFEEDS_PATTERN.format(user_id=user_id)
        return RedisHelper.load_objects(key, lazy_load_newsfeeds(user_id), serializer)

    @classmethod
    def push_newsfeed_to_cache(cls, newsfeed):
        key = USER_NEWSFEEDS_PATTERN.format(user_id=newsfeed.user_id)
        RedisHelper.push_object(key, newsfeed, lazy_load_newsfeeds(newsfeed.user_id))

    @classmethod
    def create(cls, **kwargs):
        if GateKeeper.is_switch_on('switch_newsfeed_to_hbase'):
            newsfeed = HBaseNewsFeed.create(**kwargs)
            # 需要手动触发 cache 更改，因为没有 listener 监听 hbase create
            cls.push_newsfeed_to_cache(newsfeed)
        else:
            newsfeed = NewsFeed.objects.create(**kwargs)
        return newsfeed

    @classmethod
    def batch_create(cls, batch_params):
        if GateKeeper.is_switch_on('switch_newsfeed_to_hbase'):
            newsfeeds = HBaseNewsFeed.batch_create(batch_params)
        else:
            newsfeeds = [NewsFeed(**params) for params in batch_params]
            NewsFeed.objects.bulk_create(newsfeeds)
        for newsfeed in newsfeeds:
            NewsFeedService.push_newsfeed_to_cache(newsfeed)
        return newsfeeds

    @classmethod
    def count(cls, user_id=None):
        if GateKeeper.is_switch_on('switch_newsfeed_to_hbase'):
            return len(HBaseNewsFeed.filter(prefix=(user_id,)))
        if user_id is None:
            return NewsFeed.objects.count()
        return NewsFeed.objects.filter(user_id=user_id).count()
