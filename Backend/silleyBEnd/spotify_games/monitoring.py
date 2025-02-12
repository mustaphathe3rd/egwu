from dataclasses import dataclass
from datetime import datetime
import statsd
import logging
from .models import GameSession

@dataclass
class GameEvent:
    event_type: str
    user_id: int
    game_type: str
    timestamp: datetime
    metadata: dict
    
class GameAnalytics:
    def __init__(self):
        self.statsd = statsd.StatsClient('localhost', 8125)
        self.logger = logging.getLogger('game.analytics')
        
    def track_event(self, event: GameEvent):
        """Track a game event."""
        # Log to file
        self.logger.info(f"Game event: {event}")
        
        # Send to StatsD
        metric_name = f"game.{event.game_type}.{event.event_type}"
        self.statsd.incr(metric_name)
        
        # Track timing if available
        if 'duration' in event.metadata:
            self.statsd.timing(f"{metric_name}.duration", event.metadata['duration'])
            
    def track_game_completion(self, session: GameSession):
        """Track game completion metrics."""
        duration = (session.end_time - session.start_time).total_seconds()
        
        event = GameEvent(
            event_type = 'completion',
            user_id = session.user.id,
            game_type = session.game_type,
            timestamp = datetime.now(),
            metadata = {
                'duration': duration,
                'score': session.score,
                'attempts': session.current_tries
            }
        )
        self.track_event(event)