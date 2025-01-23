#1. Custom Exceptions for Better Error Handling

class GameError(Exception):
    """Base exception for game_related errors."""
    pass

class GameInitializationError(GameError):
    """Raised when game cannot be initialized."""
    pass

class GameStateError(GameError):
    """Raised when game state is invalid."""
    pass

class ResourceNotFoundError(GameError):
    """Raised when required game resources aere not found."""
    pass

class AIServiceError(GameError):
    """Raised when AI service fails."""
    pass
    