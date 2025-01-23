from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import GameSession, GameStatistics, GameLeaderboard
from .serializers import GameSessionSerializer, ArtistGuessInputSerializer, GuessSubmissionResponseSerializer
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
from .monitoring import GameAnalytics
from .exceptions import *
from .services.analytics_service import AnalyticsService

logger = logging.getLogger("spotify_games")
class GameSessionViewSet(viewsets.ModelViewSet):
    queryset = GameSession.objects.all()
    serializer_class = GameSessionSerializer
    authentication_classes = [SpotifyTokenAuthentication]
    permission_classes = [IsAuthenticated, IsSpotifyAuthenticated]
    analytics = GameAnalytics()
    cache_service = GameCacheService()
    
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
        
        try:
            # Check for existing active session in cache
            cache_key = f"active-session:{request.user.id}:{game_type}"
            existing_session = self.cache_service.get_game_session(
                request.user.id,
                cache_key
            )  
            
            if existing_session:
                # Return cached session if it exists and is still valid
                return Response(existing_session)
            
            # Create new session
            session = GameSession.objects.create(
                user=request.user,
                game_type= game_type,
                max_tries=10 if game_type =='guess_artist' else 1
            )
            
            # Initialize game
            game = self._get_game_instance(session)
            initial_state = game.initialize_game()
        
            # Prepare response data
            response_data = {
                'session': GameSessionSerializer(session).data,
                'current_state': initial_state
            }
            
            #cache the new session
            self.cache_service.cache_game_session(
                request.user.id,
                cache_key,
                response_data,
                timeout=3600
            )
            
            # Track game start
            self.analytics.track_event({
                'event_type': 'game_start',
                'user_id': request.user.id,
                'game_type': game_type,
                'timestamp': datetime.now(),
                'metadata': {'session_id': session.id}
            })

            return Response(response_data)
        
        except GameInitializationError as e:
            logger.error(f"Game initialization failed: {str(e)}")
            return Response(
                {'error': str(e)},
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
        
        try: 
            # Get current game state from cache
            cache_key = f"game_state:{session.id}"
            current_state = self.cache_service.get_game_session(
                request.user.id,
                cache_key
            )
            
            if not current_state:
                return Response(
                    {'error':'Game state not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            answer = request.data.get('answer')
            if not answer:
                return Response(
                    {'error': 'Answer is required'},
                    status = status.HTTP_400_BAD_REQUEST
                )
                
            game = self._get_game_instance(session)
            result = game.validate_answer(answer)
            
            # Update cache with new state
            updated_state = {
                'session': GameSessionSerializer(session).data,
                'current_state': result
            }
            
            self.cache_service.cache_game_session(
                request.user.id,
                cache_key,
                updated_state
            )
            
            # Track answer submission
            self.analytics.track_event({
                'event_type': 'answer_submission',
                'user_id': request.user.id,
                'game_type': session.game_type,
                'timestamp': datetime.now(),
                'metadata': {
                    'session_id': session.id,
                    'is_correct': result.get('is_correct', False)
                }
            })
            
            return Response(updated_state)
        
        except GameError as e:
            logger.error(f"Error processing answer: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
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
            raise ValidationError(f"Invalid game type: {session.game_type}")
        
           # Verify session ownership before creating game instance
        if session.user != self.request.user:
            raise GameError("Unauthorized access to game session")
            
        return game_class(session)
        
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
            
        try:    
            # Get current game state from cache
            cache_key = f"artist_game:{session.id}"
            current_state = self.cache_service.get_game_session(
                request.user.id,
                cache_key
            )
            
            if not current_state:
                return Response(
                    {'error': 'Game state not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            game = self._get_game_instance(session)
            guess_artist_name = input_serializer.validated_data['artist_name']
            
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
            
            self.cache_service.cache_game_session(
                request.user.id,
                cache_key,
                response_data
            )
            
            # Track guess submission
            self.analytics.track_event({
                'event_type': 'guess_submission',
                'user_id': request.user.id,
                'game_type': 'guess_artist',
                'timestamp': datetime.now(),
                'metadata': {
                    'session_id': session.id,
                    'is_correct': feedback['is_correct'],
                    'tries': session.current_tries
                }
            })
            
            # Validate response format
            response_serializer = GuessSubmissionResponseSerializer(data=response_data)
            response_serializer.is_valid(raise_exception=True)
            
            return Response(response_serializer.validated_data)  
    
        except GameError as e:
            logger.error(f"Error processing guess: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )   
            
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
    
    @action(detail=True, methods=['post'])
    def restart_game(self, request, pk=None):
        """Restart the current game session."""
        try:
            old_session = self.get_object()
            
            # Create new session with same game type
            new_session = GameSession.objects.create(
                user=request.user,
                game_type=old_session.game_type,
                max_tries=old_session.max_tries
            )
            
            # Initialize new game
            game = self._get_game_instance(new_session)
            initial_state = game.initialize_game()
            
            return Response({
                'session': GameSessionSerializer(new_session).data,
                'state': initial_state
            })
        except GameError as e:
            logger.error(f"Error restarting game: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )   
            
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """Get leaderboard for a specific game type."""
        game_type = request.query_params.get('game_type')
        if not game_type:
            return Response(
                {'error': 'Game type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        top_scores = GameLeaderboard.objects.filter(
            game_type=game_type
        ).select_related('user').order_by('-score')[:100]

        return Response({
            'leaderboard': [{
                'username': score.user.username,
                'score': score.score,
                'achieved_at': score.achieved_at
            } for score in top_scores]
        })

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get user's game statistics."""
        analytics_service = AnalyticsService(request.user)
        stats = analytics_service.get_user_statistics()
        return Response(stats)