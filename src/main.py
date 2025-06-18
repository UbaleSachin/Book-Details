from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime
import logging
from src.book_sites.open_library import BookScraper
from src.book_sites.barnes_and_noble import BarnesNobleBookScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Updated Flask configuration to match your file structure
app = Flask(__name__, static_folder='static', template_folder='template')
CORS(app)

# Initialize the book scraper
scraper = BookScraper()
barnes_noble_scraper = BarnesNobleBookScraper()

# Store search results temporarily (in production, use a proper database)
search_cache = {}

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/style.css')
def styles():
    """Serve the CSS file"""
    return send_from_directory('src/static', 'style.css')

@app.route('/scripts.js')
def script():
    """Serve the JavaScript file"""
    return send_from_directory('src/static', 'scripts.js')

@app.route('/api/search', methods=['POST'])
def search_books():
    """Handle book search requests from the frontend"""
    try:
        data = request.get_json()
        
        # Extract search parameters
        book_name = data.get('bookName', '').strip()
        isbn = data.get('isbn', '').strip()
        author = data.get('author', '').strip()
        site = data.get('site', 'openlibrary')
        
        # Validate input
        if not any([book_name, isbn, author]):
            return jsonify({
                'success': False,
                'message': 'Please provide at least one search parameter (book name, ISBN, or author)'
            }), 400
        
        # Determine search query priority: ISBN > Book Name > Author
        search_query = isbn if isbn else (book_name if book_name else author)
        search_type = 'isbn' if isbn else ('title' if book_name else 'author')
        
        logger.info(f"Searching for: {search_query} (type: {search_type}) on {site}")
        
        # Perform search based on selected site
        results = []
        
        if site in ['openlibrary', 'library']:
            results = scraper.search_open_library(search_query, max_results=1)
        elif site == 'amazon':
            # Placeholder for Amazon search (would need Amazon API integration)
            results = search_amazon_placeholder(search_query, book_name, author, isbn)
        elif site == 'goodreads':
            # Placeholder for Goodreads search (would need Goodreads API integration)
            results = search_goodreads_placeholder(search_query, book_name, author, isbn)
        elif site == 'bookdepository':
            # Placeholder for Book Depository search
            results = search_bookdepository_placeholder(search_query, book_name, author, isbn)
        elif site == 'barnesandnoble':
            # Placeholder for Barnes & Noble search (would need Barnes & Noble API integration)
            results = barnes_noble_scraper.search_barnes_noble(search_query, max_results=1)
        else:
            # Default to Open Library
            results = scraper.search_open_library(search_query, max_results=10)
        
        # Cache results with timestamp
        cache_key = f"{search_query}_{site}_{datetime.now().strftime('%Y%m%d_%H')}"
        search_cache[cache_key] = {
            'results': results,
            'timestamp': datetime.now().isoformat(),
            'query': search_query,
            'site': site
        }
        
        # Format results for frontend
        formatted_results = format_results_for_frontend(results, site)
        
        # Save results to Excel if requested
        if results and data.get('saveToExcel', False):
            try:
                filename = scraper.save_to_excel(results)
                logger.info(f"Results saved to {filename}")
            except Exception as e:
                logger.error(f"Error saving to Excel: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': f'Found {len(results)} books',
            'results': formatted_results,
            'query': search_query,
            'site': site,
            'total_count': len(results)
        })
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Search failed: {str(e)}'
        }), 500

def format_results_for_frontend(results, site):
    """Format search results for frontend consumption"""
    formatted = []
    
    for book in results:
        # Handle different result formats from different sources
        formatted_book = {
            'id': book.get('ID', f"{book.get('Title', 'Unknown')}_{book.get('Author', 'Unknown')}"),
            'title': book.get('Title', 'Unknown Title'),
            'author': book.get('Author', 'Unknown Author'),
            'isbn': book.get('ISBN', 'N/A'),
            'publisher': book.get('Publisher', 'Unknown Publisher'),
            'publish_date': book.get('Publication_Year', 'Unknown'),
            'pages': book.get('Pages', 'N/A'),
            'language': book.get('Language', 'Unknown'),
            'subjects': book.get('Subjects', []),
            'cover_url': book.get('Cover URL', ''),
            'openlibrary_url': book.get('OpenLibrary URL', ''),
            'site': site,
            'price': book.get('Price', ''),  
            'availability': 'Available',  
            'rating': generate_mock_rating(),
            'format': book.get('Format', '')
        }
        formatted.append(formatted_book)
    
    return formatted

def generate_mock_price():
    """Generate mock price for demonstration"""
    import random
    return f"${random.randint(10, 50)}.{random.randint(10, 99)}"

def generate_mock_rating():
    """Generate mock rating for demonstration"""
    import random
    return round(random.uniform(3.5, 5.0), 1)

