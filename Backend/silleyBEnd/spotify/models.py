from django.db import models
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging
from .constants import SCOPE
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import make_password
import uuid
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

# Create your models here.

logger = logging.getLogger('spotify')

class User(AbstractUser):
    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True
    )
    spotify_id = models.CharField(max_length=255, null=True, blank=True)    
    display_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(unique=True, null=True)
    country = models.CharField(max_length=3, null=True, blank=True, default='US')
    last_updated = models.DateTimeField(null=True, blank=True, auto_now=True)
    is_active = models.BooleanField(default=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = f"user_{uuid.uuid4().hex[:8]}"
        if not self.password:
            self.password = make_password(None)
        super().save(*args, **kwargs)
    
    def __str__(self) -> str:
        return f"{self.display_name or self.email}"
    
class MostListenedSongs(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    spotify_id =models.CharField(max_length=255,unique=True)
    name = models.CharField(max_length=255)
    genres = models.TextField(max_length=255, blank=True,null=True)
    artist = models.CharField(max_length=255)
    album = models.CharField(max_length=255)
    release_date = models.DateField(null=True, blank=True)
    duration_seconds = models.FloatField()
    popularity = models.IntegerField(default=0)
    lyrics = models.TextField(blank=True, null=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)
    track_uri = models.CharField(max_length=500, null=True, blank=True)
    
    
    
    def __str__(self):
        return self.name
    
class MostListenedArtist(models.Model):
    spotify_id = models.CharField(max_length=255, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    popularity = models.IntegerField(default=0)
    genres = models.TextField(default=None)
    followers = models.IntegerField(default=0)
    debut_year = models.IntegerField(null=True, blank=True)
    birth_year = models.IntegerField(null=True, blank=True)
    num_albums = models.IntegerField(null=True, blank=True)
    members = models.IntegerField(null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)
    gender = models.CharField(max_length=255, null=True, blank=True)
    most_popular_song = models.CharField(max_length=255, null=True, blank=True)
    most_popular_song_id = models.CharField(max_length=255, null=True)
    most_popular_track_uri = models.CharField(max_length=255, null=True, blank=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)
    biography = models.TextField(blank=True, null=True)
    
  
    
    def __str__(self) -> str:
        return f"{self.name}"
    
class MostListenedAlbum(models.Model):
    spotify_id = models.CharField(max_length = 255, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, default="Unknown Artist")
    artists = models.CharField(max_length=255)
    release_date = models.DateField(null=True, default=timezone.now)
    total_tracks = models.IntegerField(default=0)
    image_url = models.URLField(max_length=500, null=True, blank=True)
    
   
    
    def __str__(self) -> str:
        return f"{self.name}"
    
class SpotifyToken(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='spotify_token'
    )
    access_token = models.CharField(max_length=1024)
    refresh_token = models.CharField(max_length=1024, null=True, blank=True)
    expires_at = models.DateTimeField()
    
    def is_expired(self, buffer_time=300):
        if not self.expires_at:
            logger.warning(f"No expiry timee set for token {self.id}")
            return True
        
        now = timezone.now()
        #Add buffer time to ensure token refresh before actual expiry
        is_expired = self.expires_at - timedelta(seconds=buffer_time) <= now
        
        if is_expired:
            logger.info(f"Token {self.id} expired at {self.expires_at}")
            
        return is_expired
    
    def refresh(self):
        """Refresh the Spotify access token using the refresh token."""
        if not self.refresh_token:
            logger.error(f"No refresh token available for user {self.user.id}")
            raise ValueError("No refresh token available")
            
        try:
            sp_oauth = SpotifyOAuth(
                client_id=settings.SPOTIFY_CLIENT_ID,
                client_secret=settings.SPOTIFY_CLIENT_SECRET,
                redirect_uri=settings.SPOTIFY_REDIRECT_URI,
                scope=SCOPE
            )
            
            token_info = sp_oauth.refresh_access_token(self.refresh_token)
            
            if token_info:
                self.access_token = token_info['access_token']
                if token_info.get('refresh_token'):
                    self.refresh_token = token_info['refresh_token']
                self.expires_at = timezone.now() + timedelta(seconds=token_info['expires_in'])
                self.save()
                
            return self.access_token
        except Exception as e:
            logger.error(f"Error refreshing token for user {self.user.id}: {str(e)}")
            raise