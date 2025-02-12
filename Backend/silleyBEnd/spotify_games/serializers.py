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
    current_state = serializers.SerializerMethodField()
        
    class Meta:
        model = GameSession
        fields = ['id', 'game_type', 'start_time', 'end_time', 'score',
                  'max_tries','current_tries','completed', 'playback', 'current_state']
    
    def get_current_state(self, obj):
        """Fetch game state from related GameState model"""
        game_state = obj.gamestate.first()
        if game_state:
            return game_state.current_state
        return None
class ArtistGuessInputSerializer(serializers.Serializer):
    artist_name = serializers.CharField(max_length=255, required=True)
    
class ArtistGuessFeedbackSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
    guessed_value = serializers.CharField()
    animation = FlexibleCharField()
class ArtistGuessAttributesSerializer(serializers.Serializer):
    debut_year = ArtistGuessFeedbackSerializer(required=False)
    birth_year = ArtistGuessFeedbackSerializer(required=False)
    num_albums = ArtistGuessFeedbackSerializer(required=False)
    members = ArtistGuessFeedbackSerializer(required=False)  # Note: using 'members' to match your data
    gender = ArtistGuessFeedbackSerializer(required=False)
    popularity = ArtistGuessFeedbackSerializer(required=False)
    country = ArtistGuessFeedbackSerializer(required=False)
    genres = ArtistGuessFeedbackSerializer(required=False)  # Note: using 'genres' (plural)

    def to_representation(self, instance):
        """Only include the keys we have defined, ignoring any extras."""
        ret = {}
        for field in self.fields:
            if field in instance:
                ret[field] = self.fields[field].to_representation(instance[field])
        return ret
class ArtistInfoSerializer(serializers.Serializer):
    name = serializers.CharField()
    image_url = serializers.URLField()
    favorite_song = serializers.DictField(required=False)
    
class GuessResponseSerializer(serializers.Serializer):
    attributes = ArtistGuessAttributesSerializer()
    is_correct = serializers.BooleanField()
    animation_effects = serializers.ListField(child=serializers.DictField())
    artist_info = ArtistInfoSerializer()
    target_artist = ArtistInfoSerializer(required=False)
    
class SessionStateSerializer(serializers.Serializer):
    tries_left = serializers.IntegerField()
    is_complete = serializers.BooleanField()
    score = serializers.IntegerField()
    
class GuessSubmissionResponseSerializer(serializers.Serializer):
    feedback = GuessResponseSerializer()
    session_state = SessionStateSerializer()
    revealed_info = serializers.DictField()