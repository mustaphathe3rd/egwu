from django.db import models
from spotify.models  import User, MostListenedArtist, MostListenedSongs
from datetime import timedelta
class GameSession(models.Model):
    GAME_TYPE_CHOICES = [
        ('lyrics_text', 'Lyrics Text Mode'),
        ('lyrics_voice', 'Lyrics Voice Mode'),
        ('guess_artist, Artist Guess'),
        ('crossword', 'Crossword'),
        ('trivia', 'Trivia')
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game_type = models.CharField(max_length=50, choices = GAME_TYPE_CHOICES)
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
    album_image_url = models.URLField()
    spotify_uri = models.CharField(max_length=255, null=True)
        
class GameState(models.Model):
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name="gamestate")
    current_state = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)
    last_action = models.CharField(max_length=50, null=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['session', 'last_updated'])
        ]

    def update_state(self, new_state, action=None):
        if not isinstance(self.current_state, dict):
            self.current_state = {}
        self.current_state.update(new_state)
        if action:
            self.last_action = action
        self.save()
        
    def log_action(self, action, metadata=None):
        if metadata:
            if not isinstance(self.metadata, dict):
                self.metadata = {}
            self.metadata[action] = metadata
        self.last_action = action
        self.save()
        
class GameStatistics(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game_type = models.CharField(max_length=50)
    total_games = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)
    highest_score = models.IntegerField(default=0)
    average_score = models.FloatField(default=0.0)
    total_time_played = models.DurationField(default=timedelta())
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'game_type']
        
class GameLeaderboard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game_type = models.CharField(max_length=50)
    score = models.IntegerField()
    achieved_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['-score','game_type']),
        ]