from .base import BaseGame
from spotify.models import MostListenedSongs, MostListenedArtist
from difflib import SequenceMatcher
from datetime import datetime
from django.db.models import Q
from ..services.cache_service import GameCacheService
from ..services.game_state import GameState
from ..exceptions import *
import logging

logger = logging.getLogger("spotify_games")

class ArtistGuessGame(BaseGame):
    def __init__(self, session):
        super().__init__(session)
        self.current_year = datetime.now().year
        self.cache_service = GameCacheService()
        
        
    def _process_artist_data(self, artist):
        """Process and validate artist data, handling null values."""
        return{
            'id': artist.spotify_id,
            'name': artist.name,
            'image_url': artist.image_url or '/static/default_artist.png',
            'genres' : artist.genres or 'Genre Unknown',
            'debut_year': artist.debut_year or 0,
            'birth_year': artist.birth_year or 0,
            'num_albums': artist.num_albums or 0,
            'members': artist.members or 1, # Default to solo artist
            'country': artist.country or 'Country Unknown',
            'gender': artist.gender or 'Not Specified',
            'popularity': artist.popularity or 50, # Default to medium popularity
            'most_popular_song': artist.most_popular_song or None,
            'most_popular_track_uri': artist.most_popular_track_uri or None, 
            'most_popular_song_id' : artist.most_popular_song_id or None
            }
        
    def _initialize_game_impl(self):
        """Initialize a new artist guessing game session."""
        #Check if we have a completed game
        if self.session.completed:
            # If we're trying to access a completed game, restart it
            return self.restart_game()
        
        # Check cache first
        cached_game = self.get_cached_game('guess_artist')
        if cached_game:
            return cached_game
        
        artist = self.get_random_artists(1)[0] # Uses base class method
        if not artist:
            raise GameInitializationError("No valid artists found")
        
        processed_artist = self._process_artist_data(artist)
        
        # Setup playback for the artist's song
        if processed_artist['most_popular_song'] and processed_artist['most_popular_track_uri']:
            self.setup_playback(
                processed_artist['most_popular_song_id'],
                 processed_artist['most_popular_song'],
                processed_artist['name'],
                processed_artist['image_url'],
                processed_artist['most_popular_track_uri'],
            )
        
        # Create standardized game state
        game_state = GameState.create_initial_state(processed_artist, self.session.max_tries)
        
        # Save state to session
        self.state.current_state = game_state
        self.state.save()
        
        self.cache_game('guess_artist', game_state)
        
        return game_state
    def validate_guess(self, guess_artist_name):
        """
        Validate a guess and provide detailed feedback on matching attributes.
        
        Args:
            guess_artist_name (str): Name of the guessed artist
            
        """
        logger.debug(f"Attempting to validate guess: {guess_artist_name}")
        available_artists = MostListenedArtist.objects.filter(
            user=self.session.user
        ).values_list('name', flat=True)
        logger.debug(f"Available artists: {list(available_artists)}")
        
        current_state = self.state.current_state
        
        # Check cache for processed artist data
        target_artist_id = current_state['game_data'].get('artist_id')
        if not target_artist_id:
            raise GameError("Target artist is not set in the game state")
        
        cached_target = self.cache_service.get_artist_data(target_artist_id)
        if not cached_target:
            target_artist = MostListenedArtist.objects.get(spotify_id=target_artist_id)
            cached_target = self._process_artist_data(target_artist)
            self.cache_service.cache_artist_data(target_artist_id, cached_target)
            
        guess_artist = MostListenedArtist.objects.filter(
            user=self.session.user,
            name__iexact= guess_artist_name
        ).first()
        
        if not guess_artist or not guess_artist.name:
            return {
                'error': 'Invalid artist selection',
                'is_correct': False
            }
        
        processed_guess = self._process_artist_data(guess_artist)
          
        feedback = {
            'attributes': {},
            'is_correct': False,
            'animation_effects':[],
            'artist_info': {
                'name': processed_guess['name'],
                'image_url': processed_guess['image_url'],
            }
        }
        
        # Compare only non-null attributes
        for attr in cached_target:
            if attr in ['name', 'image_url', 'biography','id', 'most_popular_song', 'most_popular_track_uri', 'most_popular_song_id']:
                continue
            
            
            result = self._compare_values(
                attr,
                processed_guess[attr],
                cached_target[attr]
            )
            feedback['attributes'][attr] = {
                'status': result['status'],
                'message': result['message'],
                'animation': f"fade-{result['status']}",
                'guessed_value': processed_guess[attr]
            }
        # Name comparison
        name_similarity = SequenceMatcher(
            None,
            processed_guess['name'].lower(),
            cached_target['name'].lower()
        ).ratio()
        
        feedback['is_correct'] = name_similarity > 0.9
        
        if feedback['is_correct'] or self.session.current_tries >= self.session.max_tries - 1:

            feedback['target_artist'] = {
                'name': cached_target['name'],
                'image_url':   cached_target['image_url'],
                'favorite_song': {
                    'name': cached_target['most_popular_song'],
                    # Use 'most_popular_track_uri' for both preview_url and uri
                    # to match what the frontend expects.
                    'preview_url': cached_target['most_popular_track_uri'],
                    'uri': cached_target['most_popular_track_uri']
                }
            }
                
        # Update game state with the new guess
        updated_state = GameState.update_with_guess(current_state, feedback)
        self.state.current_state = updated_state
        self.state.save()
                    
        if feedback['is_correct'] or self.session.current_tries >= self.session.max_tries - 1:
            self.end_game(score=self.state.current_state['session_state']['score'])
                    
        return feedback
        
    def _compare_values(self, attr, guess_val, target_val):
        """Compare values with null handling."""
        if guess_val is None or target_val is None:
            return {
                'status': 'invalid',
                'message': 'Information not available'
            }
            
        comparison_funcs = {
            'debut_year': self._compare_years,
            'birth_year': self._compare_years,
            'num_albums': self._compare_numeric,
            'members': self._compare_exact,
            'gender': self._compare_exact,
            'popularity': self._compare_numeric,
            'country': self._compare_exact,
            'genres': self._compare_genre
        }
        
        compare_func = comparison_funcs.get(attr, self._compare_exact)
        return compare_func(guess_val, target_val)
    def search_artists(self, query):
        """
        Search available artists for autocomplete.
        
        Args:
            query(str): Search query string
        """
        return MostListenedArtist.objects.filter(
            user=self.session.user,
            name__icontains=query,
        ).values('name', 'image_url')[:10] # Limit to 10 results
    def _compare_years(self, guess, actual):
        """Compare years with closeness indicator."""
        diff = abs(guess - actual)
        if diff == 0:
            return {'status': 'exact', 'message': 'Exact match!'}
        elif diff <= 5:
            return {'status': 'close', 'message': 'Very Close!'}
        else:
            direction = 'earlier' if guess < actual else 'later'
            return {'status': 'wrong', 'message': f'Try {direction}'}
        
    def _compare_numeric(self, guess, actual):
        """compare numeric values with percentage difference."""
        if guess == actual:
            return {'status': 'exact', 'message': 'Exact match!'}
        
        diff_percent = abs(guess - actual) / max(actual, 1) * 100
        if diff_percent <= 20:
            return {'status': 'close', 'message': 'Very close!'}
        else:
            direction = 'lower' if guess > actual else 'higher'
            return {'status': 'wrong', 'message': f'Try {direction}'}
        
    def _compare_exact(self, guess, actual):
        """Compare values that need exact matches."""
        if guess == actual:
            return {'status': 'exact', 'message': 'Exact match!'}
        return {'status': 'wrong', 'message': 'No match'}
    
    def _compare_genre(self, guess, actual):
        """Compare genres with subgenre matching."""
        if guess.lower() == actual.lower():
            return {'status': 'exact', 'message': 'Exact match!'}
        
        #Check if one genre is a subgenre of the other
        if guess.lower() in actual.lower() or actual.lower() in guess.lower():
            return {'status': 'close', 'message': 'Related genre!'}
        
        return {'status': 'wrong', 'message': 'Different genre'}
    
    def get_artist_details(self):
        """Fetch complete artist details from the current game state or database."""
        artist_id = self.state.current_state.get('game_data', {}).get('artist_id') or self.state.current_state.get('artist_id')
        if not artist_id:
            raise GameError("Artist ID not found in game state")
        artist = MostListenedArtist.objects.filter(spotify_id=artist_id).first()
        if not artist:
            raise GameError("Artist not found in database")
        return self._process_artist_data(artist)
    
    def _create_initial_game_state(self, processed_artist, available_artists):
        """Create game state in a separate method"""
        
        game_state = {
             # Root-level fields (required by frontend and backend)
            'artist_id': processed_artist['id'],  # MOVE TO ROOT LEVEL
            'revealed_info': {
                'genres': processed_artist['genres'],
                'country': processed_artist['country']
            },
            'session_state': {
                'tries_left': self.session.max_tries,
                'is_complete': False,
                'score': 0
            },
            # Keep other data under metadata
            '_metadata': {
                'available_artists': [
                    {
                        'name': a.name,
                        'image_url': a.image_url or '/static/default_artist.png'
                        }
                    for a in available_artists
                    if a.name
                    ],
                'remaining_attributes': {
                    attr: processed_artist[attr] for attr in [
                        'debut_year',
                        'birth_year',
                        'num_albums',
                        'members',
                        'gender',
                        'popularity',
                    ]
                if processed_artist.get(attr) is not None # Only include non-null attributes
                }
            }
             }
        
        self.state.current_state = game_state
        self.state.save()
        
        return game_state
        