from typing import Dict, List, Any
import openai
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_exponential

class AIService:
    def __init__(self):
        self.openai = openai
        settings.OPENAI_API_KEY
        
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
        
        response = self.openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        return self._process_crossword_response(response.choices[0].message.content)
    
    
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
        
        response = self.openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        return self._process_trivia_response(response.choices[0].message.content)
    
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def analyze_artist_similarity(self, target_artist: Dict, guessed_name: str) -> Dict[str, Any]:
        prompt = f"""
        Analyze the similarity between the guessed artist name "{guessed_name}"
        and the target artist with these characteristics:
        Genre: {target_artist['genres']}
        Era: {target_artist.get('debut_year')}
        Style: {target_artist.get('musical_style', '')}
        
        Provide feedback in JSON format:
        {{
            "similarity_score": 0-1,
            "genre_match": true/false,
            "era_match": true/false,
            "feedback": "Specific guidance based on the guess",
            "hint": "Subtle hint about the correct artist"
        }}
        """
        
        response = self.openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        return self._process_similarity_response(response.choices[0].message.content)