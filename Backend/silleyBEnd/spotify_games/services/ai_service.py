from typing import Dict, List, Any
import openai
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class AIService:
    def __init__(self):
        self.openai = openai
        self.openai.api_key = settings.OPENAI_API_KEY
        self.rate_limit = 100 #requests per hour
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate_crossword(self, lyrics: str) -> Dict[str, Any]:
        prompt = f"""
        Create an engaging crossword puzzle from these lyrics:
        {lyrics}
        
        Requirements:
        1. Extract 8-12 meaningful words from the lyrics
        2. Create contextual clues referencing the song's themes and meaning
        3. Include a mix of:
            - Direct word definitions
            - Song context clues
            - Thematic references
            - Wordplay or puns when appropriate
        4. Ensure words intersect in a valid crossword pattern
        
        Format the response as a JSON object with:
        {{
            "words": [{{
                "word": "example",
                "clue": "contextual clue here",
                "position": {{
                    "x": 0,
                    "y": 0,
                    "direction": "across/down"
                }}
            }}],
            "grid": [[null or letter]], // 2D array representing the crossword grid
            "dimensions": {{
                "width": N,
                "height": N
            }}
        }}
        """
        try:
            response = self.openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            return self._process_crossword_response(response.choices[0].message.content)
        
        except Exception as e:
            logger.error(f"Error generating crossword: {e}")
            return {"error": "Failed to generate crossword"} 
    
    def _process_crossword_response(self, response_content: str) -> Dict[str, Any]:
        try:
            return json.loads(response_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse crossword response: {e}")
            return {"error": "Invalid response format"}
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate_trivia_questions(self, artist_data: Dict) -> List[Dict[str, Any]]:
        prompt = f"""
        Create engaging trivia questions about this artist:
        Biography: {artist_data['biography']}
        Genres: {artist_data['genres']}
        Career Highlights: {artist_data.get('career_highlights','')}
        
        Requirements:
        1. Generate 10 multiple-choice questions
        2. Include questions about:
            - Career milestones
            - Musical style and genres
            - Notable collaborations
            - Historical impact
            - Interesting facts
        3. Vary difficulty levels
        4. Ensure all options are plausible
        5. Include brief explanations for correct answers
        
        Format each question as:
        {{
            "question": "Question text",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "Correct option",
            "explanation": "Why this is correct",
            "difficulty": "easy/medium/hard"
        }}
        """
        try:    
            response = self.openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            logger.info("Received response from OPENAI API")
            return self._process_trivia_response(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error generating trivia questions: {e}")
            return [{"error": "Failed to generate trivia questions"}]
            
    def _process_trivia_response(self, response_content: str) -> List[Dict[str,Any]]:
        try:
            return json.loads(response_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse trivia response: {e}")
            return [{"error": "Invalid response format"}]
   