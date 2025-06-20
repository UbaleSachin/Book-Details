from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime
import logging
from src.book_sites.open_library import BookScraper
from src.book_sites.barnes_and_noble import BarnesNobleBookScraper
from src.book_sites.thriftbooks import ThriftBooksBookScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Updated Flask configuration to match your file structure
app = Flask(__name__, static_folder='static', template_folder='template')
CORS(app)

# Initialize the book scraper
scraper = BookScraper()
barnes_noble_scraper = BarnesNobleBookScraper()
thrift_books_scraper = ThriftBooksBookScraper()

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
        site = data.get('site', '')
        
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
        
        if site == 'openlibrary':
            results = scraper.search_open_library(search_query, max_results=1)
        elif site == 'barnesandnoble':
            results = barnes_noble_scraper.search_barnes_noble(search_query, max_results=1)
        elif site == 'thriftbooks':
            results = thrift_books_scraper.search_thriftbooks(search_query, max_results=1)
        else:
            # Search both Open Library and Barnes & Noble, combine results
            results = []
        
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
            'title': book.get('Title', 'Unknown Title'),
            'author': book.get('Author', 'Unknown Author'),
            'isbn': book.get('ISBN', 'N/A'),
            'publisher': book.get('Publisher', 'Unknown Publisher'),
            'publish_date': book.get('Publication_Year', 'Unknown'),
            'price': book.get('Price', ''),  
            'format': book.get('Format', ''),
            'site': site,
            'url': book.get('URL', ''),

        }
        formatted.append(formatted_book)
    
    return formatted


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
                'Price': result.get('price'),
                'Publisher': result.get('publisher'),
                'Publish Date': result.get('publish_date'),
                'Book URL': result.get('url')

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
        logger.info("Book scraper initialized successfully")
    except Exception as e:
        logger.warning(f"Book scraper initialization issue: {str(e)}")
    
    # Run the Flask app
    port = int(os.environ.get('PORT', 5000))
    #debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting server on port {port}")
    logger.info("Access the application at: http://localhost:5000")
    
    app.run(host='0.0.0.0', port=port, debug=True)

if __name__ == "__main__":
    main()