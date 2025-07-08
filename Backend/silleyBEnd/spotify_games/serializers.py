from rest_framework import serializers
from .models import GameSession, GamePlayback

class FlexibleCharField(serializers.CharField):
    def to_internal_value(self, data):
        # If data is an int, convert it to a string.
        if isinstance(data, int):
            data = str(data)
        return super().to_internal_value(data)

class GamePlaybackSerializer(serializers.ModelSerializer):
    class Meta:
        model = GamePlayback
        fields = ['spotify_track_id','track_name', 'artist_name', 
                  'album_image_url', 'preview_url']
        
class GameSessionSerializer(serializers.ModelSerializer):
    playback = GamePlaybackSerializer(read_only=True)
    state = serializers.SerializerMethodField()
        
    class Meta:
        model = GameSession
        fields = ['id', 'game_type', 'start_time', 'end_time', 'score',
                  'max_tries','current_tries','completed', 'playback', 'state']

    def get_state(self, obj):
        """Fetch game state from related GameState model"""
        game_state = obj.gamestate.first()
        if game_state and game_state.current_state:
            # Directly return the stored JSON state
            return game_state.current_state
        return None
class ArtistGuessInputSerializer(serializers.Serializer):
    artist_name = serializers.CharField(max_length=255, required=True)
    
class GameDataSerializer(serializers.Serializer):
    """Serializer for game data component of the game state"""
    artist_id = serializers.CharField(read_only=True)
    revealed_info = serializers.DictField(read_only=True)
    guesses = serializers.ListField(child=serializers.DictField(), read_only=True, required=False)
    target_artist = serializers.DictField(read_only=True, required=False)
    
class SessionStateSerializer(serializers.Serializer):
    """Serializer for session state component of the game state"""
    tries_left = serializers.IntegerField(read_only=True)
    tries_used = serializers.IntegerField(read_only=True)
    is_complete = serializers.BooleanField(read_only=True)
    score = serializers.IntegerField(read_only=True)
    
class UIStateSerializer(serializers.Serializer):
    """Serializer for UI state component of the game state"""
    loading = serializers.BooleanField(read_only=True)
    error = serializers.CharField(read_only=True,allow_null=True, required=False)
    current_view = serializers.CharField(read_only=True)
    
class GameStateSerializer(serializers.Serializer):
    """Complete game state serializer"""
    game_data = GameDataSerializer(read_only=True)
    session_state = SessionStateSerializer(read_only=True)
    ui_state = UIStateSerializer(read_only=True)

class GuessResponseSerializer(serializers.Serializer):
    state = GameStateSerializer()
    feedback = serializers.DictField()
 
class SessionStateSerializer(serializers.Serializer):
    """Serializer for session state component of the game state"""
    tries_left = serializers.IntegerField()
    tries_used = serializers.IntegerField()
    is_complete = serializers.BooleanField()
    score = serializers.IntegerField()
    


