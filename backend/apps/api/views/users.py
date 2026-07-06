from rest_framework import mixins, viewsets

from apps.api.permissions import ADMIN_PERMISSIONS
from apps.api.serializers import UserSerializer
from apps.domain.models import User


class UserViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = User.objects.order_by("email")
    serializer_class = UserSerializer
    permission_classes = ADMIN_PERMISSIONS
