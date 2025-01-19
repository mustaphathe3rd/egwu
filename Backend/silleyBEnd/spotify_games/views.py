from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import GameSession
from .serializers import GameSessionSerializer, GameStateSerializer, ArtistGuessInputSerializer, GuessSubmissionResponseSerializer
from .services.cache_service import GameCacheService
import logging
from .permission import IsSpotifyAuthenticated, IsGameSessionOwner
from .game_modes.lyrics_game import LyricsGame
from .game_modes.artist_guess import ArtistGuessGame
from .game_modes.crossword import CrosswordGame
from .game_modes.trivia import TriviaGame
from .authentication import SpotifyTokenAuthentication
from datetime import datetime
from django.utils import timezone
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
class GameSessionViewSet(viewsets.ModelViewSet):
    queryset = GameSession.objects.all()
    serializer_class = GameSessionSerializer
    authentication_classes = [SpotifyTokenAuthentication]
    permission_classes = [IsAuthenticated, IsSpotifyAuthenticated]
    
    GAME_TYPES = {
        'lyrics_text': LyricsGame,
        'lyrics_voice': LyricsGame,
        'guess_artist': ArtistGuessGame,
        'crossword': CrosswordGame,
        'trivia': TriviaGame
    }
    
    def get_permissions(self):
        if self.action in ['retrieve', 'submit_answer', 'get_hint','submit_guess','search_artists']:
            return [IsAuthenticated(), IsGameSessionOwner()]
        return super().get_permissions()
    
    @action(detail=False, methods=['post'])
    def start_game(self, request):
        game_type = request.data.get('game_type')
        if not game_type:
            return Response(
                {'error': 'Game type is required'},
                status = status.HTTP_400_BAD_REQUEST
            )    
        
        if game_type not in self.GAME_TYPES:
            return Response(
                {'error': 'Invalid game type'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Create new session
        session = GameSession.objects.create(
            user=request.user,
            game_type= game_type,
            max_tries=10 if game_type =='guess_artist' else 1
        )
        
        # Initialize game
        try:    
            game = self._get_game_instance(session)
            initial_state = game.initialize_game()
        
            # Serialize response
            serializer = GameStateSerializer(data={
                'session': GameSessionSerializer(session).data,
                'current_state': initial_state
            })
            serializer.is_valid(raise_exception=True)
            
            return Response(serializer.data)
        except Exception as e:
            session.delete()
            return Response(
                {'error':str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    @action(detail=True, methods=['post'])
    def submit_answer(self, request, pk=None):
        """Submit an answer for the current game session."""
        session = self.get_object()
        if session.completed:
            return Response(
                {'error': 'Game session already completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        answer = request.data.get('answer')
        if not answer:
            return Response(
                {'error': 'Answer is required'},
                status = status.HTTP_400_BAD_REQUEST
            )
            
        game = self._get_game_instance(session)
        result = game.validate_answer(answer)
        
        serializer = GameStateSerializer(data={
            'session': GameSessionSerializer(session).data,
            'current_state': result
        })
        serializer.is_valid(raise_exception=True)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def get_hint(self, request, pk=None):
        """Get a hint for guess_artist game mode."""
        session = self.get_object()
        if session.game_type != 'guess_artist':
            return Response(
                {'error': 'Hints are only available for guess artist mode'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        game = self._get_game_instance(session)
        hint = game.get_next_hint()
        
        return Response({'hint': hint})
    
    def _get_game_instance(self, session):
        """Get the appropriate game instance based on session type."""
       
        game_class = self.GAME_TYPES.get(session.game_type)
        if not game_class:
            raise ValueError(f"Invalid game type: {session.game_type}")
        return game_class(session) if game_class else None
    
    
    @action(detail=True, methods=['post'])
    def submit_guess(self, request, pk=None):
        """Submit a guess for the guess_artist game mode."""
        session = self.get_object()
        if session.game_type != 'guess_artist':
            return Response(
                {'error': 'This endpoint is only for guess_artist mode'},
                status=Status.HTTP_400_BAD_REQUEST
            )
            
        # validate input
        input_serializer = ArtistGuessInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        
        game = self._get_game_instance(session)
        guess_artist_name = input_serializer.validated_dara['artist_name']
        
        if not guess_artist_name:
            return Response(
                {'error': 'Artist name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        feedback = game.validate_guess(guess_artist_name)
        
        if 'error' in feedback:
            return Response(feedback, status=status.HTTP_400_BAD_REQUEST)
        
        session.current_tries += 1
        if feedback['is_correct']:
            session.score += max(1, session.max_tries - session.current_tries)
            session.completed = True
            session.end_time = timezone.now()
        elif session.current_tries >= session.max_tries:
            session.completed = True
            session.end_time = timezone.now()
        session.save()
        
        response_data = {
            'feedback': feedback,
            'session_state': {
                'tries_left': session.max_tries - session.current_tries,
                'is_complete': session.completed, 
                'score': session.score
            }
        }
        
        # Validate response format
        response_serializer = GuessSubmissionResponseSerializer(data=response_data)
        response_serializer.is_valid(raise_exception=True)
        
        return Response(response_serializer.validated_data)  
          
    @action(detail=True, methods=['get'])
    def search_artists(self, request, pk=None):
        """Search artists for autocomplete in guess_artist mode."""
        session = self.get_object()
        
        if session.game_type != 'guess_artist':
            return Response(
                {'error': 'This endpoint is only for guess_artist mode'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        query = request.query_params.get('q', '')
        if not query:
            return Response(
                {'error': 'Search query is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        game = self._get_game_instance(session)
        artists = game.search_artists(query)
        
        return Response(list(artists))