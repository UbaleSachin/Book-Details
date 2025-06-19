import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
from urllib.parse import urljoin, quote_plus
import re
from typing import List, Dict, Optional
import random
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BetterWorldBooksScraper:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://www.betterworldbooks.com"
        self.search_url = "https://www.betterworldbooks.com/search/results"
        
        # More comprehensive user agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        # Setup session with retry strategy
        self.setup_session()
        self.update_headers()

    def setup_session(self):
        """Setup session with retry strategy and connection pooling"""
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def update_headers(self):
        """Update headers with random user agent and realistic browser headers"""
        self.headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"'
        }
        self.session.headers.update(self.headers)

    def get_initial_session(self):
        """Visit homepage first to establish session"""
        try:
            logger.info("Establishing initial session...")
            self.update_headers()
            response = self.session.get(self.base_url, timeout=15)
            if response.status_code == 200:
                logger.info("Initial session established successfully")
                # Add random delay
                time.sleep(random.uniform(2, 4))
                return True
            else:
                logger.warning(f"Initial session returned status code: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to establish initial session: {str(e)}")
            return False

    def make_request_with_retry(self, url: str, max_retries: int = 3, timeout: int = 30) -> Optional[requests.Response]:
        """Make HTTP request with retry logic and error handling"""
        for attempt in range(max_retries):
            try:
                # Update headers for each attempt
                self.update_headers()
                
                if attempt > 0:
                    delay = random.uniform(3, 8)  # Longer delays
                    logger.info(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s delay")
                    time.sleep(delay)
                
                # Add random delay before each request
                time.sleep(random.uniform(1, 3))
                
                response = self.session.get(url, timeout=timeout)
                
                if response.status_code == 403:
                    logger.warning(f"403 Forbidden on attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        # Try to re-establish session
                        self.get_initial_session()
                    continue
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed on attempt {attempt + 1}/{max_retries}: {str(e)}")
                if "403" in str(e):
                    # For 403 errors, try longer delays
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(5, 10))
        
        return None

    def search_better_world_books(self, book_query: str, max_results: int = 5) -> List[Dict]:
        """Search Better World Books for books"""
        try:
            # First establish session
            if not self.get_initial_session():
                logger.error("Could not establish initial session")
                return []
            
            # Try different search approaches
            search_urls = [
                f"{self.search_url}?q={quote_plus(book_query)}",
                f"{self.base_url}/search?q={quote_plus(book_query)}",
                f"{self.base_url}/search/results?query={quote_plus(book_query)}"
            ]

            logger.info(f"Searching Better World Books for: {book_query}")
            
            response = None
            for search_url in search_urls:
                logger.info(f"Trying search URL: {search_url}")
                response = self.make_request_with_retry(search_url, timeout=15)
                if response:
                    break
                time.sleep(random.uniform(2, 4))
            
            if not response:
                logger.error("Failed to get search results from Better World Books")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Try multiple selectors for book containers
            selectors = [
                '.product-item',
                '.book-item', 
                '.search-result',
                '.product',
                '.book',
                '[data-testid="product"]',
                '.result-item'
            ]
            
            book_containers = []
            for selector in selectors:
                containers = soup.select(selector)
                if containers:
                    book_containers = containers
                    logger.info(f"Found {len(containers)} containers with selector: {selector}")
                    break
            
            if not book_containers:
                logger.warning("No book containers found. Trying alternative approach...")
                # Try to find any links that might be book results
                book_containers = soup.select('a[href*="/product"], a[href*="/book"]')
                if book_containers:
                    logger.info(f"Found {len(book_containers)} potential book links")
            
            if not book_containers:
                logger.warning("No book containers found. Page structure may have changed.")
                # Save HTML for debugging
                with open('debug_page.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                logger.info("Saved page HTML to debug_page.html for inspection")
                return []
            
            count = 0
            for container in book_containers[:max_results * 2]:
                book_data = self.extract_book_details(container)
                if book_data and count < max_results:
                    results.append(book_data)
                    count += 1
                
                # Random delay between extractions
                time.sleep(random.uniform(0.5, 2))
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Better World Books: {str(e)}")
            return []

    def extract_book_details(self, container) -> Optional[Dict]:
        """Extract book details from search result container"""
        try:
            # Extract basic information with multiple selector attempts
            title = self.extract_title(container)
            book_url = self.extract_url(container)
            author = self.extract_author(container)
            price = self.extract_price(container)
            format_info = self.extract_format(container)
            
            # Get additional details from product page if URL available
            additional_details = {}
            if book_url and book_url != "N/A":
                time.sleep(random.uniform(1, 3))  # Delay before detail page request
                additional_details = self.get_book_details_from_page(book_url)
            
            # Combine all details
            book_details = {
                "Site": "Better World Books",
                "Title": title,
                "Author": author,
                "Publisher": additional_details.get('publisher', 'Unknown Publisher'),
                "Publication_Year": additional_details.get('pub_year', 'Unknown'),
                "ISBN": additional_details.get('isbn', 'N/A'),
                "Price": price,
                "URL": book_url,
                "Format": format_info
            }
            
            return book_details
            
        except Exception as e:
            logger.error(f"Error extracting book details: {str(e)}")
            return None

    def extract_title(self, container) -> str:
        """Extract book title with multiple selector attempts"""
        selectors = [
            '.product-title',
            '.book-title',
            'h2 a',
            'h3 a',
            '.title',
            '[data-testid="title"]',
            'a[title]'
        ]
        
        for selector in selectors:
            title_elem = container.select_one(selector)
            if title_elem:
                title = title_elem.get('title') or title_elem.get_text(strip=True)
                if title and len(title) > 3:
                    return self.clean_text(title)
        
        return "Unknown Title"

    def extract_url(self, container) -> str:
        """Extract book URL with multiple selector attempts"""
        selectors = [
            'a[href*="/product"]',
            'a[href*="/book"]',
            'a[href*="/item"]',
            'a[href]'
        ]
        
        for selector in selectors:
            url_elem = container.select_one(selector)
            if url_elem and url_elem.get('href'):
                href = url_elem['href']
                if '/product' in href or '/book' in href or '/item' in href:
                    return urljoin(self.base_url, href)
        
        return "N/A"

    def extract_author(self, container) -> str:
        """Extract author name with multiple selector attempts"""
        selectors = [
            '.author',
            '.product-author',
            '.by-author',
            '[data-testid="author"]'
        ]
        
        for selector in selectors:
            author_elem = container.select_one(selector)
            if author_elem:
                author = author_elem.get_text(strip=True)
                author = re.sub(r'^by\s+', '', author, flags=re.I)
                if author and len(author) > 2:
                    return self.clean_text(author)
        
        return "Unknown Author"

    def extract_price(self, container) -> str:
        """Extract book price with multiple selector attempts"""
        selectors = [
            '.price',
            '.product-price',
            '.cost',
            '[data-testid="price"]'
        ]
        
        for selector in selectors:
            price_elem = container.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text()
                price_match = re.search(r'\$[\d.,]+', price_text)
                if price_match:
                    return price_match.group(0)
        
        return "N/A"

    def extract_format(self, container) -> str:
        """Extract book format with multiple selector attempts"""
        selectors = [
            '.format',
            '.binding',
            '.book-format',
            '[data-testid="format"]'
        ]
        
        for selector in selectors:
            format_elem = container.select_one(selector)
            if format_elem:
                format_text = format_elem.get_text(strip=True)
                if format_text and len(format_text) > 1:
                    return self.clean_text(format_text)
        
        return "N/A"

    def get_book_details_from_page(self, book_url: str) -> Dict:
        """Get additional book details from product page"""
        try:
            response = self.make_request_with_retry(book_url, timeout=20)
            if not response:
                return {}

            soup = BeautifulSoup(response.content, 'html.parser')
            details = {}

            # Extract publisher with multiple selectors
            publisher_selectors = ['.publisher', '[itemprop="publisher"]', '.pub-info']
            for selector in publisher_selectors:
                publisher_elem = soup.select_one(selector)
                if publisher_elem:
                    details['publisher'] = self.clean_text(publisher_elem.get_text())
                    break

            # Extract publication year
            date_selectors = ['.publication-date', '[itemprop="datePublished"]', '.pub-date']
            for selector in date_selectors:
                pub_date_elem = soup.select_one(selector)
                if pub_date_elem:
                    year_match = re.search(r'\d{4}', pub_date_elem.get_text())
                    if year_match:
                        details['pub_year'] = year_match.group()
                        break

            # Extract ISBN
            isbn_selectors = ['.isbn', '[itemprop="isbn"]', '.product-isbn']
            for selector in isbn_selectors:
                isbn_elem = soup.select_one(selector)
                if isbn_elem:
                    isbn = isbn_elem.get_text(strip=True)
                    isbn_match = re.search(r'[\d-]{10,17}', isbn)
                    if isbn_match:
                        details['isbn'] = isbn_match.group()
                        break

            return details

        except Exception as e:
            logger.error(f"Error getting book details from page {book_url}: {str(e)}")
            return {}

    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return "Unknown"
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "Unknown"

    def save_to_excel(self, data: List[Dict], filename: str = "better_world_books.xlsx") -> None:
        """Save book data to Excel"""
        if not data:
            logger.warning("No data to save")
            return
        
        df = pd.DataFrame(data)
        try:
            df.to_excel(filename, index=False)
            logger.info(f"Data saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving to Excel: {str(e)}")

    def save_to_csv(self, data: List[Dict], filename: str = "better_world_books.csv") -> None:
        """Save book data to CSV"""
        if not data:
            logger.warning("No data to save")
            return
        
        df = pd.DataFrame(data)
        try:
            df.to_csv(filename, index=False)
            logger.info(f"Data saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving to CSV: {str(e)}")

if __name__ == "__main__":
    scraper = BetterWorldBooksScraper()
    results = scraper.search_better_world_books("The Great Gatsby", max_results=3)
    
    if results:
        print(f"Found {len(results)} results:")
        for i, book in enumerate(results, 1):
            print(f"\n{i}. {book['Title']}")
            print(f"   Author: {book['Author']}")
            print(f"   Price: {book['Price']}")
            print(f"   URL: {book['URL']}")
        
        scraper.save_to_excel(results)
        scraper.save_to_csv(results)
    else:
        print("No results found!")