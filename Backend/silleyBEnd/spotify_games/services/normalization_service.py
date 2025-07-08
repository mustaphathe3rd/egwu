
import spacy
from spacy.cli.download import download
from thefuzz import fuzz
import re

class SemanticNormalizer:
    def __init__(self):
        """
        Initializes the normalizer by loading the spacCy model.
        The 'en_core_web_md' model includes word vectors for semantic similarity.
        """
        try:
            self.nlp = spacy.load('en_core_web_md')
        except OSError:
            # This helps if the model wasn't downloaded correctly
            print("Downloading 'en_core_web_md' spaCy model...")
            download('en_core_web_md')
            self.nlp = spacy.load('en_core_web_md')
            
    def _normalize_text(self, text: str) -> str:
        """Converts text to lowercase and removes punctuation."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        return text.strip()
    
    def are_answers_similar(self, user_answer: str, correct_answer: str, fuzzy_threshold=90, semantic_threshold=0.85) -> bool:
        """
        Checks if the user's answer is similar to the correct answer using a multi-step process.
        """
        norm_user_answer = self._normalize_text(user_answer)
        norm_correct_answer = self._normalize_text(correct_answer)
        
        # 1. Exact match check (fastest)
        if norm_user_answer == norm_correct_answer:
            return True
        
        # 2. Fuzzy string matching (catches typos and close misspellings)
        fuzzy_ratio = fuzz.ratio(norm_user_answer, norm_correct_answer)
        if fuzzy_ratio >= fuzzy_threshold:
            print(f"Fuzzy match passed with ratio: {fuzzy_ratio}")
            return True
        
        # 3. Semantic similarity using spaCy word vectors
        doc1 = self.nlp(norm_user_answer)
        doc2 = self.nlp(norm_correct_answer)
        
        # Ensure vectors are available
        if doc1.vector_norm == 0 or doc2.vector_norm == 0:
            return False # Cannot compare if one has no vector
        
        semantic_similarity = doc1.similarity(doc2)
        if semantic_similarity >= semantic_threshold:
            print(f"Semantic match passed with similarity: {semantic_similarity}")
            return True
        
        print(f"No match found. Fuzzy: {fuzzy_ratio}, Semantic: {semantic_similarity}") 
        return False