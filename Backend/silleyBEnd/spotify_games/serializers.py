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
class ArtistGuessInputSerializer(serializers.Serializer):
    artist_name = serializers.CharField(max_length=255, required=True)
    
class ArtistGuessFeedbackSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
    guessed_value = serializers.CharField()
    
class ArtistGuessAttributesSerializer(serializers.Serializer):
    debut_year = serializers.DictField(child=ArtistGuessFeedbackSerializer())
    birth_year = serializers.DictField(child=ArtistGuessFeedbackSerializer())
    num_albums = serializers.DictField(child=ArtistGuessFeedbackSerializer())
    members_count = serializers.DictField(child=ArtistGuessFeedbackSerializer())
    gender = serializers.DictField(child=ArtistGuessFeedbackSerializer())
    popularity = serializers.DictField(child=ArtistGuessFeedbackSerializer())
    country = serializers.DictField(child=ArtistGuessFeedbackSerializer())
    genre = serializers.DictField(child=ArtistGuessFeedbackSerializer())
    
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