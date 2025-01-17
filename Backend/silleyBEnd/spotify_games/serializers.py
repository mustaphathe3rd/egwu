from rest_framework import serializers
from .models import GameSession, GamePlayback

class GamePlaybackSerializer(serializers.ModelSerializer):
    class Meta:
        model = GamePlayback
        fields = ['spotify_track_id','track_name', 'artist_name', 
                  'album_image_url', 'preview_url']
        
class GameSessionSerializer(serializers.ModelSerializer):
    playback = GamePlaybackSerializer(read_only=True)
        
    class Meta:
        model = GameSession
        fields = ['id', 'game_type', 'start_time', 'end_time', 'score',
                  'max_tries','current_tries','completed', 'playback']
        
class GameStateSerializer(serializers.Serializer):
    session = GameSessionSerializer()
    current_state = serializers.JSONField()
    metadata = serializers.DictField(required=False)
    
    