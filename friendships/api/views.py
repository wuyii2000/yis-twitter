from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from friendships.models import Friendship
from friendships.api.serializers import (
    FollowerSerializer,
    FollowingSerializer,
    FriendshipSerializerForCreate,
)
from django.contrib.auth.models import User
from friendships.api.paginations import FriendshipPagination


class FriendshipViewSet(viewsets.GenericViewSet):
    serializer_class = FriendshipSerializerForCreate
    queryset = User.objects.all()

    pagination_class = FriendshipPagination

    @action(methods=['GET'], detail=True, permission_classes=[AllowAny])
    def followers(self, request, pk):
        # GET /api/friendships/uid/followers/
        friendships = Friendship.objects.filter(to_user_id=pk).order_by('-created_at')
        page = self.paginate_queryset(friendships)
        serializer = FollowerSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(methods=['GET'], detail=True, permission_classes=[AllowAny])
    def followings(self, request, pk):
        friendships = Friendship.objects.filter(from_user_id=pk).order_by('-created_at')
        page = self.paginate_queryset(friendships)
        serializer = FollowingSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(methods=['POST'], detail=True, permission_classes=[IsAuthenticated])
    def follow(self, request, pk):
        follow_user = self.get_object()
        if Friendship.objects.filter(from_user=request.user, to_user=pk).exists():
            return Response({
                'success': True,
                'duplicate': True,
            }, status=status.HTTP_201_CREATED)
        serializer = FriendshipSerializerForCreate(data={
            'from_user_id': request.user.id,
            'to_user_id': follow_user.id,
        })
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)
        instance = serializer.save()
        return Response(
            FollowingSerializer(instance, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(methods=['POST'], detail=True, permission_classes=[IsAuthenticated])
    def unfollow(self, request, pk):
        unfollow_user = self.get_object()
        # pk is of str type, need conversion
        if request.user.id == unfollow_user.id:
            return Response({
                'success': False,
                'message': 'You cannot unfollow yourself',
            }, status=status.HTTP_400_BAD_REQUEST)
        # https://docs.djangoproject.com/en/3.1/ref/models/querysets/#delete
        # Queryset 的 delete 操作返回两个值，一个是删了多少数据，一个是具体每种类型删了多少
        # 为什么会出现多种类型数据的删除？因为可能因为 foreign key 设置了 cascade 出现级联
        # 删除，也就是比如 A model 的某个属性是 B model 的 foreign key，并且设置了
        # on_delete=models.CASCADE, 那么当 B 的某个数据被删除的时候，A 中的关联也会被删除。
        # 所以 CASCADE 是很危险的，我们一般最好不要用，而是用 on_delete=models.SET_NULL
        # 取而代之，这样至少可以避免误删除操作带来的多米诺效应。
        deleted, _ = Friendship.objects.filter(
            from_user=request.user,
            to_user=unfollow_user,
        ).delete()
        return Response({'success': True, 'deleted': deleted})

    def list(self, request):
        return Response({'message': 'this is friendship page'})
