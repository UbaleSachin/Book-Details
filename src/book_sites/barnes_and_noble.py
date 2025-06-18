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

class BarnesNobleBookScraper:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://www.barnesandnoble.com"
        self.search_url = "https://www.barnesandnoble.com/s/"
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

    def search_barnes_noble(self, book_query: str, max_results: int = 5) -> List[Dict]:
        """Search Barnes & Noble for books"""
        try:
            # Encode the search query
            encoded_query = quote_plus(book_query)
            search_url = f"{self.search_url}{encoded_query}"
            
            logger.info(f"Searching Barnes & Noble for: {book_query}")
            logger.info(f"Search URL: {search_url}")
            
            response = self.make_request_with_retry(search_url, timeout=20)
            if not response:
                logger.error("Failed to get search results from Barnes & Noble")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Find book containers - Barnes & Noble uses different selectors
            book_containers = soup.find_all('div', class_=re.compile(r'product-shelf-tile|search-result'))
            
            if not book_containers:
                # Try alternative selectors
                book_containers = soup.find_all('div', {'data-testid': re.compile(r'product|book')})
            
            if not book_containers:
                # Try more general selectors
                book_containers = soup.find_all('div', class_=re.compile(r'product|result|tile'))
            
            logger.info(f"Found {len(book_containers)} book containers")
            
            count = 0
            for container in book_containers[:max_results * 2]:  # Get more to account for filtering
                book_data = self.extract_book_details_bn(container, soup)
                if book_data and count < max_results:
                    results.append(book_data)
                    count += 1
                
                # Add delay between extractions
                time.sleep(random.uniform(1, 2))
            
            logger.info(f"Successfully extracted {len(results)} books from Barnes & Noble")
            return results
            
        except Exception as e:
            logger.error(f"Error searching Barnes & Noble: {str(e)}")
            return []
    
    def extract_book_details_bn(self, container, full_soup) -> Optional[Dict]:
        """Extract book details from Barnes & Noble search result container"""
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
            
            # Extract title
            # Look for the specific div with class 'product-shelf-title'
            title_div = container.find('div', class_=re.compile(r'product-shelf-title'))
            title_elem = None
            if title_div:
                title_elem = title_div.find('a')
            if not title_elem:
                # Fallback to previous logic
                title_elem = container.find('h3') or container.find('a', class_=re.compile(r'title|product-title'))
                if not title_elem:
                    title_elem = container.find('a', {'data-testid': 'product-title'})
            if title_elem:
                title = title_elem.get('title') or title_elem.get_text(strip=True)
                # Get URL from title link
                if title_elem.get('href'):
                    book_url = urljoin(self.base_url, title_elem['href'])
            
            # Extract author
            # Try to find the author in the 'product-shelf-author' div
            author_div = container.find('div', class_=re.compile(r'product-shelf-author'))
            if author_div:
                author_link = author_div.find('a')
                if author_link:
                    author = author_link.get_text(strip=True)
                else:
                    # Fallback: get all text except the 'by' span
                    author = ''.join(
                        t for t in author_div.stripped_strings if t.lower() != 'by'
                    )
            else:
                author_elem = container.find('span', class_=re.compile(r'author|contributor'))
                if not author_elem:
                    author_elem = container.find('a', {'data-testid': 'author-link'})
                if not author_elem:
                    # Look for "by" text
                    by_elem = container.find(text=re.compile(r'by\s+', re.I))
                    if by_elem:
                        author_elem = by_elem.parent
                if author_elem:
                    author = author_elem.get_text(strip=True)
                    author = re.sub(r'^by\s+', '', author, flags=re.I)  # Remove "by" prefix
            
            # Extract price
            price_elem = None
            # Look for price in the new structure
            pricing_div = container.find('div', class_=re.compile(r'product-shelf-pricing'))
            if pricing_div:
                current_div = pricing_div.find('div', class_='current')
                if current_div:
                    # Find the <span> containing the price (usually the second span)
                    spans = current_div.find_all('span')
                    if len(spans) >= 2:
                        price = spans[1].get_text(strip=True)
                    else:
                        # Fallback: look for a span with a $ sign
                        price_span = current_div.find('span', string=re.compile(r'\$\d'))
                        if price_span:
                            price = price_span.get_text(strip=True)
            if price == "N/A":
                # Fallback to previous logic
                price_elem = container.find('span', class_=re.compile(r'price|current-price'))
                if not price_elem:
                    price_elem = container.find('div', {'data-testid': 'price'})
                if price_elem:
                    price = price_elem.get_text(strip=True)
            
            # Extract rating
            rating_elem = container.find('span', class_=re.compile(r'rating|stars'))
            if rating_elem:
                rating = rating_elem.get_text(strip=True)

            # Extract format
            pricing_elem = container.find('div', class_='product-shelf-pricing mt-xs')
            if pricing_elem:
                format_elem = pricing_elem.find('span', class_='format')
                if format_elem:
                    format = format_elem.get_text(strip=True)
                    
            
            # If we have a book URL, try to get more details from the product page
            if book_url != "N/A":
                detailed_info = self.get_book_details_from_page(book_url)
                if detailed_info:
                    publisher = detailed_info.get('publisher', publisher)
                    pub_year = detailed_info.get('pub_year', pub_year)
                    isbn = detailed_info.get('isbn', isbn)
            
            # Clean up extracted data
            title = self.clean_text(title)
            author = self.clean_text(author)
            publisher = self.clean_text(publisher)
            
            # Skip if we don't have meaningful data
            if title == "Unknown Title" and author == "Unknown Author":
                return None
            
            return {
                "Site": "Barnes & Noble",
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
            logger.error(f"Error extracting Barnes & Noble book details: {str(e)}")
            return None
    
    def get_book_details_from_page(self, book_url: str) -> Optional[Dict]:
        """Get additional book details from individual product page"""
        try:
            response = self.make_request_with_retry(book_url, timeout=15)
            if not response:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            details = {}
            
            # Look for publisher information in the details table
            pub_table = soup.find('table', class_='plain centered')
            if pub_table:
                rows = pub_table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td and 'publisher' in th.get_text(strip=True).lower():
                        # Try to get publisher from <span itemprop="publisher"> if present
                        span = td.find('span', attrs={'itemprop': 'publisher'})
                        if span:
                            details['publisher'] = span.get_text(strip=True)
                        else:
                            details['publisher'] = td.get_text(strip=True)
                        break
            
            # Look for publication date in the details table
            if pub_table:
                rows = pub_table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        th_text = th.get_text(strip=True).lower()
                        if 'publication date' in th_text:
                            pub_date = td.get_text(strip=True)
                            # Extract year from date
                            year_match = re.search(r'\d{4}', pub_date)
                            if year_match:
                                details['pub_year'] = year_match.group()
                            break
            
            # Look for ISBN-13 in the details table
            if pub_table:
                rows = pub_table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td and 'isbn-13' in th.get_text(strip=True).lower():
                        isbn_text = td.get_text(strip=True)
                        isbn_match = re.search(r'[\d-]{10,17}', isbn_text)
                        if isbn_match:
                            details['isbn'] = isbn_match.group()
                        break
            
            # Try alternative method - look in product details section
            product_details = soup.find('div', class_=re.compile(r'product-details|book-details'))
            if product_details:
                # Look for structured data
                for dt in product_details.find_all('dt'):
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
        """Search Barnes & Noble by ISBN"""
        return self.search_barnes_noble(isbn, max_results=1)
    
    def search_by_title_author(self, title: str, author: str = "") -> List[Dict]:
        """Search Barnes & Noble by title and author"""
        query = f"{title} {author}".strip()
        return self.search_barnes_noble(query)

    def save_to_excel(self, data: List[Dict], filename: str = "barnes_noble_books.xlsx") -> None:
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
                print(df[['Title', 'Author', 'Price']].head().to_string(index=False))
                
        except Exception as e:
            logger.error(f"Error saving to Excel: {str(e)}")

    def save_to_csv(self, data: List[Dict], filename: str = "barnes_noble_books.csv") -> None:
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
    scraper = BarnesNobleBookScraper()
    
    # Example searches
    search_queries = [
        "Can't Hurt Me",
    ]
    
    all_results = []
    
    for query in search_queries:
        print(f"\nSearching for: {query}")
        results = scraper.search_barnes_noble(query, max_results=1)
        all_results.extend(results)
        
        # Add delay between searches
        time.sleep(random.uniform(2, 4))
    
    # Save results
    if all_results:
        scraper.save_to_excel(all_results)
        scraper.save_to_csv(all_results)
    else:
        print("No results found!")