def search_amazon_placeholder(query, book_name, author, isbn):
    """Placeholder for Amazon search - to be implemented with actual Amazon API"""
    return [{
        'Title': f'{book_name or query} (Amazon)',
        'Author': author or 'Various Authors',
        'ISBN': isbn or 'N/A',
        'Publisher': 'Amazon Publishing',
        'Publish Date': '2024',
        'Pages': '250',
        'Language': 'English',
        'Subjects': ['Fiction', 'Popular'],
        'Cover URL': '',
        'OpenLibrary URL': 'https://amazon.com/placeholder'
    }]

def search_goodreads_placeholder(query, book_name, author, isbn):
    """Placeholder for Goodreads search - to be implemented with actual Goodreads API"""
    return [{
        'Title': f'{book_name or query} (Goodreads)',
        'Author': author or 'Popular Author',
        'ISBN': isbn or 'N/A',
        'Publisher': 'Goodreads Selection',
        'Publish Date': '2024',
        'Pages': '300',
        'Language': 'English',
        'Subjects': ['Highly Rated', 'Popular'],
        'Cover URL': '',
        'OpenLibrary URL': 'https://goodreads.com/placeholder'
    }]

def search_bookdepository_placeholder(query, book_name, author, isbn):
    """Placeholder for Book Depository search - to be implemented with actual API"""
    return [{
        'Title': f'{book_name or query} (Book Depository)',
        'Author': author or 'International Author',
        'ISBN': isbn or 'N/A',
        'Publisher': 'International Publisher',
        'Publish Date': '2024',
        'Pages': '280',
        'Language': 'English',
        'Subjects': ['International', 'Popular'],
        'Cover URL': '',
        'OpenLibrary URL': 'https://bookdepository.com/placeholder'
    }]

@app.route('/api/book/<book_id>')
def get_book_details(book_id):
    """Get detailed information about a specific book"""
    try:
        # In a real application, you would fetch detailed book information
        # For now, return mock detailed data
        book_details = {
            'id': book_id,
            'title': 'Sample Book Title',
            'author': 'Sample Author',
            'description': 'This is a sample book description that would contain more detailed information about the book content, plot, and other relevant details.',
            'isbn': '9781234567890',
            'publisher': 'Sample Publisher',
            'publish_date': '2024',
            'pages': 350,
            'language': 'English',
            'rating': 4.5,
            'reviews_count': 1250,
            'price': '$19.99',
            'availability': 'In Stock',
            'cover_url': '',
            'purchase_links': {
                'amazon': 'https://amazon.com/book',
                'goodreads': 'https://goodreads.com/book',
                'library': 'https://library.com/book'
            }
        }
        
        return jsonify({
            'success': True,
            'book': book_details
        })
        
    except Exception as e:
        logger.error(f"Error fetching book details: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to fetch book details: {str(e)}'
        }), 500

@app.route('/api/history')
def get_search_history():
    """Get recent search history"""
    try:
        # Return recent searches from cache (sorted by timestamp)
        history = []
        for key, data in search_cache.items():
            history.append({
                'query': data['query'],
                'site': data['site'],
                'timestamp': data['timestamp'],
                'result_count': len(data['results'])
            })
        
        # Sort by timestamp (most recent first)
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            'success': True,
            'history': history[:20]  # Return last 20 searches
        })
        
    except Exception as e:
        logger.error(f"Error fetching search history: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to fetch search history: {str(e)}'
        }), 500

@app.route('/api/export', methods=['POST'])
def export_results():
    """Export search results to Excel"""
    try:
        data = request.get_json()
        results = data.get('results', [])
        
        if not results:
            return jsonify({
                'success': False,
                'message': 'No results to export'
            }), 400
        
        # Convert frontend format back to scraper format
        scraper_format_results = []
        for result in results:
            scraper_format_results.append({
                'Title': result.get('title'),
                'Author': result.get('author'),
                'ISBN': result.get('isbn'),
                'Publisher': result.get('publisher'),
                'Publish Date': result.get('publish_date'),
                'Pages': result.get('pages'),
                'Language': result.get('language'),
                'Subjects': result.get('subjects'),
                'Cover URL': result.get('cover_url'),
                'OpenLibrary URL': result.get('openlibrary_url')
            })
        
        filename = scraper.save_to_excel(scraper_format_results)
        
        return jsonify({
            'success': True,
            'message': f'Results exported to {filename}',
            'filename': filename
        })
        
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Export failed: {str(e)}'
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'message': 'Internal server error'
    }), 500

def main():
    """Main function to run the Flask web application"""
    logger.info("Starting Book Search Web Application...")
    
    # Check if the scraper is working
    try:
        test_results = scraper.search_open_library("test", max_results=1)
        logger.info("Book scraper initialized successfully")
    except Exception as e:
        logger.warning(f"Book scraper initialization issue: {str(e)}")
    
    # Run the Flask app
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting server on port {port}")
    logger.info("Access the application at: http://localhost:5000")
    
    app.run(host='127.0.0.1', port=port, debug=debug)

if __name__ == "__main__":
    main()