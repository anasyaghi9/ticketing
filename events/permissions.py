from rest_framework import permissions


class IsOrganizer(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == "organizer")


class IsEventOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.organizer_id == request.user.id