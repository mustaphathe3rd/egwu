import copy
from  datetime import datetime

class GameState:
    """
    Standard game state strucuture across the application.
    
    KThe strucuture has three main components:
    - game_data: Contains core game information (artsit, music, etc.)
    - session_state: Contains session management information
    -ui_state: Contains UI-specific state information
    """
    
    @staticmethod
    def create_initial_state(artist_data, max_tries=10):
        """Create a standardized initial game state"""
        return {
            "game_data": {
                "artist_id": artist_data["id"],
                "artist_name": artist_data["name"],
                "revealed_info": {
                    "genres": artist_data["genres"],
                    "country": artist_data["country"]
                },
                "guesses": []
            },
            "session_state": {
                "tries_left": max_tries,
                "tries_used": 0,
                "is_complete": False,
                "score": 0
            },
            "ui_state": {
                "loading": False,
                "error": None,
                "current_view": "game" #Options: "game", "completion", "error"
            },
            "_metadata": {
                # Internal data not directly used by frontend
                "artist_details": artist_data,
                "game_started_at": datetime.now().isoformat()
            }
        }
        
    
    @staticmethod
    def update_with_guess(current_state, guess_feedback):
        """Update game state with guess feedback"""
        # Create a copy to avoid modifying the original
        new_state = copy.deepcopy(current_state)
        
        # Update tries information
        new_state["session_state"]["tries_used"] += 1
        new_state["session_state"]["tries_left"] -= 1
        
        # Add guess to history
        new_state["game_data"]["guesses"].append(guess_feedback)
        
        # Check for game completion
        if guess_feedback.get("is_correct") or new_state["session_state"]["tries_left"] <= 0:
            new_state["session_state"]["is_complete"] = True
            new_state["ui_state"]["current_view"] = "completion"
            
            # Calculate score based on tries used
            max_tries = new_state["session_state"]["tries_used"] + new_state["session_state"]["tries_left"]
            new_state["session_state"]["score"] = max(0, 10 - new_state["session_state"]["tries_used"])
            
            # Add target artist info to revealed info
            if "target_artist" in guess_feedback:
                new_state["game_data"]["target_artist"] = guess_feedback["target_artist"]
                
        return new_state
    
    
