from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import GameSession
from .serializers import GameSessionSerializer, GameStateSerializer
from .permission import IsSpotifyAuthenticated, IsGameSessionOwner
from .game_modes.lyrics_game import LyricsGame
from .game_modes.artist_guess import ArtistGuessGame
from .game_modes.crossword import CrosswordGame
from .game_modes.trivia import TriviaGame
from .authentication import SpotifyTokenAuthentication

class GameSessionViewSet(viewsets.ModelViewSet):
    queryset = GameSession.objects.all()
    serializer_class = GameSessionSerializer
    authentication_classes = [SpotifyTokenAuthentication]
    permission_classes = [IsAuthenticated, IsSpotifyAuthenticated]
    
    def get_permissions(self):
        if self.action in ['retrieve', 'submit_answer', 'get_hint']:
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
            
        # Create new session
        session = GameSession.objects.create(
            user=request.user,
            game_type= game_type,
            max_tries=10 if game_type =='guess_artist' else 1
        )
        
        # Initialize game
        game = self._get_game_instance(session)
        if not game:
            session.delete()
            return Response(
                {'error': 'Invalid game type'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        initial_state = game.initialize_game()
        
        # Serialize response
        serializer = GameStateSerializer(data={
            'session': GameSessionSerializer(session).data,
            'current_state': initial_state
        })
        serializer.is_valid(raise_exception=True)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def submit_answer(self, request, pk=None):
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
        session = self.get_object()
        if session.game_type != 'guess_artist':
            return Response(
                {'error': 'Hints are only available for guess artist mode'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        game = self._get_game_instance(session)
        hint = get.get_next_hint()
        
        return Response({'hint: hint'})
    
    def _get_game_instance(self, session):
        game_types = {
            'lyrics_text': LyricsGame,
            'lyrics_voice': LyricsGame,
            'guess_artist': ArtistGuessGame,
            'crossword': CrosswordGame,
            'trivia': TriviaGame
        }
        
        game_class = game_types.get(session.game_type)
        return game_class(session) if game_class else None