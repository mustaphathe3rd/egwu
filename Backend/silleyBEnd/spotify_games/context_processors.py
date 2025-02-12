from .models import GameStatistics
import logging

logger = logging.getLogger('spotify_games')

def game_context(request):
    """Global context processor for game-related data"""
    context = {
        'available_games': [
            {
                'name': 'Lyrics Game',
                'type': 'lyrics_text',
                'description': 'Test your knowledge of song lyrics',
                'icon': 'music-notes'
            },
            {
                'name': 'Artist Guess',
                'type': 'guess_artist',
                'description': 'Guess the artist based on hints',
                'icon': 'microphone'
            },
            {
                'name': 'Music Trivia',
                'type': 'trivia',
                'description': 'Test your music knowledge',
                'icon': 'question'
            }
        ]
    }
    
    if request.user.is_authenticated:
        try:
            stats = GameStatistics.objects.filter(user=request.user).first()
            context.update({
                'user_stats': {
                    'game_played': stats.total_games if stats else 0,
                    'high_score': stats.highest_score if stats else 0,
                    'total_points': stats.total_score if stats else 0
                }
            })
        except Exception as e:
            # log the error but don't break the template
            logger.error(f"Error fetching user stats: {e}")
            context['user_stats'] = None
            
    return context