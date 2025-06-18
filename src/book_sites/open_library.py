import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
from urllib.parse import urljoin, quote_plus
import re
from typing import List, Dict, Optional
import random

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BookScraper:
    def __init__(self):
        self.session = requests.Session()
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ]
        self.update_headers()
    
    def update_headers(self):
        """Update headers with random user agent"""
        self.session.headers.update({
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })
        
    def make_request_with_retry(self, url: str, max_retries: int = 3, timeout: int = 30) -> Optional[requests.Response]:
        """Make HTTP request with retry logic and error handling"""
        for attempt in range(max_retries):
            try:
                self.update_headers()
                if attempt > 0:
                    delay = random.uniform(2, 5)
                    logger.info(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s delay")
                    time.sleep(delay)
                
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed on attempt {attempt + 1}/{max_retries}: {str(e)}")
        
        return None

    def search_open_library(self, book_query: str, max_results: int = 5) -> List[Dict]:
        """Search Open Library API for books"""
        try:
            if book_query.isdigit() or ('978' in book_query and len(book_query) >= 10):
                # ISBN search
                api_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{book_query}&format=json&jscmd=data"
            else:
                # Title/Author search
                encoded_query = quote_plus(book_query)
                api_url = f"https://openlibrary.org/search.json?q={encoded_query}&limit={max_results}"
            
            logger.info(f"Searching Open Library for: {book_query}")
            logger.info(f"API URL: {api_url}")
            
            response = self.make_request_with_retry(api_url, timeout=15)
            if not response:
                return []
            
            data = response.json()
            results = []
            
            if 'docs' in data:  # Search API response
                books = data['docs'][:max_results]
                for book in books:
                    book_data = self.extract_book_details_ol(book)
                    if book_data:
                        results.append(book_data)
            elif len(data) > 0:  # ISBN API response
                for isbn, book_info in data.items():
                    book_data = self.extract_book_details_ol_isbn(book_info, book_query)
                    if book_data:
                        results.append(book_data)
            
            logger.info(f"Found {len(results)} books from Open Library")
            return results
            
        except Exception as e:
            logger.error(f"Error searching Open Library: {str(e)}")
            return []
    
    def extract_book_details_ol(self, book_data: Dict) -> Optional[Dict]:
        """Extract book details from Open Library search API response"""
        try:
            title = book_data.get('title', 'Unknown Title')
            authors = book_data.get('author_name', ['Unknown Author'])
            author = ', '.join(authors) if isinstance(authors, list) else str(authors)
            pub_year = book_data.get('first_publish_year', 'Unknown')
            isbn_list = book_data.get('isbn', [])
            isbn = isbn_list[0] if isbn_list else 'N/A'
            publishers = book_data.get('publisher', [])
            publisher = publishers[0] if publishers else 'Unknown Publisher'
            ol_key = book_data.get('key', '')
            book_url = f"https://openlibrary.org{ol_key}" if ol_key else "N/A"
            
            return {
                "Site": "Open Library",
                "Title": title,
                "Author": author,
                "Publisher": publisher,
                "Publication_Year": pub_year,
                "ISBN": isbn,
                "URL": book_url
            }
            
        except Exception as e:
            logger.error(f"Error extracting Open Library book details: {str(e)}")
            return None
    
    def extract_book_details_ol_isbn(self, book_data: Dict, isbn: str) -> Optional[Dict]:
        """Extract book details from Open Library ISBN API response"""
        try:
            title = book_data.get('title', 'Unknown Title')
            authors = book_data.get('authors', [])
            author_names = [author.get('name', 'Unknown') for author in authors]
            author = ', '.join(author_names) if author_names else 'Unknown Author'
            publishers = book_data.get('publishers', [])
            publisher = publishers[0].get('name', 'Unknown Publisher') if publishers else 'Unknown Publisher'
            pub_date = book_data.get('publish_date', 'Unknown')
            book_url = book_data.get('url', f"https://openlibrary.org/isbn/{isbn}")
            
            return {
                "Site": "Open Library",
                "Title": title,
                "Author": author,
                "Publisher": publisher,
                "Publication_Year": pub_date,
                "ISBN": isbn,
                "URL": book_url
            }
            
        except Exception as e:
            logger.error(f"Error extracting Open Library ISBN book details: {str(e)}")
            return None

    def save_to_excel(self, data: List[Dict], filename: str = "book_results.xlsx") -> None:
        """Save book data to Excel"""
        if not data:
            logger.warning("No data to save")
            return
        
        df = pd.DataFrame(data)
        df["Date_Scraped"] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            df.to_excel(filename, index=False)
            logger.info(f"Data saved to {filename}")
            logger.info(f"Total books found: {len(df)}")
        except Exception as e:
            logger.error(f"Error saving to Excel: {str(e)}")

