from rest_framework import permissions

class IsSpotifyAuthenticated(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
    
class IsGameSessionOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user