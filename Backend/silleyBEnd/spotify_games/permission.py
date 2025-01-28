from rest_framework import permissions
from spotify.models import SpotifyToken
from rest_framework.permissions import BasePermission

class ValidSpotifyTokenRequired(BasePermission):
    """Permission class instead of auth class"""
    def has_permission(self, request, view):
        try:
            token = SpotifyToken.objects.get(user=request.user)
            if token.is_expired():
                if token.refresh_token:
                    token.refresh()
                    return True
                return False
            return True
        except SpotifyToken.DoesNotExist:
            return False
        
class IsGameSessionOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user