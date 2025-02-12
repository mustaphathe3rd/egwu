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
import time
from google.ai import generativelanguage as glm
from google.generativeai import GenerativeModel, configure

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
        self.api_key = settings.PALM_API_KEY
        configure(api_key=self.api_key)
        self.model = GenerativeModel('gemini-pro')
        self.max_retries = 3
        
    def _make_api_request(self, prompt: str) -> str:
        """Make API request to PaLM with improved error handling"""
        for attempt in range(self.max_retries):
           try:
               response = self.model.generate_content(
                   prompt,
                   generation_config={
                       'temperature': 0.7,
                       'max_output_tokens': 1024,
                   }
                    )

               if not response.parts:
                   raise AIServiceError("Empty response from API")
               
               return response.parts[0].text
           
           except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"API request failed after {self.max_retries} attempts: {str(e)}")
                    raise AIServiceError(f"API request failed: {str(e)}")
                
                logger.warning(f"API request attempt {attempt + 1} failed: {str(e)}")
                time.sleep(2 ** attempt) # Exponential backoff
                
        raise AIServiceError(f"API request failed after {self.max_retries} attempts")        
                    
    def generate_trivia_questions(self, artist_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate trivia questions about an artist"""
        if not isinstance(artist_data, dict):
            raise valueError("Artist data must be a dictionary")
        
        prompt = f"""Generate 3  multiple choice trivia questions about this artist in english:
        
        Biography: {artist_data.get('biography', 'Not provided')}
        Genres: {', '.join(artist_data.get('genres', ['Unknown']))}
        Career Highlights: {artist_data.get('career_highlights', 'Not provided')}
        
        Format your response exactly like this example, with no additional text:
        [
        {{
        "question": "What genre is this artist primarily known for?",
        "options": ["Rock", "Pop", "Jazz", "Hip-Hop"],
        "correct_answer": "Rock",
        "explanation": "The artist is primarily known for rock music",
        "difficulty": "easy"
        }},
        {{
        "question": "In what year did this artist debut?",
        "options": ["1990", "1995", "2000", "2005"],
        "correct_answer": "1995",
        "explanation": "The artist debuted in 1995",
        "difficulty": "medium"
        }}
        ]"""       
        
        try: 
            response_text = self._make_api_request(prompt)
            
             # Clean the response text
            response_text = response_text.strip()
            if not response_text.startswith('['):
                # Find the first occurrence of [
                start_idx = response_text.find('[')
                if start_idx == -1:
                    raise AIServiceError("No JSON array found in response")
                response_text = response_text[start_idx:]
            
            if not response_text.endswith(']'):
                # Find the last occurrence of ]
                end_idx = response_text.rfind(']')
                if end_idx == -1:
                    raise AIServiceError("No JSON array found in response")
                response_text = response_text[:end_idx+1]

            # Parse JSON with error handling
            try:
                questions = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {str(e)}")
                logger.error(f"Problematic response: {response_text}")
                return []

            # Validate questions
            validated_questions = []
            for question in questions:
                if self._validate_question(question):
                    validated_questions.append(question)

            return validated_questions

        except Exception as e:
            logger.error(f"Error generating trivia questions: {str(e)}")
            return []

    def _validate_question(self, question: Dict) -> bool:
        """Validate a single question"""
        required_fields = ["question", "options", "correct_answer", "explanation", "difficulty"]
        
        # Check required fields
        if not all(field in question for field in required_fields):
            return False
            
        # Validate options
        if not isinstance(question["options"], list) or len(question["options"]) != 4:
            return False
            
        # Validate correct answer
        if question["correct_answer"] not in question["options"]:
            return False
            
        # Validate difficulty
        if question["difficulty"] not in ["easy", "medium", "hard"]:
            return False
            
        return True
        
    def generate_crossword(self, lyrics: str) -> Dict[str, Any]:
        """Generate a crossword puzzle from lyrics."""
        if not lyrics.strip():
            raise ValueError("Lyrics cannot be empty")
        
        # Build a prompt that instructs the AI to return only a list of words and clues.
        prompt = f"""From these lyrics:
    {lyrics}

    Generate a list of 30 words with clues from the lyrics. Follow these rules exactly:
    1. Each word MUST be between 3-8 letters long
    2. Each word MUST contain only letters A-Z
    3. Each clue MUST end with either (across) or (down)
    4. Each word must be unique (no duplicates)
    5. Format must be valid JSON

    Return only the JSON in this exact format:
    {{
      "words": [
        {{"word": "LOVE", "clue": "Main emotion in the song (across)"}},
        {{"word": "LIFE", "clue": "Theme of journey through time (down)"}},
        // ... more entries
      ]
    }}
    """
        try:
            response_text = self._make_api_request(prompt).strip()
            
            # Clean up response and parse JSON
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            try:
                ai_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {response_text}")
                raise AIServiceError(f"Invalid JSON response: {str(e)}")
            
            logger.debug(f"AI response parsed: {ai_data}")
            
             # Validate response structure
            if not isinstance(ai_data, dict) or 'words' not in ai_data:
                raise AIServiceError("Invalid response format: missing 'words' key")
            
            word_list = ai_data.get("words", [])
            if not isinstance(word_list, list) or not word_list:
                raise AIServiceError("No words found in the AI response")

             # Additional validation before puzzle generation
            valid_words = []
            seen_words = set()
            
            for entry in word_list:
                if not isinstance(entry, dict) or 'word' not in entry or 'clue' not in entry:
                    continue
                    
                word = str(entry['word']).upper()
                if (
                    word.isalpha() and
                    3 <= len(word) <= 8 and
                    word not in seen_words
                ):
                    seen_words.add(word)
                    valid_words.append(entry)
            
            if len(valid_words) < 15:
                raise AIServiceError(f"Insufficient valid words: {len(valid_words)} (minimum 15 required)")  
                            
            # Now pass the word list to your custom crossword generator.
            # For example, using a 15x15 grid:
            puzzle = generate_crossword_puzzle(word_list, width=15, height=15, max_attempts=3)
            return puzzle

        except Exception as e:
            logger.error(f"Error generating crossword: {str(e)}")
            return {'error': f"Generation failed: {str(e)}"}
        
    def generate_lyrics_challenges(self, lyrics: str, num_challenges: int) -> List[Dict[str, Any]]:
        """Generate multiple optimized lyrics challenges using AI"""
        if not lyrics.strip():
            raise ValueError("Lyrics cannot be empty")
        
        prompt = f"""Analyze these lyrics and return {num_challenges} different challenge sections in English.
        For each section, return a JSON object in an array.
        
        Return in this exact format:
        [
            {{
                "selected_section": {{
                    "start_index": 123,
                    "end_index": 145,
                    "text": "the selected portion of lyrics"
                }},
                "hint": "Brief hint about the missing section",
                "difficulty": "easy/medium/hard",
            }},
            // ...more challenges
        ]
        
        Selection criteria for each challenge:
        1. Choose different sections of the lyrics (don't repeat)
        2. Each section should be 15-20 words
        3. Choose memorable or distinctive phrases
        4. Prefer complete thoughts/phrases
        5. Select sections with clear context from surrounding lyrics
        6. Vary the difficulty levels
        """
        
        try:
            full_prompt = f"{prompt}\n\nLyrics to analyze: \n{lyrics}"
            response_text = self._make_api_request(full_prompt)
            
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                challenges_data = json.loads(json_str)
            else:
                raise AIServiceError("No Valid JSON array found in response")
            
            challenges = []
            for challenge_data in challenges_data:
                # Validate each challenge
                if not all(field in challenge_data for field in ["selected_section","hint","difficulty"]):
                    continue
                
                section = challenge_data["selected_section"]
                if not all(field in section for field in ["start_index", "end_index", "text"]):
                    continue
                
                missing_portion = section["text"]
                placeholder = " _____ " * (len(missing_portion.split()) // 2)
                challenge_lyrics = lyrics.replace(missing_portion, placeholder)
                
                challenges.append({
                    "complete_lyrics": lyrics,
                    "challenge_lyrics": challenge_lyrics,
                    "missing_portion": missing_portion,
                    "hint": challenge_data["hint"],
                    "difficulty": challenge_data["difficulty"],
                    "word_count": len(missing_portion.split()),
                })
                
            if not challenges:
                raise AIServiceError("No valid challenges generated")
            
            return challenges
        
        except Exception as e:
            logger.error(f"Error generating lyrics challenges: {str(e)}")
            return [{"error": str(e)}]
        
class WordEntry:
    def __init__(self, word: str, clue: str):
        self.word = word.upper()
        self.clue = clue

    @property
    def is_valid(self) -> bool:
        return( bool(self.word and self.clue) and
               self.word.isalpha() and
               3 <= len(self.word) <= 8 and
               any(direction in self.clue.lower() for direction in ["(across)", "(down)"])
        )
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
            
        return cls(word, clue)

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
        
        # Sort words by scoring them based on multiple factors
        self.words.sort(key=self._score_word, reverse=True)
        
        # Ensure minimum word count (reduced for better success rate)
        if len(self.words) < 10:
            raise ValueError(f"Insufficient valid words: {len(self.words)} (minimum 10 required)")

    def _score_word(self, word_entry: WordEntry) -> float:
        """Score words based on length and letter frequency."""
        word = word_entry.word
        
        # Common letters in English that often create intersections
        common_letters = 'ETAOINSHRDL'
        common_letter_score = sum(2 for letter in word if letter in common_letters)
        
        # Length score (prefer medium length words)
        length_score = 10 - abs(5 - len(word))  # 5 letters is optimal
        
        # Unique letters score
        unique_letters_score = len(set(word))
        
        return common_letter_score + length_score + unique_letters_score
    
    def validate_placement(self, word_entry: WordEntry, direction: str) -> bool:
        """Validate if the word can be placed in the specified direction based on its clue."""
        clue = word_entry.clue.lower()
        return (direction == "across" and "(across)" in clue) or \
               (direction == "down" and "(down)" in clue)

    def find_intersections(self, word_entry: WordEntry) -> List[Dict[str, Any]]:
        """Enhanced intersection finding with better positioning strategy."""
        positions = []
        word = word_entry.word
        
        # For first word, try multiple starting positions
        if all(cell is None for row in self.grid for cell in row):
            start_positions = [
                (self.width // 4, self.height // 2),
                (self.width // 2, self.height // 2),
                (self.width // 3, self.height // 2)
            ]
            
            for x, y in start_positions:
                if self.validate_placement(word_entry, "across"):
                    positions.append({"x": x, "y": y, "direction": "across"})
                if self.validate_placement(word_entry, "down"):
                    positions.append({"x": x, "y": y, "direction": "down"})
            return positions

        # Find intersections with looser constraints
        for y in range(self.height):
            for x in range(self.width):
                if self.grid[y][x] is not None:
                    # Try both directions for each intersection point
                    for direction in ["across", "down"]:
                        if not self.validate_placement(word_entry, direction):
                            continue
                            
                        # Try placing word at different positions relative to intersection
                        for i, letter in enumerate(word):
                            if letter == self.grid[y][x]:
                                pos_x = x - i if direction == "across" else x
                                pos_y = y if direction == "across" else y - i
                                
                                if self.can_place(word, pos_x, pos_y, direction):
                                    positions.append({
                                        "x": pos_x,
                                        "y": pos_y,
                                        "direction": direction,
                                        "intersections": self._count_intersections(word, pos_x, pos_y, direction)
                                    })

        # Sort positions by number of intersections
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
        formatted_grid = []
        numbered_cells = {
            (word["position"]["x"], word["position"]["y"]): word["number"]
            for word in puzzle["words"]
        }
        
        for y, row in enumerate(puzzle["grid"]):
            formatted_row = []
            for x, cell in enumerate(row):
                cell_data = {
                    "letter": cell if cell is not None else "",
                    "isActive": cell is not None,
                    "isBlack": cell is None,
                    "x": x,
                    "y": y,
                    "number": numbered_cells.get((x, y))
                }
                formatted_row.append(cell_data)
            formatted_grid.append(formatted_row)
        
        # Format word data for frontend
        formatted_words = []
        for word in puzzle["words"]:
            formatted_word = {
                "word": word["word"],
                "clue": word["clue"],
                "number": word["number"],
                "position": {
                    "x": word["position"]["x"],
                    "y": word["position"]["y"],
                    "direction": word["position"]["direction"]
                }
            }
            formatted_words.append(formatted_word)
            
        return {
            "grid": formatted_grid,
            "words": formatted_words,
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