import ssl
import certifi
import aiohttp 
import asyncio
from bs4 import BeautifulSoup
import requests
import time
from typing import Optional, Dict, List
from functools import lru_cache
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
import requests
import mwparserfromhell
import re
from django.conf import settings
from aiohttp import TCPConnector
from typing import Tuple, Dict
from asgiref.sync import sync_to_async
from django.db import transaction
from .models import MostListenedArtist
import logging

logger = logging.getLogger("spotify")

class LyricsService:
    def __init__(self):
        self.genius_token= settings.GENIUS_API_TOKEN
        self.search_url = "https://api.genius.com/search"
        self.headers = {
            "Authorization": f"Bearer {self.genius_token}",
            "User-Agent": "Mozilla/5.0(Wimdows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language" : "en-US,en;q=0.5",
        }
         # Create SSL context with verified certificates
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        
    async def _create_client_session(self) -> aiohttp.ClientSession:
        """Create a client session with proper SSL configuration."""
        return aiohttp.ClientSession(
            headers = self.headers,
            connector= TCPConnector(ssl=self.ssl_context)
        )
                 
    @retry(stop=stop_after_attempt(3),wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_song(self, song_title: str, artist_name: Optional[str] = None) -> Optional[str]:
        if not isinstance(song_title, str):
            logger.error(f"Invalid song_title type: {type(song_title)}")
            return None
        
        if artist_name and not isinstance(artist_name, str):
            logger.error(f"Invalid artist_name type: {type(artist_name)} ")
            return None
        params = {"q": song_title}
        async with await self._create_client_session() as session:
            try:
                async with session.get(self.search_url, params=params) as response:
                    response.raise_for_status()
                    if response.status != 200:
                        logger.error(f"Search failed: {response.status}")
                        return None
                    
                    data = await response.json()
                    hits = data.get("response", {}).get("hits",[])
                    
                    for hit in hits:
                        song = hit.get("result", {})
                        if not song:
                            continue
                        
                        artist_data = song.get("primary_artist",{})
                        artist_name_from_api = artist_data.get("name","") if artist_data else ""
                        
                        if not artist_name or (
                            artist_name_from_api and
                            isinstance(artist_name, str) and 
                            artist_name.lower() in artist_name_from_api.lower()
                        ):
                            return song.get("url")
                    
                    logger.warning(f"No matching songs found for {song_title}")
                    return None
                
            except aiohttp.ClientError as e:
                logger.error(f"Network error searching song: {e}")
                return None
                
            except Exception as e:
                logger.error(f"Error searching song: {e}")
                return None
            
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))        
    async def get_lyrics(self,song_url: str) -> Optional[str]:
        if not isinstance(song_url, str):
            logger.error("Invalid song_url type: must be string")
            return None
        
        async with await self._create_client_session() as session:
            try:
                async with session.get(song_url) as response:
                    response.raise_for_status()
                    if response.status != 200:
                        logger.error(f"Lyrics fetch failed: {response.status}")
                        return None
                    
                    html = await response.text()
                    if not html:
                        return None
                    
                    soup = BeautifulSoup(html, 'html.parser')
                    lyrics = await self.extract_lyrics(soup)
                    
                    return lyrics
            
            
            except aiohttp.ClientError as e:
                logger.error(f"Network error fetching lyrics: {e}")
                return None
            except Exception as e:
                logger.error(f"Error fetching lyrics: {e}")
                return None
            
    async def extract_lyrics(self, soup: BeautifulSoup) -> Optional[str]:
        if not isinstance(soup, BeautifulSoup):
            logger.error("Invalid soup type: must be BeautifulSoup")
            return None
        
        try: 
            lyrics_containers = soup.select('div[class*="Lyrics__Container"]')
            if not lyrics_containers:
                lyrics_containers = soup.find_all("div", attrs={"data-lyrics-container": "true"})
                
            if not lyrics_containers:
                return None
            
            lyrics = []
            for container in lyrics_containers:
                for element in container.find_all(['script', 'button']):
                    element.decompose()
                text = container.get_text(separator='\n')
                lyrics.append(text.strip())
                
            full_lyrics = '\n'.join(lyrics)
            full_lyrics = re.sub(r'\n{3,}', '\n\n', full_lyrics)
            full_lyrics = re.sub(r'\[.*?\]', '', full_lyrics)
                    
            return full_lyrics.strip()
        
        except Exception as e:
            logger.error(f"Error extracting lyrics: {e}")
            return None
        
