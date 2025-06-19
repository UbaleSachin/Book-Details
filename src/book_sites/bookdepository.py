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

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BookDepositoryBookScraper:
    def __init__(self):
        self.session = requests.Session()
        self.driver = None
        self.base_url = "https://www.bookdepository.com"
        self.search_url = "https://www.amazon.com/s?k="
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]
        
        # Initialize headers
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        }
        
        # Update headers with random user agent
        self.update_headers()
    
    def update_headers(self):
        """Update headers with random user agent and BookDepository-specific headers"""
        self.headers.update({
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
        
        # Update session headers
        self.session.headers.update(self.headers)
        
    def setup_selenium_driver(self):
        """Setup Selenium WebDriver with proper configuration"""
        if self.driver:
            return self.driver
            
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(f"--user-agent={self.headers.get('User-Agent')}")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return self.driver
        
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
                
        # If requests fail, try with Selenium
        logger.info("Falling back to Selenium...")
        return self.make_selenium_request(url)
    
    def make_selenium_request(self, url: str) -> Optional[requests.Response]:
        """Make request using Selenium as fallback"""
        try:
            driver = self.setup_selenium_driver()
            driver.get(url)
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Create a mock response object
            class MockResponse:
                def __init__(self, content, url, status_code=200):
                    self.content = content.encode('utf-8')
                    self.text = content
                    self.url = url
                    self.status_code = status_code
                
                def raise_for_status(self):
                    if self.status_code >= 400:
                        raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            
            page_source = driver.page_source
            return MockResponse(page_source, url)
            
        except Exception as e:
            logger.error(f"Selenium request failed: {str(e)}")
            return None
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None

    def search_bookdepository(self, book_query: str, max_results: int = 5) -> List[Dict]:
        """Search BookDepository for books"""
        try:
            # First, visit the homepage to establish session
            logger.info("Establishing session with BookDepository...")
            home_response = self.make_request_with_retry(self.base_url, timeout=15)
            if not home_response:
                logger.error("Failed to establish session with BookDepository")
                return []
            
            # Add a small delay
            time.sleep(random.uniform(1, 3))
            
            # Construct search URL - BookDepository uses 'searchTerm' parameter
            search_url = f"{self.search_url}{quote_plus(book_query)}"
            
            logger.info(f"Searching BookDepository for: {book_query}")
            logger.info(f"Search URL: {search_url}")
            
            response = self.make_request_with_retry(search_url, timeout=20)
            if not response:
                logger.error("Failed to get search results from BookDepository")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Debug: Print some of the page content to understand structure
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Page title: {soup.title.string if soup.title else 'No title'}")
            
            # Find book containers - Try multiple BookDepository selectors
            book_containers = self.find_book_containers(soup)
            
            if not book_containers:
                # Check if we're being blocked or redirected
                page_text = soup.get_text().lower()
                if any(keyword in page_text for keyword in ["access denied", "blocked", "captcha", "please verify"]):
                    logger.error("Access appears to be blocked by BookDepository")
                else:
                    logger.warning("No book containers found. Page structure may have changed.")
                    # Print first 1000 chars of HTML for debugging
                    logger.debug(f"HTML snippet: {str(soup)[:1000]}...")
                return []
            
            count = 0
            for container in book_containers[:max_results * 2]:  # Get more to account for filtering
                book_data = self.extract_book_details_bd(container, soup)
                if book_data and count < max_results:
                    results.append(book_data)
                    count += 1
                
                # Add delay between extractions
                time.sleep(random.uniform(0.5, 1.5))
            
            logger.info(f"Successfully extracted {len(results)} books from BookDepository")
            return results
            
        except Exception as e:
            logger.error(f"Error searching BookDepository: {str(e)}")
            return []
    
    def find_book_containers(self, soup):
        """Find book containers using multiple selector strategies for BookDepository"""
        book_containers = []
        
        # BookDepository-specific selectors
        selectors = [
            ('div', {'class': 'book-item'}),
            ('div', {'class': re.compile(r'item-wrap')}),
            ('div', {'class': re.compile(r'book.*item')}),
            ('article', {'class': re.compile(r'book')}),
            ('div', {'itemtype': 'http://schema.org/Book'}),
            ('div', {'class': re.compile(r'search-result')}),
            ('div', {'class': re.compile(r'result.*item')}),
            ('div', {'class': re.compile(r'product.*item')}),
            ('div', {'data-cy': re.compile(r'book|product')}),
            ('li', {'class': re.compile(r'book')}),
            ('div', {'class': re.compile(r'grid.*item')}),
        ]
        
        for tag, attrs in selectors:
            book_containers = soup.find_all(tag, attrs)
            if book_containers:
                logger.info(f"Found {len(book_containers)} books using {tag} with {attrs}")
                break
        
        return book_containers
    
    def extract_book_details_bd(self, container, full_soup) -> Optional[Dict]:
        """Extract book details from BookDepository search result container"""
        try:
            # Initialize default values
            title = "Unknown Title",
            author = "Unknown Author",
            publisher = "Unknown Publisher",
            pub_year = "Unknown",
            isbn = "N/A",
            price = "N/A",
            book_url = "N/A",
            format = "N/A",
            
            # Extract title using multiple strategies
            title, book_url = self.extract_title_and_url(container)
            
            # Extract author
            author = self.extract_author(container)
            
            # Extract price
            price = self.extract_price(container)
            
            # Extract format
            format = self.extract_format(container)
            
            # Extract publisher and publication year from container if available
            publisher = self.extract_publisher(container)
            pub_year = self.extract_publication_year(container)
            
            # If we have a book URL, try to get more details from the product page
            if book_url != "N/A" and "http" in book_url:
                detailed_info = self.get_book_details_from_page(book_url)
                if detailed_info:
                    publisher = detailed_info.get('publisher', publisher)
                    pub_year = detailed_info.get('pub_year', pub_year)
                    isbn = detailed_info.get('isbn', isbn)
                    if format == "N/A":
                        format = detailed_info.get('format', format)
                    if rating == "N/A":
                        rating = detailed_info.get('rating', rating)
            
            # Clean up extracted data
            title = self.clean_text(title)
            author = self.clean_text(author)
            publisher = self.clean_text(publisher)
            
            # Skip if we don't have meaningful data
            if title == "Unknown Title" and author == "Unknown Author":
                return None
            
            return {
                "Site": "BookDepository",
                "Title": title,
                "Author": author,
                "Publisher": publisher,
                "Publication_Year": pub_year,
                "ISBN": isbn,
                "Price": price,
                "URL": book_url,
                "Format": format,
            }
            
        except Exception as e:
            logger.error(f"Error extracting BookDepository book details: {str(e)}")
            return None
    
    def extract_title_and_url(self, container):
        """Extract title and URL from container"""
        title = "Unknown Title"
        book_url = "N/A"
        
        # BookDepository-specific title selectors
        title_selectors = [
            'h3.title a',
            '.title a',
            'h2 a',
            'h3 a',
            'h4 a',
            '.book-title a',
            'a[title]',
            'a[href*="/book/"]',  # BookDepository book URLs contain /book/
            '[itemprop="name"] a',
            '.item-title a',
        ]
        
        title_elem = None
        for selector in title_selectors:
            title_elem = container.select_one(selector)
            if title_elem:
                break
        
        if not title_elem:
            # Fallback: find any link that looks like a book title
            links = container.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                if ('/book/' in href or text) and len(text) > 5:
                    title_elem = link
                    break
        
        if title_elem:
            title = title_elem.get_text(strip=True)
            href = title_elem.get('href')
            if href:
                book_url = urljoin(self.base_url, href)
        
        return title, book_url
    
    def extract_author(self, container):
        """Extract author from container"""
        author = "Unknown Author"

        # Try to find BookDepository/Amazon-style author row
        # Look for a row with multiple <span class="a-size-base">, possibly with "by" prefix
        author_row = container.select_one('.a-row.a-size-base.a-color-secondary .a-row')
        if author_row:
            spans = author_row.find_all('span', class_='a-size-base')
            # Filter out 'by' and ',' and 'et al.' and join the rest
            author_names = []
            for span in spans:
                text = span.get_text(strip=True)
                if text.lower() == 'by' or text == ',' or text.lower() == 'et al.':
                    continue
                author_names.append(text)
            if author_names:
                author = ', '.join(author_names)
                return author

        # Fallback: Try to find Amazon-style bylineInfo structure
        byline_div = container.find("div", id="bylineInfo")
        if byline_div:
            author_span = byline_div.find("span", class_="author")
            if author_span:
                author_link = author_span.find("a")
                if author_link:
                    author = author_link.get_text(strip=True)
                    if author and author.lower() != 'unknown':
                        return author

        return author
    
    def extract_price(self, container):
        """Extract price from container"""
        price = "N/A"
        
        # BookDepository-specific price selectors
        price_selectors = [
            '.price',
            '[class*="price"]',
            '.cost',
            '[class*="cost"]',
            '[itemprop="price"]',
            '.book-price',
            '.item-price',
        ]
        
        for selector in price_selectors:
            price_elem = container.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                # Extract price using regex - handle different currencies
                price_match = re.search(r'[£$€¥]\s*[\d.,]+', price_text)
                if price_match:
                    price = price_match.group()
                    break
                elif price_text and any(char in price_text for char in ['£', '$', '€', '¥']):
                    price = price_text
                    break
        
        return price
    
    def extract_format(self, container):
        """Extract format from container"""
        format = "N/A"
        
        # BookDepository-specific format selectors
        format_selectors = [
            '.format',
            '[class*="format"]',
            '.binding',
            '[class*="binding"]',
            '[itemprop="bookFormat"]',
            '.book-format',
            '.item-format',
        ]
        
        for selector in format_selectors:
            format_elem = container.select_one(selector)
            if format_elem:
                format = format_elem.get_text(strip=True)
                if format:
                    break
        
        return format
    
    def extract_rating(self, container):
        """Extract rating from container"""
        rating = "N/A"
        
        # BookDepository-specific rating selectors
        rating_selectors = [
            '.rating',
            '[class*="rating"]',
            '.stars',
            '[class*="stars"]',
            '[class*="review"]',
            '.book-rating',
        ]
        
        for selector in rating_selectors:
            rating_elem = container.select_one(selector)
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                # Look for star ratings or numeric ratings
                star_match = re.search(r'(\d+\.?\d*)\s*(?:out of|/)\s*5', rating_text)
                if star_match:
                    rating = f"{star_match.group(1)}/5"
                    break
                elif rating_text:
                    rating = rating_text
                    break
        
        return rating
    
    def extract_publisher(self, container):
        """Extract publisher from container"""
        publisher = "Unknown Publisher"
        
        # BookDepository-specific publisher selectors
        publisher_selectors = [
            '[itemprop="publisher"]',
            '.publisher',
            '[class*="publisher"]',
            '.book-publisher',
            '.imprint',
        ]
        
        for selector in publisher_selectors:
            publisher_elem = container.select_one(selector)
            if publisher_elem:
                publisher = publisher_elem.get_text(strip=True)
                if publisher:
                    break
        
        return publisher
    
    def extract_publication_year(self, container):
        """Extract publication year from container"""
        pub_year = "Unknown"
        
        # BookDepository-specific publication date selectors
        pub_selectors = [
            '[itemprop="datePublished"]',
            '.publication-date',
            '.pub-date',
            '[class*="date"]',
            '.published',
        ]
        
        for selector in pub_selectors:
            pub_elem = container.select_one(selector)
            if pub_elem:
                pub_text = pub_elem.get_text(strip=True)
                year_match = re.search(r'\b(19|20)\d{2}\b', pub_text)
                if year_match:
                    pub_year = year_match.group()
                    break
        
        return pub_year
    
    def get_book_details_from_page(self, book_url: str) -> Optional[Dict]:
        """Get additional book details from individual product page"""
        try:
            response = self.make_request_with_retry(book_url, timeout=15)
            if not response:
                return None

            soup = BeautifulSoup(response.content, 'html.parser')
            details = {}

            # Try to extract details from Amazon-style detail bullets
            detail_div = soup.find('div', id='detailBullets_feature_div')
            if detail_div:
                items = detail_div.select('ul.a-unordered-list > li')
                for item in items:
                    label_elem = item.find('span', class_='a-text-bold')
                    value_elem = label_elem.find_next_sibling('span') if label_elem else None
                    if not label_elem or not value_elem:
                        continue
                    label = label_elem.get_text(separator=' ', strip=True).replace(':', '').strip().lower()
                    value = value_elem.get_text(separator=' ', strip=True)
                    if 'publisher' in label:
                        details['publisher'] = value
                    elif 'publication date' in label:
                        # Try to extract year
                        year_match = re.search(r'\b(19|20)\d{2}\b', value)
                        if year_match:
                            details['pub_year'] = year_match.group()
                        else:
                            details['pub_year'] = value
                    elif 'isbn-13' in label:
                        details['isbn'] = value
                    elif 'isbn-10' in label and 'isbn' not in details:
                        details['isbn'] = value
                    elif 'format' in label:
                        details['format'] = value

            # Fallback to BookDepository selectors if not found above
            if 'isbn' not in details:
                isbn_selectors = [
                    '[itemprop="isbn"]',
                    '.isbn',
                    '[class*="isbn"]',
                ]
                for selector in isbn_selectors:
                    isbn_elem = soup.select_one(selector)
                    if isbn_elem:
                        isbn_text = isbn_elem.get_text(strip=True)
                        isbn_match = re.search(r'[\d-]{10,17}', isbn_text)
                        if isbn_match:
                            details['isbn'] = isbn_match.group()
                            break

            if 'publisher' not in details:
                publisher_selectors = [
                    '[itemprop="publisher"]',
                    '.publisher',
                    '[class*="publisher"]',
                ]
                for selector in publisher_selectors:
                    pub_elem = soup.select_one(selector)
                    if pub_elem:
                        details['publisher'] = pub_elem.get_text(strip=True)
                        break

            if 'pub_year' not in details:
                date_selectors = [
                    '[itemprop="datePublished"]',
                    '.publication-date',
                ]
                for selector in date_selectors:
                    date_elem = soup.select_one(selector)
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        year_match = re.search(r'\b(19|20)\d{2}\b', date_text)
                        if year_match:
                            details['pub_year'] = year_match.group()
                            break

            if 'format' not in details:
                format_selectors = [
                    '[itemprop="bookFormat"]',
                    '.format',
                    '[class*="format"]',
                ]
                for selector in format_selectors:
                    format_elem = soup.select_one(selector)
                    if format_elem:
                        details['format'] = format_elem.get_text(strip=True)
                        break

            # Look for rating
            rating_selectors = [
                '.rating',
                '[class*="rating"]',
                '.stars',
                '[class*="stars"]',
            ]
            for selector in rating_selectors:
                rating_elem = soup.select_one(selector)
                if rating_elem:
                    rating_text = rating_elem.get_text(strip=True)
                    star_match = re.search(r'(\d+\.?\d*)\s*(?:out of|/)\s*5', rating_text)
                    if star_match:
                        details['rating'] = f"{star_match.group(1)}/5"
                        break
                    elif rating_text:
                        details['rating'] = rating_text
                        break

            # Look for JSON-LD structured data
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    if script.string:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'Book':
                            if 'publisher' in data and 'publisher' not in details:
                                pub_info = data['publisher']
                                if isinstance(pub_info, dict):
                                    details['publisher'] = pub_info.get('name', '')
                                else:
                                    details['publisher'] = str(pub_info)
                            if 'datePublished' in data and 'pub_year' not in details:
                                year_match = re.search(r'\d{4}', data['datePublished'])
                                if year_match:
                                    details['pub_year'] = year_match.group()
                            if 'isbn' in data and 'isbn' not in details:
                                details['isbn'] = data['isbn']
                            if 'bookFormat' in data and 'format' not in details:
                                details['format'] = data['bookFormat']
                except (json.JSONDecodeError, AttributeError):
                    continue

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
        """Search BookDepository by ISBN"""
        return self.search_bookdepository(isbn, max_results=1)
    
    def search_by_title_author(self, title: str, author: str = "") -> List[Dict]:
        """Search BookDepository by title and author"""
        query = f"{title} {author}".strip()
        return self.search_bookdepository(query)

    def save_to_excel(self, data: List[Dict], filename: str = "bookdepository_books.xlsx") -> None:
        """Save book data to Excel"""
        if not data:
            logger.warning("No data to save")
            return
        
        df = pd.DataFrame(data)
        
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

    def save_to_csv(self, data: List[Dict], filename: str = "bookdepository_books.csv") -> None:
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

    def __del__(self):
        """Cleanup when object is destroyed"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass


# Example usage
if __name__ == "__main__":
    scraper = BookDepositoryBookScraper()
    
    # Example searches
    search_queries = [
        "life of pi",
    ]
    
    all_results = []
    
    for query in search_queries:
        print(f"\nSearching for: {query}")
        results = scraper.search_bookdepository(query, max_results=5)
        all_results.extend(results)
        
        # Add delay between searches
        time.sleep(random.uniform(2, 4))
    
    # Save results
    if all_results:
        scraper.save_to_excel(all_results)
        scraper.save_to_csv(all_results)
    else:
        print("No results found!")
    
    # Clean up
    del scraper