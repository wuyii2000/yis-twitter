from comments.models import Comment
from django.contrib.auth.models import User
from django.test import TestCase as DjangoTestCase
from rest_framework.test import APIClient
from tweets.models import Tweet
from django.contrib.contenttypes.models import ContentType
from likes.models import Like
from newsfeeds.models import NewsFeed
from django.core.cache import caches
from utils.redis_client import RedisClient
from friendships.services import FriendshipService
from django_hbase.models import HBaseModel
from gatekeeper.models import GateKeeper
from newsfeeds.services import NewsFeedService


class TestCase(DjangoTestCase):

    hbase_tables_created = False

    def setUp(self):
        self.clear_cache()
        try:
            self.hbase_tables_created = True
            for hbase_model_class in HBaseModel.__subclasses__():
                hbase_model_class.create_table()
        except Exception:
            self.tearDown()
            raise

    def tearDown(self):
        if not self.hbase_tables_created:
            return
        for hbase_model_class in HBaseModel.__subclasses__():
            hbase_model_class.drop_table()

    def clear_cache(self):
        caches['testing'].clear()
        RedisClient.clear()
        #GateKeeper.turn_on('switch_friendship_to_hbase')
        #GateKeeper.turn_on('switch_newsfeed_to_hbase')

    @property
    def anonymous_client(self):
        if hasattr(self, '_anonymous_client'):
            return self._anonymous_client
        self._anonymous_client = APIClient()
        return self._anonymous_client

    def create_user(self, username, email=None, password=None):
        if password is None:
            password = 'generic password'

        if email is None:
            email = '{}@gmail.com'.format(username)
        # 不能写成 User.objects.create()
        # 因为 password 需要被加密, username 和 email 需要进行一些 normalize 处理
        return User.objects.create_user(username, email, password)

    def create_tweet(self, user, content=None):
        if content is None:
            content = 'default tweet content'
        return Tweet.objects.create(user=user, content=content)

    def create_comment(self, user, tweet, content=None):
        if content is None:
            content = 'default comment content'
        return Comment.objects.create(user=user, tweet=tweet, content=content)

    def create_like(self, user, target):
        instance, _ = Like.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(target.__class__),
            object_id=target.id,
            user=user,
        )
        return instance

    def create_user_and_client(self, *args, **kwargs):
        user = self.create_user(*args, **kwargs)
        client = APIClient()
        client.force_authenticate(user)
        return user, client

    def create_newsfeed(self, user, tweet):
        if GateKeeper.is_switch_on('switch_newsfeed_to_hbase'):
            created_at = tweet.timestamp
        else:
            created_at = tweet.created_at
        return NewsFeedService.create(user_id=user.id, tweet_id=tweet.id, created_at=created_at)

    def create_friendship(self, from_user, to_user):
        return FriendshipService.follow(from_user.id, to_user.id)

