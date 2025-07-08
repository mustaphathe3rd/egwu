from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework import authentication
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.template.exceptions import TemplateDoesNotExist
from django.http import HttpResponseServerError
from .models import GameSession, GameStatistics, GameLeaderboard
from .serializers import GameSessionSerializer, ArtistGuessInputSerializer, GuessResponseSerializer, GameStateSerializer
from .services.cache_service import GameCacheService
import logging
from .permission import ValidSpotifyTokenRequired, IsGameSessionOwner
from .game_modes.lyrics_game import LyricsGame
from .game_modes.artist_guess import ArtistGuessGame
from .game_modes.crossword import CrosswordGame
from .game_modes.trivia import TriviaGame
#from .authentication import CompositeAuthentication
from datetime import datetime
from django.utils import timezone
from django.core.exceptions import ValidationError
from .monitoring import GameAnalytics, GameEvent
from .exceptions import *
from .services.analytics_service import AnalyticsService
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from spotify.models import SpotifyToken
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator


logger = logging.getLogger("spotify_games")

@method_decorator(ensure_csrf_cookie, name='dispatch')
class GameSessionViewSet(viewsets.ModelViewSet):
    queryset = GameSession.objects.all()
    serializer_class = GameSessionSerializer
    #authentication_classes = [CompositeAuthentication]
    permission_classes = [IsAuthenticated]
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
        permissions = super().get_permissions()
        if self.action in ['retrieve', 'submit_answer', 'get_hint','submit_guess','search_artists']:
            permissions.append(IsGameSessionOwner())
        return permissions
    
    @action(detail=False, methods=['post'])
    def start_game(self, request):
        game_type = request.data.get('game_type')
        logger.debug(f"Attempting to start game of type: {game_type}")
        
        if not game_type:
            logger.error("No game type provided")
            return Response(
                {'error': 'Game type is required'},
                status = status.HTTP_400_BAD_REQUEST
            )    
        
        if game_type not in self.GAME_TYPES:
            logger.error(f"Invalid game type: {game_type}")
            return Response(
                {'error': 'Invalid game type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        spotify_token = SpotifyToken.objects.filter(user=request.user).first()
        if not spotify_token or not spotify_token.is_valid():
            logger.error("No valid Spotify token found")
            return Response(
                {'error': 'Valid Spotify token required'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        try:
            # Create new session
            session = GameSession.objects.create(
                user=request.user,
                game_type= game_type, 
            )
            
            # Initialize game
            game = self._get_game_instance(session)
            initial_state = game.initialize_game()
            
            logger.debug(f"Initial State: {initial_state}")
        
            # Prepare response data
            response_data = {
                'session': GameSessionSerializer(session).data,
            }
            
            logger.debug(f"serializer response data: {response_data}")
        
            # Track game start - Create a GameEvent instance instead of a dict
            game_event = GameEvent(
                event_type='game_start',
                user_id=request.user.id,
                game_type=game_type,
                timestamp=datetime.now(),
                metadata={'session_id': session.id}
            )
            
            self.analytics.track_event(game_event)

            return Response(response_data)
        
        except GameInitializationError as e:
            logger.error(f"Game initialization failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    @action(detail=True, methods=['post'],url_path='submit-answer')
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
            current_state = self.cache_service.get_game_session(
                session.id,
                session.game_type
            )
            
            if not current_state:
                return Response(
                    {'error':'Game state not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            answer = request.data.get('answer')
            if not answer or not isinstance(answer, str):
                return Response(
                    {'error': 'Answer is required'},
                    status = status.HTTP_400_BAD_REQUEST
                )
                
            game = self._get_game_instance(session)
            result = game.validate_answer({'answer': answer})
            
            # Update cache with new state
            # updated_state = {
            #     'session': GameSessionSerializer(session).data,
            #     'current_state': game.get_current_state()
            # }
            
            # self.cache_service.cache_game_session(
            #     session.id,
            #     session.game_type,
            #     updated_state
            # )
            
            # Track answer submission
            self.analytics.track_event(GameEvent(
                event_type= 'answer_submission',
                user_id= request.user.id,
                game_type= session.game_type,
                timestamp= datetime.now(),
                metadata= {
                    'session_id': session.id,
                    'is_correct': result.get('is_correct', False)
                }
            ))
            
            return Response(result)
        
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
        
    @action(detail= True, methods=['post'], parser_classes=[MultiPartParser])
    def submit_voice_answer(self, request, pk=None):
        """Submit a voice recording answer for lyrics game."""
        session = self.get_object()
        
        if session.game_type != 'lyrics_voice':
            return Response(
                {'error': 'This endpoint is only for lyrics voice mode'},
                status= status.HTTP_400_BAD_REQUEST
            )
        
        if session.completed:
            return Response(
                {'error': 'Game session already completed'},
                status=status.HTTP_400_BAD_REQUEST
                )       
        
        try:
            audio_file = request.FILES.get('audio')
            if not audio_file:
                return Response(
                    {'error': 'Audio file is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            game = self._get_game_instance(session)
            result = game.validate_voice_answer(audio_file.read())
            
            # Update cache with new state
            updated_state = {
                'session' : GameSessionSerializer(session).data,
                'current_state': result
            }
            
            self.cache_service.cache_game_session(
                request.session.id,
                session.game_type,
                updated_state
            )
            
            # Track voice answer submission
            self.analytics.track_event({
                'event_type': 'voice_answe_submission',
                'user_id': request.user.id,
                'game_type': 'lyrics_voice',
                'timestamp': datetime.now(),
                'metadata': {
                    'session_id': session.id,
                    'is_correct': result.get('is_correct', False),
                    'confidence': result.get('confidence', 0)
                }
            })
            
            return Response(updated_state)
        
        except GameError as e:
            logger.error(f"Error processing voice answer: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )                
    @action(detail=True, methods=['post'])
    def submit_guess(self, request, pk=None):
        """Submit a guess for the guess_artist game mode."""
        session = self.get_object()

        game_type = session.game_type
        if game_type != 'guess_artist':
            return Response(
                {'error': 'This endpoint is only for guess_artist mode'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if session.completed:
            return Response(
                {'error': 'Game session already completed'},
                status=status.HTTP_400_BAD_REQUEST
                )
    
        # validate input
        input_serializer = ArtistGuessInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
            
        try:    
            # Get current game state from cache
            current_state = self.cache_service.get_game_session(
                session.id,
                game_type,
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
            
            # retrueve updated game state
            game_state = session.gamestate.first().current_state
            
            response_data = {
                "state": game_state,
                "feedback": feedback
            }
            
            self.cache_service.cache_game_session(
                session.id,
                game_type,
                game_state,
            )
            
            # Track guess submission
            self.analytics.track_event(GameEvent(
                event_type='guess_submission',
                user_id=request.user.id,
                game_type='guess_artist',
                timestamp=datetime.now(),
                metadata={
                    'session_id': session.id,
                    'is_correct': feedback['is_correct'],
                    'tries': session.current_tries
                }
            ))
                        
            return Response(response_data)
    
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
    
    @action(detail=True, methods=['post'], url_path='restart-game')
    def restart_game(self, request, pk=None):
        """Restart the current game session."""
        try:
            session = self.get_object()
            
            if session.user != request.user:
                return Response(
                    {'error': 'You do not have permission to restart this game.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            game = self._get_game_instance(session)
            # This function correctly resets the DB and returns the new state
            new_game_state = game.restart_game()
            
            # =======================================================
            # THE FIX IS HERE
            # Instead of serializing the old session, we will directly
            # return the fresh game state in the expected format.
            # =======================================================
            response_data = {
                "state": new_game_state
            }
            
            return Response(response_data, status=status.HTTP_200_OK)

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
    
    @action(detail=False, methods=['get'])
    def state(self, request, pk=None):
        """Direct state endpoint for debugging"""
        session = self.get_object()
        game_state = session.gamestate.first()
        if not game_state or not game_state.current_state:
            return Response({'error': 'State not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(game_state.current_state)