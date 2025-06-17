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
        # Rotate user agents to avoid detection
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
            "Cache-Control": "max-age=0"
        })
        
    def make_request_with_retry(self, url: str, max_retries: int = 3, timeout: int = 30) -> Optional[requests.Response]:
        """Make HTTP request with retry logic and better error handling"""
        for attempt in range(max_retries):
            try:
                # Update headers with new user agent for each retry
                self.update_headers()
                
                # Add random delay to seem more human-like
                if attempt > 0:
                    delay = random.uniform(2, 5)
                    logger.info(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s delay")
                    time.sleep(delay)
                
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    logger.error(f"All {max_retries} attempts timed out for URL: {url}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed on attempt {attempt + 1}/{max_retries}: {str(e)}")
                if attempt == max_retries - 1:
                    logger.error(f"All {max_retries} attempts failed for URL: {url}")
        
        return None
        """Clean and normalize text content"""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text.strip())
    
    def extract_price(self, price_text: str) -> Optional[float]:
        """Extract numeric price from price text"""
        if not price_text:
            return None
        # Remove currency symbols and extract number
        price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
        return float(price_match.group()) if price_match else None
    
    def search_barnes_and_noble(self, book_query: str, max_results: int = 5) -> List[Dict]:
        """Search Barnes & Noble for books with improved error handling and data extraction"""
        try:
            # URL encode the query properly
            encoded_query = quote_plus(book_query)
            search_url = f"https://www.barnesandnoble.com/s/{encoded_query}"
            
            logger.info(f"Searching Barnes & Noble for: {book_query}")
            logger.info(f"URL: {search_url}")
            
            response = self.make_request_with_retry(search_url)
            if not response:
                logger.error("Failed to get response from Barnes & Noble")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Try multiple selectors for book containers (websites change their structure)
            book_selectors = [
                '.product-shelf-tile',
                '.product-info-view',
                '.product-item',
                '[data-testid="product-shelf-tile"]',
                '.pItem'
            ]
            
            books = []
            for selector in book_selectors:
                books = soup.select(selector)
                if books:
                    logger.info(f"Found {len(books)} books using selector: {selector}")
                    break
            
            if not books:
                logger.warning("No books found with any selector")
                return results
            
            for i, book in enumerate(books[:max_results]):
                try:
                    book_data = self.extract_book_details_bn(book)
                    if book_data:
                        results.append(book_data)
                        logger.info(f"Extracted book {i+1}: {book_data.get('Title', 'Unknown')}")
                except Exception as e:
                    logger.error(f"Error extracting book {i+1}: {str(e)}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Unexpected error in Barnes & Noble search: {str(e)}")
            return []
    
    def extract_book_details_bn(self, book_element) -> Optional[Dict]:
        """Extract book details from Barnes & Noble book element with debugging"""
        try:
            # Debug: Print the HTML structure of the first book element
            logger.info(f"Book element HTML preview: {str(book_element)[:200]}...")
            
            # Try multiple selectors for title with more specific patterns
            title_selectors = [
                'h3 a[href*="/w/"]',  # More specific selector for B&N
                '.product-shelf-title a',
                '.product-info-title a',
                '.product-title a',
                'h3 a',
                '.pTitle a',
                'a[href*="/w/"]',  # B&N product URLs contain /w/
                '.product-shelf-tile h3 a'
            ]
            
            title_element = None
            title_selector_used = None
            for selector in title_selectors:
                title_element = book_element.select_one(selector)
                if title_element:
                    title_selector_used = selector
                    logger.info(f"Found title using selector: {selector}")
                    break
            
            if not title_element:
                logger.warning("No title element found. Available links:")
                all_links = book_element.select('a')
                for i, link in enumerate(all_links[:3]):  # Show first 3 links
                    logger.info(f"Link {i+1}: {link.get('href', 'No href')} - Text: {link.get_text()[:50]}")
                return None
            
            title = self.clean_text(title_element.get_text())
            book_url = title_element.get('href', '')
            if book_url and not book_url.startswith('http'):
                book_url = urljoin('https://www.barnesandnoble.com', book_url)
            
            logger.info(f"Extracted title: {title}")
            
            # Try multiple selectors for price with B&N specific patterns
            price_selectors = [
                '.price-display .current-price',
                '.current-price',
                '.current',
                '.price-current',
                '.pPrice .current',
                '[data-testid="current-price"]',
                '.price .current',
                'span[class*="price"]',
                'div[class*="price"] span'
            ]
            
            price_element = None
            price_selector_used = None
            for selector in price_selectors:
                price_element = book_element.select_one(selector)
                if price_element:
                    price_selector_used = selector
                    logger.info(f"Found price using selector: {selector}")
                    break
            
            if not price_element:
                logger.warning("No price element found. Available price-related elements:")
                price_candidates = book_element.select('[class*="price"], [class*="Price"]')
                for i, elem in enumerate(price_candidates[:3]):
                    logger.info(f"Price candidate {i+1}: {elem.get('class', 'No class')} - Text: {elem.get_text()[:30]}")
            
            price_text = self.clean_text(price_element.get_text()) if price_element else "N/A"
            price_numeric = self.extract_price(price_text)
            
            # Try to extract author with B&N specific patterns
            author_selectors = [
                '.contributors a',
                '.product-shelf-author a',
                '.product-info-author a',
                '.contrib-author a',
                '.pAuthor a',
                'a[href*="/contrib/"]',  # B&N contributor URLs
                '.product-shelf-tile .contributors a'
            ]
            
            author_element = None
            for selector in author_selectors:
                author_element = book_element.select_one(selector)
                if author_element:
                    logger.info(f"Found author using selector: {selector}")
                    break
            
            author = self.clean_text(author_element.get_text()) if author_element else "Unknown Author"
            
            # Try to extract format
            format_selectors = [
                '.format-info',
                '.product-format',
                '.format',
                '.pFormat',
                'span[class*="format"]',
                'div[class*="format"]'
            ]
            
            format_element = None
            for selector in format_selectors:
                format_element = book_element.select_one(selector)
                if format_element:
                    break
            
            book_format = self.clean_text(format_element.get_text()) if format_element else "Unknown Format"
            
            result = {
                "Site": "Barnes & Noble",
                "Title": title,
                "Author": author,
                "Format": book_format,
                "Price_Text": price_text,
                "Price_Numeric": price_numeric,
                "Currency": "USD",
                "URL": book_url,
                "Search_Query": "",
                "Debug_Title_Selector": title_selector_used,
                "Debug_Price_Selector": price_selector_used
            }
            
            logger.info(f"Successfully extracted: {title} by {author} - {price_text}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting book details: {str(e)}")
            return None
    
    def search_open_library(self, book_query: str, max_results: int = 5) -> List[Dict]:
        """Search Open Library API for books - more reliable alternative"""
        try:
            # OpenLibrary API is more reliable and doesn't block requests
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
            
            # Get publication year
            pub_year = book_data.get('first_publish_year', 'Unknown')
            
            # Get ISBN
            isbn_list = book_data.get('isbn', [])
            isbn = isbn_list[0] if isbn_list else 'N/A'
            
            # Get publisher
            publishers = book_data.get('publisher', [])
            publisher = publishers[0] if publishers else 'Unknown Publisher'
            
            # Create Open Library URL
            ol_key = book_data.get('key', '')
            book_url = f"https://openlibrary.org{ol_key}" if ol_key else "N/A"
            
            return {
                "Site": "Open Library",
                "Title": title,
                "Author": author,
                "Publisher": publisher,
                "Publication_Year": pub_year,
                "ISBN": isbn,
                "Format": "Various",
                "Price_Text": "Free (Digital)",
                "Price_Numeric": 0.0,
                "Currency": "USD",
                "URL": book_url,
                "Search_Query": ""
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
                "Format": "Various",
                "Price_Text": "Free (Digital)",
                "Price_Numeric": 0.0,
                "Currency": "USD",
                "URL": book_url,
                "Search_Query": ""
            }
            
        except Exception as e:
            logger.error(f"Error extracting Open Library ISBN book details: {str(e)}")
            return None
        """Search multiple book sites (extensible for future sites)"""
        all_results = []
        
        # Barnes & Noble
        bn_results = self.search_barnes_and_noble(book_query, max_results)
        for result in bn_results:
            result["Search_Query"] = book_query
        all_results.extend(bn_results)
        
        # Add small delay to be respectful
        time.sleep(1)
        
        # Future: Add other sites like Amazon, Book Depository, etc.
        # amazon_results = self.search_amazon(book_query, max_results)
        # all_results.extend(amazon_results)
        
        return all_results
    
    def save_to_excel(self, data: List[Dict], filename: str = "book_prices.xlsx") -> None:
        """Save book data to Excel with enhanced formatting"""
        if not data:
            logger.warning("No data to save")
            return
        
        df = pd.DataFrame(data)
        df["Date_Scraped"] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Reorder columns for better readability
        column_order = [
            "Title", "Author", "Publisher", "Publication_Year", "ISBN", "Format", 
            "Price_Text", "Price_Numeric", "Currency", "Site", "URL", "Search_Query", "Date_Scraped"
        ]
        
        # Only include columns that exist in the DataFrame
        existing_columns = [col for col in column_order if col in df.columns]
        df = df[existing_columns]
        
        try:
            df.to_excel(filename, index=False)
            logger.info(f"Data saved to {filename}")
            logger.info(f"Total books found: {len(df)}")
        except Exception as e:
            logger.error(f"Error saving to Excel: {str(e)}")

