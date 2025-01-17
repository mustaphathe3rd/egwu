from django.db import models
from django.utils import timezone

# Create your models here.

class User(models.Model):
    spotify_id = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    country = models.CharField(max_length=3, null=True, blank=True, default='US')
    last_updated = models.DateTimeField(null=True, blank=True, auto_now=True)

    
    def _str_(self) -> str:
        return f"{self.display_name} email: {self.email}"
    
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
    display_url = models.URLField(max_length=500, null=True, blank=True)
    
    
    
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
    most_popular_song_url = models.URLField(max_length=255, null=True, blank=True)
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
    
