from typing import Dict, List, Any, Optional
import copy
import random
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_exponential
from dataclasses import dataclass
from enum import Enum
import logging
import json
import requests
import re
import time
from google.ai import generativelanguage as glm
from google.generativeai.generative_models import GenerativeModel
from google.generativeai.client import configure
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logger = logging.getLogger("spotify_games")


class Difficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    
@dataclass
class TriviaQuestion:
    question: str
    options: List[str]
    correct_answer: str
    explanation: str
    difficulty: Difficulty
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "difficulty": self.difficulty.value
        }
        
class AIServiceError(Exception):
    """Custom exception for AIService errors"""
    pass

class AIService:
    def __init__(self):
        # =======================================================
        # FIX 1: Load and rotate multiple API keys
        # =======================================================
        self.api_keys = [key for key in [
            getattr(settings, 'PALM_API_KEY', None),
            getattr(settings, 'PALM_API_KEY_2', None)
        ] if key]

        if not self.api_keys:
            raise ValueError("No PALM_API_KEY or PALM_API_KEY_2 found in settings.")

        self.max_retries = 3

    def _get_model(self) -> GenerativeModel:
        """Initializes and returns a model with a randomly chosen API key and disabled safety settings."""
        api_key = settings.PALM_API_KEY_2
        configure(api_key=api_key)
        
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        model = GenerativeModel(
            'gemini-1.5-pro-latest',
            safety_settings=safety_settings
        )
        return model

    def _make_api_request(self, prompt: str) -> str:
        """Make API request with retries and key rotation."""
        for attempt in range(self.max_retries):
            try:
                model = self._get_model()
                response = model.generate_content(
                    prompt,
                    generation_config={
                        'temperature': 0.7,
                        'max_output_tokens': 2048, # Increased token limit for larger responses
                    }
                )

                if not response.parts:
                    raise AIServiceError("Empty response from API - likely blocked by safety filters or a model refusal.")
                
                return response.text # Use response.text for simplicity
            
            except Exception as e:
                logger.warning(f"API request attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    logger.error(f"API request failed after all retries: {str(e)}")
                    raise AIServiceError(f"API request failed: {str(e)}")
                time.sleep(2 ** attempt)
                        
        raise AIServiceError("API request failed after all retries.")
        
    def generate_trivia_questions(self, artists_data: List[Dict[str, Any]], num_questions: int) -> List[Dict[str, Any]]:
        """Generate a batch of trivia questions for multiple artists in a single API call."""
        if not artists_data:
            raise ValueError("Artists data cannot be empty.")

        context_block = ""
        for i, artist in enumerate(artists_data, 1):
            context_block += f"\n---ARTIST {i}---\n"
            context_block += f"Name: {artist.get('name', 'N/A')}\n"
            context_block += f"Biography: {artist.get('biography', 'N/A')}\n"
            context_block += f"Genres: {artist.get('genres', 'N/A')}\n"
            context_block += f"Career Highlights: {artist.get('career_highlights', 'N/A')}\n"

        # =======================================================
        # FIX 2: Refined and more direct prompt
        # =======================================================
        prompt = f"""
        CONTEXT:
        {context_block}

        TASK:
        Based *only* on the context provided above, generate exactly {num_questions} unique multiple-choice trivia questions about the artists.

        RULES:
        1. The output MUST be a single, valid JSON array of objects.
        2. Do NOT include any text, markdown, or explanations outside of the JSON array.
        3. Each JSON object must have these exact keys: "question", "options" (an array of 4 strings), "correct_answer" (a string that must be one of the options), "explanation" (a brief string), "difficulty" (a string: "easy", "medium", or "hard").
        
        EXAMPLE OUTPUT:
        [
          {{
            "question": "Which of these artists is primarily known for the 'motown' genre?",
            "options": ["Artist A", "Artist B", "Artist C", "Artist D"],
            "correct_answer": "Artist A",
            "explanation": "Artist A is a legendary motown artist.",
            "difficulty": "medium"
          }}
        ]
        """
        
        try:
            response_text = self._make_api_request(prompt)
            
            # Find the start and end of the JSON array
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            
            if json_start == -1 or json_end == 0:
                raise AIServiceError("No JSON array found in the AI response.")
            
            json_str = response_text[json_start:json_end]
            
            questions = json.loads(json_str)
            validated_questions = [q for q in questions if self._validate_question(q)]
            return validated_questions

        except Exception as e:
            logger.error(f"Error processing AI response for trivia questions: {str(e)}")
            return []

    def _validate_question(self, question: Dict) -> bool:
        """Validate a single question"""
        required_fields = ["question", "options", "correct_answer", "explanation", "difficulty"]
        if not all(field in question for field in required_fields): return False
        if not isinstance(question["options"], list) or len(question["options"]) != 4: return False
        if question["correct_answer"] not in question["options"]: return False
        if question["difficulty"] not in ["easy", "medium", "hard"]: return False
        return True
    
    def generate_crossword(self, lyrics: str) -> Dict[str, Any]:
        """Generate a crossword puzzle from lyrics."""
        if not lyrics.strip():
            raise ValueError("Lyrics cannot be empty")
        
        # =======================================================
        # FIX 1: Improved AI Prompt
        # =======================================================
        prompt = f"""
        CONTEXT:
        The following are lyrics from a song:
        ---
        {lyrics}
        ---

        TASK:
        Generate a list of 15-20 unique words and clues based ONLY on the lyrics provided.

        RULES:
        1. Each "word" MUST be a single word between 4-8 letters long, found in the lyrics.
        2. Each "clue" MUST be a short hint about the word's meaning in the context of the lyrics.
        3. The output MUST be a valid JSON array of objects. Do not include any text outside of the JSON array.
        4. Each object must have exactly two keys: "word" and "clue". Do not add "(across)" or "(down)".

        EXAMPLE OUTPUT:
        [
        {{"word": "HEAVEN", "clue": "A place of eternal bliss mentioned in the song"}},
        {{"word": "HEART", "clue": "The center of emotion"}},
        {{"word": "EYES", "clue": "Organs of sight"}}
        ]
        """
        try:
            response_text = self._make_api_request(prompt).strip()
            
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            if json_start == -1 or json_end == 0:
                raise AIServiceError("No JSON array found in AI response for crossword.")
            
            json_str = response_text[json_start:json_end]
            word_list = json.loads(json_str)

            if len(word_list) < 10:
                raise AIServiceError(f"AI generated only {len(word_list)} words, not enough for a puzzle.")
            
            puzzle = generate_crossword_puzzle(word_list, width=15, height=15)
            return puzzle

        except Exception as e:
            logger.error(f"Error generating crossword: {str(e)}")
            return {'error': f"Generation failed: {str(e)}"}
        
    def generate_lyrics_challenges(self, lyrics: str, num_challenges: int, song_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate multiple optimized lyrics challenges using AI"""
        if not lyrics.strip():
            raise ValueError("Lyrics cannot be empty")
        
        # The prompt itself does not need to change
        prompt = f"""
        CONTEXT:
        The following are song lyrics:
        ---
        {lyrics}
        ---

        TASK:
        Analyze the lyrics and identify {num_challenges} unique, memorable, and clear phrases to use for a "complete the lyrics" game.

        RULES FOR EACH CHALLENGE:
        1.  Select a short, contiguous section of lyrics to be the "missing part". This part should be between 5 and 10 words long.
        2.  The missing part MUST be a complete or near-complete phrase that makes sense on its own.
        3.  Provide the line of lyrics that comes directly BEFORE the missing part as "context_before".
        4.  Provide the line of lyrics that comes directly AFTER the missing part as "context_after".
        5.  The final output MUST be a single, valid JSON array of objects. Do not include any text outside of the JSON array.
        6.  Each object must have these exact keys: "missing_portion", "context_before", "context_after".
        """
        
        try:
            response_text = self._make_api_request(prompt)
            
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            if json_start == -1 or json_end == 0:
                raise AIServiceError("No Valid JSON array found in response for lyrics challenge")
            
            json_str = response_text[json_start:json_end]
            challenges_data = json.loads(json_str)
            
            # =======================================================
            # THE FIX IS HERE: Attach the song_data to each challenge
            # =======================================================
            for challenge in challenges_data:
                if isinstance(challenge, dict):
                    challenge["song_data"] = song_data
            
            if not challenges_data:
                raise AIServiceError("No valid challenges generated")
            
            return challenges_data
        
        except Exception as e:
            logger.error(f"Error generating lyrics challenges: {str(e)}")
            return [{"error": str(e)}]
class WordEntry:
    def __init__(self, word: str, clue: str):
        self.word = word.upper()
        self.clue = clue

    @property
    def is_valid(self) -> bool:
        return 4 <= len(self.word) <= 10
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "word": self.word,
            "clue": self.clue
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WordEntry':
        if not isinstance(data, dict):
            raise ValueError("Input must be a dictionary")
        
        word = str(data.get("word", "")).strip()
        clue = str(data.get("clue", "")).strip()
        
        if not word or not clue:
            raise ValueError("Word and clue are required")
        
        sanitized_word = re.sub(r'[^A-Z]', '', word.upper())
            
        return cls(sanitized_word, clue)

class CrosswordGenerator:
    def __init__(self, words: List[Dict[str, str]], width: int = 15, height: int = 15):
        self.width = width
        self.height = height
        self.grid = [[None for _ in range(width)] for _ in range(height)]
        self.placements = []
        
        # Improved word filtering and sorting
        seen_words = set()
        self.words: List[WordEntry] = []
        
        # First pass: collect all valid words
        for word_dict in words:
            try:
                word_entry = WordEntry.from_dict(word_dict)
                if word_entry.is_valid and word_entry.word not in seen_words:
                    seen_words.add(word_entry.word)
                    self.words.append(word_entry)
            except (ValueError, AttributeError) as e:
                logger.warning(f"Skipping invalid word entry: {word_dict}. Error: {str(e)}")
                continue
        
        # Sort words by scoring them based on multiple factors
        self.words.sort(key=lambda x: len(x.word), reverse=True)
        
        # Ensure minimum word count (reduced for better success rate)
        if len(self.words) < 10:
            raise ValueError(f"Insufficient valid words: {len(self.words)} (minimum 10 required)")

    def find_intersections(self, word_entry: WordEntry) -> List[Dict[str, Any]]:
        positions = []
        word = word_entry.word
        
        if not self.placements: # For the first word
            # Try placing the first word horizontally in the middle
            x = (self.width - len(word)) // 2
            y = self.height // 2
            positions.append({"x": x, "y": y, "direction": "across", "intersections": 0})
            return positions

        # Find intersections with existing words
        for y_grid in range(self.height):
            for x_grid in range(self.width):
                if self.grid[y_grid][x_grid] is not None:
                    for i, letter in enumerate(word):
                        if letter == self.grid[y_grid][x_grid]:
                            # Try placing ACROSS
                            pos_x_across = x_grid - i
                            if self.can_place(word, pos_x_across, y_grid, "across"):
                                intersections = self._count_intersections(word, pos_x_across, y_grid, "across")
                                positions.append({"x": pos_x_across, "y": y_grid, "direction": "across", "intersections": intersections})
                            # Try placing DOWN
                            pos_y_down = y_grid - i
                            if self.can_place(word, x_grid, pos_y_down, "down"):
                                intersections = self._count_intersections(word, x_grid, pos_y_down, "down")
                                positions.append({"x": x_grid, "y": pos_y_down, "direction": "down", "intersections": intersections})

        positions.sort(key=lambda p: p["intersections"], reverse=True)
        return positions
    
    def can_place(self, word: str, x: int, y: int, direction: str) -> bool:
        """Check if a word can be placed at the given position."""
        length = len(word)
        
        # Check bounds
        if direction == "across":
            if x < 0 or x + length > self.width:
                return False
            for i in range(length):
                cell = self.grid[y][x + i]
                if cell is not None and cell != word[i]:
                    return False
        else:  # down
            if y < 0 or y + length > self.height:
                return False
            for i in range(length):
                cell = self.grid[y + i][x]
                if cell is not None and cell != word[i]:
                    return False
                    
        return True

    def place_word(self, word: str, x: int, y: int, direction: str) -> None:
        """Place the word on the grid."""
        for i, letter in enumerate(word):
            if direction == "across":
                self.grid[y][x + i] = letter
            else:
                self.grid[y + i][x] = letter
    

    def _count_intersections(self, word: str, x: int, y: int, direction: str) -> int:
        """Count number of intersections a word placement would create."""
        intersections = 0
        for i, letter in enumerate(word):
            curr_x = x + (i if direction == "across" else 0)
            curr_y = y + (i if direction == "down" else 0)
            
            if self.grid[curr_y][curr_x] == letter:
                intersections += 1
                
        return intersections

    def generate(self) -> Dict[str, Any]:
        """Generate crossword with improved backtracking."""
        def backtrack(index: int, min_intersections: int = 0) -> bool:
            if index >= len(self.words):
                return True
                
            word_entry = self.words[index]
            positions = self.find_intersections(word_entry)
            
            # Try positions with most intersections first
            for pos in positions:
                if pos.get("intersections", 0) >= min_intersections:
                    if self.can_place(word_entry.word, pos["x"], pos["y"], pos["direction"]):
                        prev_grid = copy.deepcopy(self.grid)
                        
                        self.place_word(word_entry.word, pos["x"], pos["y"], pos["direction"])
                        self.placements.append({
                            "word": word_entry.word,
                            "clue": word_entry.clue,
                            "position": pos
                        })
                        
                        if backtrack(index + 1, min_intersections):
                            return True
                            
                        self.grid = prev_grid
                        self.placements.pop()
            
            # If we couldn't place with current constraints, try with fewer required intersections
            if min_intersections > 0 and not positions:
                return backtrack(index, min_intersections - 1)
                
            return False

        # Try to generate with different minimum intersection requirements
        for min_intersections in [2, 1, 0]:
            if backtrack(0, min_intersections):
                break
        
        if not self.placements:
            raise ValueError("Could not generate valid crossword with given words")

        return self._format_result()

    def _format_result(self) -> Dict[str, Any]:
        """Format the final puzzle with numbered positions."""
        number = 1
        numbered_positions = {}
        
        for placement in self.placements:
            pos = (placement["position"]["x"], placement["position"]["y"])
            if pos not in numbered_positions:
                numbered_positions[pos] = number
                placement["number"] = number
                number += 1
            else:
                placement["number"] = numbered_positions[pos]

        return {
            "grid": self.grid,
            "words": self.placements,
            "dimensions": {"width": self.width, "height": self.height}
        }

def format_grid_for_frontend(puzzle: Dict[str, Any]) -> Dict[str, Any]:
    """Format the puzzle data for frontend display with enhanced metadata."""
    try:
        grid_data = puzzle["grid"]
        words_data = puzzle["words"]
        
        formatted_grid = []
        for y, row in enumerate(grid_data):
            formatted_row = []
            for x, cell in enumerate(row):
                cell_data = {
                    "char": cell, # The correct letter for this cell
                    "number": None,
                    "isBlack": cell is None,
                }
                formatted_row.append(cell_data)
            formatted_grid.append(formatted_row)
        
        # Format word data and add numbers to the grid
        for word_info in words_data:
            x, y = word_info["position"]["x"], word_info["position"]["y"]
            if formatted_grid[y][x]["number"] is None:
                 formatted_grid[y][x]["number"] = word_info["number"]
        
        return {
            "grid": formatted_grid,
            "words": words_data,
            "dimensions": puzzle["dimensions"]
        }
    except Exception as e:
        logger.error(f"Error formatting grid for frontend: {str(e)}")
        raise ValueError(f"Failed to format puzzle for frontend: {str(e)}")

def generate_crossword_puzzle(
    word_list: List[Dict[str, str]], 
    width: int = 15, 
    height: int = 15,
    max_attempts: int = 3
) -> Dict[str, Any]:
    """
    Generate a crossword puzzle with multiple attempts and improved error handling.
    
    Args:
        word_list: List of dictionaries containing words and clues
        width: Width of the puzzle grid (default: 15)
        height: Height of the puzzle grid (default: 15)
        max_attempts: Maximum number of generation attempts (default: 3)
        
    Returns:
        Dictionary containing formatted puzzle data for frontend
        
    Raises:
        ValueError: If puzzle generation fails after all attempts
    """
    last_error = None
    
    for attempt in range(max_attempts):
        try:
            logger.info(f"Attempting to generate crossword (attempt {attempt + 1}/{max_attempts})")
            
            # Shuffle word list to get different combinations on each attempt
            shuffled_words = random.sample(word_list, len(word_list))
            
            # Create generator with current word set
            generator = CrosswordGenerator(shuffled_words, width, height)
            
            # Generate puzzle
            puzzle = generator.generate()
            
            # Validate puzzle structure
            if not puzzle.get("grid") or not puzzle.get("words"):
                raise ValueError("Generated puzzle is missing required components")
                
            # Format for frontend
            formatted_puzzle = format_grid_for_frontend(puzzle)
            
            # Validate formatted puzzle
            if not formatted_puzzle.get("grid") or not formatted_puzzle.get("words"):
                raise ValueError("Formatted puzzle is missing required components")
                
            logger.info("Successfully generated crossword puzzle")
            return formatted_puzzle
            
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Puzzle generation attempt {attempt + 1} failed: {last_error}")
            
            # On last attempt, try with smaller grid
            if attempt == max_attempts - 1 and width > 10:
                try:
                    logger.info("Attempting generation with smaller grid")
                    return generate_crossword_puzzle(
                        word_list,
                        width=10,
                        height=10,
                        max_attempts=1
                    )
                except Exception as small_grid_error:
                    last_error = str(small_grid_error)
                    
    # If all attempts fail, return error structure
    error_msg = f"Failed to generate crossword after {max_attempts} attempts: {last_error}"
    logger.error(error_msg)
    
    return {
        "error": error_msg,
        "grid": None,
        "words": None,
        "dimensions": {"width": width, "height": height}
    }