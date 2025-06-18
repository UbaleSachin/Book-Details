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

class ThriftBooksBookScraper:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://www.thriftbooks.com"
        self.search_url = "https://www.thriftbooks.com/browse/"
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]
        self.update_headers()
    
    def update_headers(self):
        """Update headers with random user agent and ThriftBooks-specific headers"""
        self.session.headers.update({
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
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
            "Sec-CH-UA": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"'
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

    def search_thriftbooks(self, book_query: str, max_results: int = 5) -> List[Dict]:
        """Search ThriftBooks for books"""
        try:
            # First, visit the homepage to establish session
            logger.info("Establishing session with ThriftBooks...")
            home_response = self.make_request_with_retry(self.base_url, timeout=15)
            if not home_response:
                logger.error("Failed to establish session with ThriftBooks")
                return []
            
            # Add a small delay
            time.sleep(random.uniform(1, 3))
            
            # Build search URL with parameters
            search_params = {
                'b.search': book_query,
                'b.p': '1'  # page number
            }
            
            # Construct URL manually to avoid encoding issues
            search_url = f"{self.search_url}?b.search={quote_plus(book_query)}"
            
            logger.info(f"Searching ThriftBooks for: {book_query}")
            logger.info(f"Search URL: {search_url}")
            
            response = self.make_request_with_retry(search_url, timeout=20)
            if not response:
                logger.error("Failed to get search results from ThriftBooks")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Debug: Print some of the page content to understand structure
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Page title: {soup.title.string if soup.title else 'No title'}")
            
            # Find book containers - Try multiple ThriftBooks selectors
            book_containers = []
            
            # Try primary selector
            book_containers = soup.find_all('div', class_='SearchResultListItem')
            if book_containers:
                logger.info(f"Found {len(book_containers)} books using SearchResultListItem")
            
            # Try alternative selectors if primary fails
            if not book_containers:
                book_containers = soup.find_all('div', class_=re.compile(r'AllEditionsItem'))
                if book_containers:
                    logger.info(f"Found {len(book_containers)} books using AllEditionsItem")
            
            if not book_containers:
                book_containers = soup.find_all('div', class_=re.compile(r'bookItem'))
                if book_containers:
                    logger.info(f"Found {len(book_containers)} books using bookItem")
            
            if not book_containers:
                # Try more generic selectors
                book_containers = soup.find_all('div', class_=re.compile(r'item|result|book'))
                if book_containers:
                    logger.info(f"Found {len(book_containers)} books using generic selectors")
            
            if not book_containers:
                # Check if we're being blocked or redirected
                if "access denied" in soup.get_text().lower() or "blocked" in soup.get_text().lower():
                    logger.error("Access appears to be blocked by ThriftBooks")
                else:
                    logger.warning("No book containers found. Page structure may have changed.")
                    # Print first 1000 chars of HTML for debugging
                    logger.debug(f"HTML snippet: {str(soup)[:1000]}...")
                return []
            
            count = 0
            for container in book_containers[:max_results * 2]:  # Get more to account for filtering
                book_data = self.extract_book_details_tb(container, soup)
                if book_data and count < max_results:
                    results.append(book_data)
                    count += 1
                
                # Add delay between extractions
                time.sleep(random.uniform(0.5, 1.5))
            
            logger.info(f"Successfully extracted {len(results)} books from ThriftBooks")
            return results
            
        except Exception as e:
            logger.error(f"Error searching ThriftBooks: {str(e)}")
            return []
    
    def extract_book_details_tb(self, container, full_soup) -> Optional[Dict]:
        """Extract book details from ThriftBooks search result container"""
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
            condition = "N/A"
            
            # Extract title
            title_elem = container.find('a', class_='AllEditionsItem-tile-title')
            if not title_elem:
                title_elem = container.find('h3') or container.find('a', class_=re.compile(r'title|book-title'))
            if not title_elem:
                title_elem = container.find('div', class_=re.compile(r'title'))
                if title_elem:
                    title_link = title_elem.find('a')
                    if title_link:
                        title_elem = title_link
            
            if title_elem:
                title = title_elem.get_text(strip=True)
                # Get URL from title link
                if title_elem.get('href'):
                    book_url = urljoin(self.base_url, title_elem['href'])
            
            # Extract author
            author_elem = container.find('div', class_='AllEditionsItem-tile-author')
            if not author_elem:
                author_elem = container.find('span', class_=re.compile(r'author|by-author'))
            if not author_elem:
                author_elem = container.find('div', class_=re.compile(r'author'))
            
            if author_elem:
                # Look for author link within the author container
                author_link = author_elem.find('a')
                if author_link:
                    author = author_link.get_text(strip=True)
                else:
                    author = author_elem.get_text(strip=True)
                    # Clean up "by" prefix if present
                    author = re.sub(r'^by\s+', '', author, flags=re.I)
            
            # Extract price
            price_elem = container.find('div', class_='SearchResultListItem-price')
            if not price_elem:
                price_elem = container.find('span', class_=re.compile(r'price|cost'))
            if not price_elem:
                price_elem = container.find('div', class_=re.compile(r'price'))
            
            if price_elem:
                # ThriftBooks often shows "from $X.XX" format
                price_text = price_elem.get_text(strip=True)
                # Extract price using regex
                price_match = re.search(r'\$[\d.]+', price_text)
                if price_match:
                    price = price_match.group()
                else:
                    price = price_text
            
            # Extract condition (specific to ThriftBooks)
            condition_elem = container.find('div', class_=re.compile(r'condition'))
            if not condition_elem:
                condition_elem = container.find('span', class_=re.compile(r'condition'))
            if condition_elem:
                condition = condition_elem.get_text(strip=True)
            
            # Extract format
            format_elem = container.find('div', class_=re.compile(r'format|binding'))
            if not format_elem:
                format_elem = container.find('span', class_=re.compile(r'format|binding'))
            if format_elem:
                format = format_elem.get_text(strip=True)
            
            # Extract rating
            rating_elem = container.find('div', class_=re.compile(r'rating|stars'))
            if not rating_elem:
                rating_elem = container.find('span', class_=re.compile(r'rating|stars'))
            if rating_elem:
                rating = rating_elem.get_text(strip=True)
                # Look for star ratings or numeric ratings
                star_match = re.search(r'(\d+\.?\d*)\s*(?:out of|/)\s*5', rating)
                if star_match:
                    rating = f"{star_match.group(1)}/5"
            
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
                "Site": "ThriftBooks",
                "Title": title,
                "Author": author,
                "Publisher": publisher,
                "Publication_Year": pub_year,
                "ISBN": isbn,
                "Price": price,
                "Rating": rating,
                "URL": book_url,
                "Format": format,
                "Condition": condition,
            }
            
        except Exception as e:
            logger.error(f"Error extracting ThriftBooks book details: {str(e)}")
            return None
    
    def get_book_details_from_page(self, book_url: str) -> Optional[Dict]:
        """Get additional book details from individual product page"""
        try:
            response = self.make_request_with_retry(book_url, timeout=15)
            if not response:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            details = {}
            
            # Look for book details section
            details_section = soup.find('div', class_=re.compile(r'book-details|product-details'))
            
            if details_section:
                # Look for structured data in dl/dt/dd format
                for dt in details_section.find_all('dt'):
                    dt_text = dt.get_text(strip=True).lower()
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        dd_text = dd.get_text(strip=True)
                        if 'publisher' in dt_text:
                            details['publisher'] = dd_text
                        elif 'publication' in dt_text or 'published' in dt_text:
                            year_match = re.search(r'\d{4}', dd_text)
                            if year_match:
                                details['pub_year'] = year_match.group()
                        elif 'isbn' in dt_text:
                            isbn_match = re.search(r'[\d-]{10,17}', dd_text)
                            if isbn_match:
                                details['isbn'] = isbn_match.group()
                        elif 'format' in dt_text or 'binding' in dt_text:
                            details['format'] = dd_text
            
            # Alternative: Look for meta tags with book information
            meta_tags = soup.find_all('meta', attrs={'property': re.compile(r'book:|og:')})
            for meta in meta_tags:
                property_name = meta.get('property', '').lower()
                content = meta.get('content', '')
                if 'book:author' in property_name:
                    details['author'] = content
                elif 'book:isbn' in property_name:
                    details['isbn'] = content
                elif 'book:release_date' in property_name:
                    year_match = re.search(r'\d{4}', content)
                    if year_match:
                        details['pub_year'] = year_match.group()
            
            # Look for JSON-LD structured data
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        if data.get('@type') == 'Book':
                            if 'publisher' in data:
                                pub_info = data['publisher']
                                if isinstance(pub_info, dict):
                                    details['publisher'] = pub_info.get('name', '')
                                else:
                                    details['publisher'] = str(pub_info)
                            
                            if 'datePublished' in data:
                                year_match = re.search(r'\d{4}', data['datePublished'])
                                if year_match:
                                    details['pub_year'] = year_match.group()
                            
                            if 'isbn' in data:
                                details['isbn'] = data['isbn']
                            
                            if 'bookFormat' in data:
                                details['format'] = data['bookFormat']
                except json.JSONDecodeError:
                    continue
            
            # Look for publication info in specific ThriftBooks elements
            pub_info = soup.find('div', class_=re.compile(r'publication-info'))
            if pub_info:
                pub_text = pub_info.get_text()
                # Extract year
                year_match = re.search(r'\b(19|20)\d{2}\b', pub_text)
                if year_match:
                    details['pub_year'] = year_match.group()
                
                # Extract publisher (usually comes before the year)
                pub_match = re.search(r'([^,]+?)(?:,\s*\d{4})', pub_text)
                if pub_match:
                    details['publisher'] = pub_match.group(1).strip()
            
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
        
        return text if text else "Unknown"
    
    def search_by_isbn(self, isbn: str) -> List[Dict]:
        """Search ThriftBooks by ISBN"""
        return self.search_thriftbooks(isbn, max_results=1)
    
    def search_by_title_author(self, title: str, author: str = "") -> List[Dict]:
        """Search ThriftBooks by title and author"""
        query = f"{title} {author}".strip()
        return self.search_thriftbooks(query)

    def save_to_excel(self, data: List[Dict], filename: str = "thriftbooks_books.xlsx") -> None:
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
            
            # Print summary
            print(f"\nScraping Summary:")
            print(f"Total books scraped: {len(df)}")
            print(f"File saved as: {filename}")
            
            # Show sample of data
            if len(df) > 0:
                print(f"\nSample of scraped data:")
                print(df[['Title', 'Author', 'Price', 'Condition']].head().to_string(index=False))
                
        except Exception as e:
            logger.error(f"Error saving to Excel: {str(e)}")

    def save_to_csv(self, data: List[Dict], filename: str = "thriftbooks_books.csv") -> None:
        """Save book data to CSV"""
        if not data:
            logger.warning("No data to save")
            return
        
        df = pd.DataFrame(data)
        df["Date_Scraped"] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            df.to_csv(filename, index=False)
            logger.info(f"Data saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving to CSV: {str(e)}")


# Example usage
if __name__ == "__main__":
    scraper = ThriftBooksBookScraper()
    
    # Example searches
    search_queries = [
        "Can't Hurt Me",
    ]
    
    all_results = []
    
    for query in search_queries:
        print(f"\nSearching for: {query}")
        results = scraper.search_thriftbooks(query, max_results=1)
        all_results.extend(results)
        
        # Add delay between searches
        time.sleep(random.uniform(2, 4))
    
    # Save results
    if all_results:
        scraper.save_to_excel(all_results)
        scraper.save_to_csv(all_results)
    else:
        print("No results found!")