from datetime import timedelta
from django.db.models import Avg, Max, Sum, Count
from django.utils import timezone
from ..models import GameSession, GameStatistics, GameLeaderboard
import logging
logger = logging.getLogger("spotify_games")
class AnalyticsService:
    def __init__(self, user):
        self.user = user
        
    # In Backend/silleyBEnd/spotify_games/game_modes/base.py

def _update_game_statistics(self, score: int):
    """Update user's game statistics after a game ends."""
    try:
        stats, created = GameStatistics.objects.get_or_create(
            user=self.session.user,
            game_type=self.session.game_type,
            defaults={
                'total_games': 1,
                'total_score': score,
                'highest_score': score,
            }
        )

        if not created:
            stats.total_games += 1
            stats.total_score += score
            if score > stats.highest_score:
                stats.highest_score = score
        
        # Calculate average score
        if stats.total_games > 0:
            stats.average_score = stats.total_score / stats.total_games
        else:
            stats.average_score = 0
            
        # =======================================================
        # THE FIX IS HERE
        # =======================================================
        # 1. Correctly calculate the duration of the current session
        if self.session.end_time and self.session.start_time:
            duration = self.session.end_time - self.session.start_time
            # 2. Add the new duration to the existing total_time_played
            stats.total_time_played += duration
        
        # 3. Save the updated statistics to the database
        stats.save()
        
        # Update leaderboard
        GameLeaderboard.objects.create(
            user=self.session.user,
            game_type=self.session.game_type,
            score=score
        )
        logger.info(f"Statistics updated for user {self.session.user.id}")

    except Exception as e:
        logger.error(f"Failed to update statistics for user {self.session.user.id}: {str(e)}", exc_info=True)
        
    def _update_leaderboard(self, session: GameSession):
        """Update leaderb oard with new game score."""
        # Only keep top 100 scores per game type
        GameLeaderboard.objects.create(
            user=self.user,
            game_type=session.game_type,
            score=session.score
        )
        
        # Cleanup old entries keeping only top 100
        top_100_scores = GameLeaderboard.objects.filter(
            game_type=session.game_type
        ).order_by('-score')[:100].values_list('id',flat=True)
        
        GameLeaderboard.objects.filter(
            game_type=session.game_type
        ).exclude(
            id_in=list(top_100_scores)
        ).delete()
        
    def get_user_statistics(self):
        """Get comprehensive user statistics."""
        return {
            'overall': self._get_overall_stats(),
            'by_game': self._get_game_specific_stats(),
            'recent_activity': self._get_recent_activity(),
            'achievements': self._get_achievements()
        }
        
    def _get_overall_stats(self):
        return GameSession.objects.filter(user=self.user).aggregate(
            total_games=Count('id'),
            total_score=Sum('score'),
            avg_score=Avg('score'),
            highest_score=Max('score')
        )
        
    def _get_game_specific_stats(self):
        return GameStatistics.objects.filter(user=self.user)
    
    def _get_recent_activity(self):
        recent_cutoff = timezone.now() - timedelta(days=30)
        return GameSession.objects.filter(
            user=self.user,
            start_time_gte=recent_cutoff
        ).order_by('-start_time')
        
    def _get_achievements(self):
        # Implementation depends on your achievement system
        pass