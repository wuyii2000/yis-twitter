from rest_framework.permissions import BasePermission


class IsObjectOwner(BasePermission):
    """
    For detail = False action, only check has_permission
    For detail = True action, check has_permission & has_object_permission
    Default error message is IsObjectOwner.message
    """
    message = "You do not have permission to access this object"

    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        return request.user == obj.user