class ArtistDetailsService:
    def __init__(self):
        self.base_url = "https://en.wikipedia.org/w/api.php"
        self.desired_sections = [
            "Early life", "Personal life", "Artistry",
            "Filmography", "Discography", "Awards and nominations"
         ]
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    async def _create_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=TCPConnector(ssl=self.ssl_context)
         )

    def _format_section(self, title: str, content: str) -> str:
        """Format a section with proper line breaks and spacing"""
        # Remove duplicate titles
        content = content.replace(title, "", 1).strip()
        
        # Special handling for different section types
        if title in ["Awards and nominations", "Filmography"]:
            #Convert run_together text into table format
            lines = []
            #Split by year indicators (4 digits)
            import re
            chunks = re.split(r'(\d{4})',content)
            for i in range(1, len(chunks),2):
                year = chunks[i]
                details = chunks[i + 1] if i + 1 < len(chunks) else ""
                # Add proper spacing between fields
                formatted_line = f"{year}{details}"
                formatted_line + re.sub(r'([A-Z][a-z]+)', r'\n\1', formatted_line)
                lines.append(formatted_line)           

            formatted_content = "\n".join(lines)
            return f"\n{title}\n{'='*len(title)}\n{formatted_content}\n"
        
        elif "Discography" in title:
            # Special handling for discography section
            lines = content.split("\n")
            formatted_lines = []
            current_category = ""
            
            for line in lines:
                line = line.strip()
                if line in ["Studio albums", "Collaborative albums"]:
                    current_category = line
                    formatted_lines.append(f"\n{current_category}:")
                elif line and current_category:
                    formatted_lines.append(f"• {line}")
            return f"\n{title}\n{'='*len(title)}\n{''.join(formatted_lines)}\n"
        
        else:
            #Regular text formatting
            paragraphs = content.split("\n")
            formatted = "\n".join(para.strip() for para in paragraphs if para.strip())
            return f"\n{title}\n{'='*len(title)}\n{formatted}\n"
        
    async def get_artist_details(self, artist_name: str) -> str:
        if not isinstance(artist_name, str):
            return "No biography available"

        try:
            async with await self._create_session() as session:
                 # Step 1: Get all sections
                params = {
                    "action": "parse",
                    "page": artist_name.title(),  # Ensure proper capitalization
                    "format": "json",
                    "prop": "sections"
                }
                
                async with session.get(self.base_url, params=params) as response:
                    data = await response.json()    
                     # Check if page exists
                    if "error" in data:
                        print(f"Page not found for {artist_name}")
                        return "No biography available"
                    
                    sections = data.get("parse", {}).get("sections", [])                    
                     # Step 2: Extract section indices for desired topics
                    section_indices = {
                        s["line"]: s["index"] 
                        for s in sections 
                        if s["line"].lower() in [section.lower() for section in self.desired_sections]
                    }
                    
                    if not section_indices:
                        print(f"No matching sections found for {artist_name}")
                        return "No biography available"
                    
                     # Step 3: Fetch content for each section
                    biography_sections = []
                    for section_name, index in section_indices.items():
                        section_params = {
                            "action": "parse",
                            "page": artist_name.title(),
                            "format": "json",
                            "prop": "wikitext",
                            "section": index
                        }
                        
                        async with session.get(self.base_url, params=section_params) as section_response:
                            section_data = await section_response.json()
                            wikitext = section_data.get("parse", {}).get("wikitext", {}).get("*", "")
                            if wikitext:
                                parsed_text = mwparserfromhell.parse(wikitext).strip_code()
                                if parsed_text:
                                    formatted_section = self._format_section(section_name, parsed_text)
                                    biography_sections.append(formatted_section)
                    
                    if biography_sections:
                        full_bio = "ARTIST BIOGRAPHY\n" + "="*16 + "\n\n"
                        full_bio += "\n".join(biography_sections)
                        return full_bio
                    return "No biography available"

        except Exception as e:
            print(f"Error fetching artist details for {artist_name}: {e}")
            return "No biography available"