def main():
    """Main function to demonstrate usage"""
    scraper = BookScraper()
    
    # Test with a single query first
    test_query = "9780156027328"  # Life of Pi ISBN
    
    print(f"\n{'='*50}")
    print(f"Testing with: {test_query}")
    print(f"{'='*50}")
    
    # Test Open Library first (should work reliably)
    print("\n--- Testing Open Library ---")
    ol_results = scraper.search_open_library(test_query, max_results=2)
    if ol_results:
        df_ol = pd.DataFrame(ol_results)
        print("Open Library Results:")
        print(df_ol[['Title', 'Author', 'Publisher']].to_string(index=False))
    else:
        print("No Open Library results found")
    
    # Test Barnes & Noble with debugging
    print("\n--- Testing Barnes & Noble (with debugging) ---")
    bn_results = scraper.search_barnes_and_noble(test_query, max_results=2)
    if bn_results:
        df_bn = pd.DataFrame(bn_results)
        print("Barnes & Noble Results:")
        print(df_bn[['Title', 'Author', 'Price_Text']].to_string(index=False))
    else:
        print("No Barnes & Noble results found")
    
    # Combine results
    all_results = ol_results + bn_results
    if all_results:
        scraper.save_to_excel(all_results, "test_book_search.xlsx")
        print(f"\nSaved {len(all_results)} results to test_book_search.xlsx")
    
    return all_results

def quick_test():
    """Quick test function for debugging"""
    scraper = BookScraper()
    
    # Test just Open Library API which should work reliably
    queries = ["9780156027328", "Life of Pi", "Harry Potter"]
    
    for query in queries:
        print(f"\nTesting Open Library with: {query}")
        results = scraper.search_open_library(query, max_results=1)
        if results:
            print(f"✓ Found: {results[0]['Title']} by {results[0]['Author']}")
        else:
            print("✗ No results")
    
    return "Test completed"

if __name__ == "__main__":
    # Run quick test first
    print("Running quick Open Library test...")
    quick_test()
    
    print("\n" + "="*60)
    print("Running full test...")
    main()