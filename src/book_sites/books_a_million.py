import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
from urllib.parse import urljoin, quote_plus, urlparse
import re
from typing import List, Dict, Optional
import random
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BooksAMillionScraper:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://www.booksamillion.com"
        self.search_url = "https://www.booksamillion.com/search"
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
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
            "Referer": "https://www.booksamillion.com/"
        })
        
    def make_request_with_retry(self, url: str, max_retries: int = 3, timeout: int = 30) -> Optional[requests.Response]:
        """Make HTTP request with retry logic and error handling"""
        for attempt in range(max_retries):
            try:
                self.update_headers()
                if attempt > 0:
                    delay = random.uniform(3, 7)
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

    def search_books_a_million(self, book_query: str, max_results: int = 5) -> List[Dict]:
        """Search Books-A-Million for books"""
        try:
            # Encode the search query for Books-A-Million
            search_params = {
                'query': book_query,
                'category': 'books'
            }
            
            logger.info(f"Searching Books-A-Million for: {book_query}")
            
            response = self.make_request_with_retry(
                f"{self.search_url}?query={quote_plus(book_query)}&category=books", 
                timeout=20
            )
            if not response:
                logger.error("Failed to get search results from Books-A-Million")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Find book containers - Books-A-Million uses different selectors
            # Try multiple possible selectors
            book_containers = []
            
            # Common selectors for Books-A-Million
            selectors_to_try = [
                'div[class*="product-item"]',
                'div[class*="search-result"]',
                'div[class*="book-item"]',
                'div[class*="product-tile"]',
                'div[class*="item-container"]',
                'div[data-testid*="product"]',
                'div[class*="product-card"]',
                'div[class*="result-item"]'
            ]
            
            for selector in selectors_to_try:
                book_containers = soup.select(selector)
                if book_containers:
                    logger.info(f"Found {len(book_containers)} containers using selector: {selector}")
                    break
            
            # If no specific containers found, try more general approach
            if not book_containers:
                # Look for containers with book-related attributes
                book_containers = soup.find_all('div', class_=re.compile(r'product|item|result|tile|card'))
                book_containers = [c for c in book_containers if self._looks_like_book_container(c)]
            
            logger.info(f"Found {len(book_containers)} book containers")
            
            count = 0
            for container in book_containers[:max_results * 2]:  # Get more to account for filtering
                book_data = self.extract_book_details_bam(container, soup)
                if book_data and count < max_results:
                    results.append(book_data)
                    count += 1
                
                # Add delay between extractions
                time.sleep(random.uniform(1, 2))
            
            logger.info(f"Successfully extracted {len(results)} books from Books-A-Million")
            return results
            
        except Exception as e:
            logger.error(f"Error searching Books-A-Million: {str(e)}")
            return []
    
    def _looks_like_book_container(self, container) -> bool:
        """Check if a container looks like it contains book information"""
        container_text = container.get_text().lower()
        container_html = str(container).lower()
        
        # Look for book-related indicators
        book_indicators = ['title', 'author', 'price', 'isbn', 'book', 'product']
        
        indicator_count = sum(1 for indicator in book_indicators 
                            if indicator in container_text or indicator in container_html)
        
        return indicator_count >= 2
    
    def extract_book_details_bam(self, container, full_soup) -> Optional[Dict]:
        """Extract book details from Books-A-Million search result container"""
        try:
            # Initialize default values
            title = "Unknown Title"
            author = "Unknown Author"
            publisher = "Unknown Publisher"
            pub_year = "Unknown"
            isbn = "N/A"
            price = "N/A"
            book_url = "N/A"
            rating = "N/A"
            format = "N/A"
            
            # Extract title - Try multiple approaches
            title_elem = None
            
            # Try Books-A-Million specific selectors
            title_selectors = [
                'h3 a',
                'h4 a',
                'a[class*="title"]',
                'a[class*="product-title"]',
                'div[class*="title"] a',
                'span[class*="title"]',
                '[data-testid*="title"] a',
                'a[href*="/p/"]'  # Books-A-Million product URLs often contain /p/
            ]
            
            for selector in title_selectors:
                title_elem = container.select_one(selector)
                if title_elem:
                    break
            
            if title_elem:
                title = title_elem.get('title') or title_elem.get_text(strip=True)
                # Get URL from title link
                if title_elem.get('href'):
                    book_url = urljoin(self.base_url, title_elem['href'])
            
            # Extract author
            author_elem = None
            author_selectors = [
                'span[class*="author"]',
                'div[class*="author"]',
                'a[class*="author"]',
                '[data-testid*="author"]',
                'p[class*="author"]'
            ]
            
            for selector in author_selectors:
                author_elem = container.select_one(selector)
                if author_elem:
                    break
            
            if not author_elem:
                # Look for "by" text pattern
                by_text = container.find(text=re.compile(r'by\s+\w+', re.I))
                if by_text:
                    author_elem = by_text.parent
            
            if author_elem:
                author = author_elem.get_text(strip=True)
                author = re.sub(r'^by\s+', '', author, flags=re.I)  # Remove "by" prefix
            
            # Extract price
            price_elem = None
            price_selectors = [
                'span[class*="price"]',
                'div[class*="price"]',
                '[data-testid*="price"]',
                'span[class*="cost"]',
                'div[class*="cost"]'
            ]
            
            for selector in price_selectors:
                price_elem = container.select_one(selector)
                if price_elem and '$' in price_elem.get_text():
                    break
            
            if price_elem:
                price = price_elem.get_text(strip=True)
                # Clean up price - extract just the price part
                price_match = re.search(r'\$[\d,]+\.?\d*', price)
                if price_match:
                    price = price_match.group()
            
            # Extract rating
            rating_elem = None
            rating_selectors = [
                'span[class*="rating"]',
                'div[class*="rating"]',
                'div[class*="stars"]',
                '[data-testid*="rating"]'
            ]
            
            for selector in rating_selectors:
                rating_elem = container.select_one(selector)
                if rating_elem:
                    break
            
            if rating_elem:
                rating = rating_elem.get_text(strip=True)
                # Extract numeric rating if possible
                rating_match = re.search(r'(\d+\.?\d*)', rating)
                if rating_match:
                    rating = rating_match.group()
            
            # Extract format
            format_elem = None
            format_selectors = [
                'span[class*="format"]',
                'div[class*="format"]',
                'span[class*="binding"]',
                'div[class*="binding"]'
            ]
            
            for selector in format_selectors:
                format_elem = container.select_one(selector)
                if format_elem:
                    break
            
            if format_elem:
                format = format_elem.get_text(strip=True)
            
            # If we have a book URL, try to get more details from the product page
            if book_url != "N/A":
                detailed_info = self.get_book_details_from_page(book_url)
                if detailed_info:
                    publisher = detailed_info.get('publisher', publisher)
                    pub_year = detailed_info.get('pub_year', pub_year)
                    isbn = detailed_info.get('isbn', isbn)
                    if format == "N/A":
                        format = detailed_info.get('format', format)
            
            # Clean up extracted data
            title = self.clean_text(title)
            author = self.clean_text(author)
            publisher = self.clean_text(publisher)
            
            # Skip if we don't have meaningful data
            if title == "Unknown Title" and author == "Unknown Author":
                return None
            
            return {
                "Site": "Books-A-Million",
                "Title": title,
                "Author": author,
                "Publisher": publisher,
                "Publication_Year": pub_year,
                "ISBN": isbn,
                "Price": price,
                "Rating": rating,
                "URL": book_url,
                "Format": format,
            }
            
        except Exception as e:
            logger.error(f"Error extracting Books-A-Million book details: {str(e)}")
            return None
    
    def get_book_details_from_page(self, book_url: str) -> Optional[Dict]:
        """Get additional book details from individual product page"""
        try:
            response = self.make_request_with_retry(book_url, timeout=15)
            if not response:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            details = {}
            
            # Look for product details in various sections
            # Try to find structured product information
            
            # Method 1: Look for product details table/list
            details_section = soup.find('div', class_=re.compile(r'product-details|book-details|item-details'))
            if details_section:
                # Look for key-value pairs in dt/dd format
                for dt in details_section.find_all('dt'):
                    dt_text = dt.get_text(strip=True).lower()
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        dd_text = dd.get_text(strip=True)
                        
                        if 'publisher' in dt_text:
                            details['publisher'] = dd_text
                        elif 'publication' in dt_text or 'publish' in dt_text:
                            year_match = re.search(r'\d{4}', dd_text)
                            if year_match:
                                details['pub_year'] = year_match.group()
                        elif 'isbn' in dt_text:
                            isbn_match = re.search(r'[\d-]{10,17}', dd_text)
                            if isbn_match:
                                details['isbn'] = isbn_match.group()
                        elif 'format' in dt_text or 'binding' in dt_text:
                            details['format'] = dd_text
            
            # Method 2: Look for structured data in meta tags or JSON-LD
            json_ld = soup.find('script', {'type': 'application/ld+json'})
            if json_ld:
                try:
                    data = json.loads(json_ld.string)
                    if isinstance(data, dict):
                        if 'publisher' in data:
                            details['publisher'] = data['publisher']
                        if 'datePublished' in data:
                            year_match = re.search(r'\d{4}', data['datePublished'])
                            if year_match:
                                details['pub_year'] = year_match.group()
                        if 'isbn' in data:
                            details['isbn'] = data['isbn']
                        if 'bookFormat' in data:
                            details['format'] = data['bookFormat']
                except json.JSONDecodeError:
                    pass
            
            # Method 3: Look for specific meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                if meta.get('name') == 'book:author':
                    # Sometimes author info is in meta tags
                    continue
                elif meta.get('property') == 'book:isbn':
                    details['isbn'] = meta.get('content', '')
                elif meta.get('property') == 'book:release_date':
                    year_match = re.search(r'\d{4}', meta.get('content', ''))
                    if year_match:
                        details['pub_year'] = year_match.group()
            
            # Method 4: Look for product specifications in a table
            spec_table = soup.find('table', class_=re.compile(r'spec|detail|product'))
            if spec_table:
                rows = spec_table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        
                        if 'publisher' in key:
                            details['publisher'] = value
                        elif 'publication' in key or 'publish' in key:
                            year_match = re.search(r'\d{4}', value)
                            if year_match:
                                details['pub_year'] = year_match.group()
                        elif 'isbn' in key:
                            isbn_match = re.search(r'[\d-]{10,17}', value)
                            if isbn_match:
                                details['isbn'] = isbn_match.group()
                        elif 'format' in key or 'binding' in key:
                            details['format'] = value
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting book details from page {book_url}: {str(e)}")
            return None
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return "Unknown"
        
        # Remove extra whitespace and newlines
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove common prefixes
        text = re.sub(r'^(by\s+)', '', text, flags=re.I)
        
        # Remove HTML entities
        text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)
        
        return text if text else "Unknown"
    
    def search_by_isbn(self, isbn: str) -> List[Dict]:
        """Search Books-A-Million by ISBN"""
        return self.search_books_a_million(isbn, max_results=1)
    
    def search_by_title_author(self, title: str, author: str = "") -> List[Dict]:
        """Search Books-A-Million by title and author"""
        query = f"{title} {author}".strip()
        return self.search_books_a_million(query)

    def save_to_excel(self, data: List[Dict], filename: str = "books_a_million_books.xlsx") -> None:
        """Save book data to Excel"""
        if not data:
            logger.warning("No data to save")
            return
        
        df = pd.DataFrame(data)
        #df["Date_Scraped"] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            df.to_excel(filename, index=False)
            logger.info(f"Data saved to {filename}")
            logger.info(f"Total books found: {len(df)}")
            
            # Print summary
            print(f"\nScraping Summary:")
            print(f"Total books scraped: {len(df)}")
            print(f"File saved as: {filename}")
            
            # Show sample of data
            if len(df) > 0:
                print(f"\nSample of scraped data:")
                print(df[['Title', 'Author', 'Price']].head().to_string(index=False))
                
        except Exception as e:
            logger.error(f"Error saving to Excel: {str(e)}")

    def save_to_csv(self, data: List[Dict], filename: str = "books_a_million_books.csv") -> None:
        """Save book data to CSV"""
        if not data:
            logger.warning("No data to save")
            return
        
        df = pd.DataFrame(data)
        #df["Date_Scraped"] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            df.to_csv(filename, index=False)
            logger.info(f"Data saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving to CSV: {str(e)}")


# Example usage
if __name__ == "__main__":
    scraper = BooksAMillionScraper()
    
    # Example searches
    search_queries = [
        "Can't Hurt Me",
        "Atomic Habits",
        "The Psychology of Money"
    ]
    
    all_results = []
    
    for query in search_queries:
        print(f"\nSearching for: {query}")
        results = scraper.search_books_a_million(query, max_results=2)
        all_results.extend(results)
        
        # Add delay between searches
        time.sleep(random.uniform(2, 4))
    
    # Save results
    if all_results:
        scraper.save_to_excel(all_results)
        scraper.save_to_csv(all_results)
        
        # Print results
        for result in all_results:
            print(f"\nTitle: {result['Title']}")
            print(f"Author: {result['Author']}")
            print(f"Price: {result['Price']}")
            print(f"URL: {result['URL']}")
    else:
        print("No results found!")
        
    print("\nIMPORTANT NOTES:")
    print("1. Books-A-Million may block automated scraping via robots.txt")
    print("2. Always respect rate limits and add delays between requests")
    print("3. Consider using their API if available for commercial use")
    print("4. This scraper is for educational purposes only")