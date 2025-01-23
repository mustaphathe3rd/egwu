from datetime import timedelta
from django.db.models import Avg, Max, Sum, Count
from django.utils import timezone
from ..models import GameSession, GameStatistics, GameLeaderboard

class AnalyticsService:
    def __init__(self, user):
        self.user = user
        
    def update_game_statistics(self, session: GameSession):
        """Update user statistics after game completion."""
        stats, created = GameStatistics.objects.get_or_create(
            user=self.user,
            game_type=session.game_type
        ) 
        
        # Update statistics
        stats.total_games += 1
        stats.total_score += session.score
        stats.highest_score = max(stats.highest_score, session.score)
        stats.average_score = stats.total_score / stats.total_games
        stats.total_time_played += session.end_time - session.start_time
        stats.save()
        
        # Update leaderboard if score is significant
        self._update_leaderboard(session)
        
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