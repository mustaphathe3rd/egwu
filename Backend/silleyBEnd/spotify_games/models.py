from django.db import models
from spotify.models  import User, MostListenedArtist, MostListenedSongs

class GameSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game_type = models.CharField(max_length=50)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    score = models.IntegerField(default=0)
    max_tries = models.IntegerField(default=10)
    current_tries = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'spotify_games'
        
class GamePlayback(models.Model):
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE)
    spotify_track_id = models.CharField(max_length=255)
    track_name = models.CharField(max_length=255)
    artist_name = models.CharField(max_length=255)
    album_image_url = models.URLfield()
    preview_url = models.URLField(null=True, blank=True)
        
# class GameState(models.Model):
#     session = models.ForeignKey(GameSession, on_delete=models.CASCADE)
#     current_state = models.JSONField()
#     last_updated = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         app_label = 'spotify_games'

class UserGameStats(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    total_score = models.IntegerField(default=0)
    games_played = models.IntegerField(default=0)
    favorite_game = models.CharField(max_length=50, null=True)
    highest_streak = models.IntegerField(default=0)