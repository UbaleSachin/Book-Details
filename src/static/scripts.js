// DOM Elements
const bookForm = document.getElementById('bookForm');
const searchBtn = document.getElementById('searchBtn');
const loadingIndicator = document.getElementById('loadingIndicator');
const results = document.getElementById('results');
const resultsContent = document.getElementById('resultsContent');
const recentSearches = document.getElementById('recentSearches');
const recentList = document.getElementById('recentList');
const clearHistoryBtn = document.getElementById('clearHistory');

// Form inputs
const bookNameInput = document.getElementById('bookName');
const isbnInput = document.getElementById('isbn');
const authorInput = document.getElementById('author');
const siteSelect = document.getElementById('site');

// Search history storage
let searchHistory = JSON.parse(localStorage.getItem('bookSearchHistory')) || [];

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
    displayRecentSearches();
});

function initializeApp() {
    // Add focus effects to inputs
    const inputs = document.querySelectorAll('input, select');
    inputs.forEach(input => {
        input.addEventListener('focus', handleInputFocus);
        input.addEventListener('blur', handleInputBlur);
    });

    // Add typing effects
    const textInputs = document.querySelectorAll('input[type="text"]');
    textInputs.forEach(input => {
        input.addEventListener('input', handleInputChange);
    });
}

function setupEventListeners() {
    // Form submission
    bookForm.addEventListener('submit', handleFormSubmit);
    
    // Clear history button
    clearHistoryBtn.addEventListener('click', clearSearchHistory);
    
    // Auto-suggestions (simulate)
    bookNameInput.addEventListener('input', debounce(showSuggestions, 300));
    authorInput.addEventListener('input', debounce(showSuggestions, 300));
}

function handleInputFocus(e) {
    e.target.parentElement.classList.add('focused');
    animateLabel(e.target);
}

function handleInputBlur(e) {
    e.target.parentElement.classList.remove('focused');
}

function handleInputChange(e) {
    // Add real-time validation feedback
    validateInput(e.target);
}

function animateLabel(input) {
    const label = input.previousElementSibling;
    if (label && label.tagName === 'LABEL') {
        label.style.transform = 'translateY(-2px)';
        label.style.color = '#667eea';
        setTimeout(() => {
            label.style.transform = '';
            label.style.color = '';
        }, 200);
    }
}

function validateInput(input) {
    const value = input.value.trim();
    
    // Remove existing validation classes
    input.classList.remove('valid', 'invalid');
    
    if (value.length > 0) {
        if (input.id === 'isbn' && value.length > 0) {
            // Basic ISBN validation (simplified)
            const isValidISBN = /^[\d\-xX]+$/.test(value) && (value.length >= 10);
            input.classList.add(isValidISBN ? 'valid' : 'invalid');
        } else {
            input.classList.add('valid');
        }
    }
}

async function handleFormSubmit(e) {
    e.preventDefault();
    
    const formData = getFormData();
    
    // Validate form
    if (!validateForm(formData)) {
        showError('Please fill in at least one search field and select a platform.');
        shakeForm();
        return;
    }
    
    // Show loading state
    showLoading();
    
    try {
        // Make API call to backend
        const result = await simulateSearch(formData);
        
        // Add to search history
        addToSearchHistory(formData);
        
        // Show results with actual data from API
        showActualResults(result);
        
    } catch (error) {
        console.error('Search error:', error);
        showError(error.message || 'An error occurred while searching. Please try again.');
    } finally {
        hideLoading();
    }
}

function getFormData() {
    return {
        bookName: bookNameInput.value.trim(),
        isbn: isbnInput.value.trim(),
        author: authorInput.value.trim(),
        site: siteSelect.value,
        timestamp: new Date().toISOString()
    };
}

function validateForm(formData) {
    const hasSearchTerm = formData.bookName || formData.isbn || formData.author;
    const hasPlatform = formData.site;
    return hasSearchTerm && hasPlatform;
}

function showLoading() {
    searchBtn.classList.add('loading');
    searchBtn.disabled = true;
    searchBtn.innerHTML = '<span class="btn-text">Searching...</span><span class="spinner"></span>';
    
    loadingIndicator.classList.remove('hidden');
    results.classList.add('hidden');
}

function hideLoading() {
    searchBtn.classList.remove('loading');
    searchBtn.disabled = false;
    searchBtn.innerHTML = '<span class="btn-text">Search Books</span><span class="btn-icon">🔍</span>';
    
    loadingIndicator.classList.add('hidden');
}

async function simulateSearch(formData) {
    // Make actual API call to the Flask backend
    const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
    });
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const result = await response.json();
    
    if (!result.success) {
        throw new Error(result.message || 'Search failed');
    }
    
    return result;
}

function showActualResults(apiResult) {
    results.classList.remove('hidden');
    results.classList.add('fade-in');
    
    const books = apiResult.results || [];
    
    if (books.length === 0) {
        resultsContent.innerHTML = `
            <div class="no-results">
                <h3>No books found</h3>
                <p>Try adjusting your search terms or selecting a different platform.</p>
            </div>
        `;
        return;
    }
    
    resultsContent.innerHTML = books.map(book => `
        <div class="result-item" onclick="selectResult('${book.id}')">
            <div class="result-header">
                <div class="result-title">${book.title || 'Unknown Title'}</div>
                <div class="result-format">${book.format || 'Unknown Format'}</div>
                <div class="result-price">${book.price || 'N/A'}</div>
            </div>
            <div class="result-author">by ${book.author || 'Unknown Author'}</div>
            <div class="result-details">
                <span class="result-isbn">ISBN: ${book.isbn || 'N/A'}</span>
                <span class="result-publisher">${book.publisher || 'Unknown Publisher'}</span>
                <span class="result-year">${book.publish_date || 'year'}</span>
            </div>
            <div class="result-platform">
                📚 <a href="${book.url || '#'}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation();">${book.site}</a>
            </div>
            <div class="result-subjects">
                ${Array.isArray(book.subjects) ? book.subjects.slice(0, 3).map(subject => 
                    `<span class="subject-tag">${subject}</span>`
                ).join('') : ''}
            </div>
        </div>
    `).join('');
    
    // Add export button
    const exportBtn = document.createElement('button');
    exportBtn.textContent = '📊 Export to Excel';
    exportBtn.className = 'export-btn';
    exportBtn.onclick = () => exportResults(books);
    resultsContent.appendChild(exportBtn);
    
    // Scroll to results
    setTimeout(() => {
        results.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

async function exportResults(books) {
    try {
        // Show loading state on export button
        const exportBtn = document.querySelector('.export-btn');
        const originalText = exportBtn.textContent;
        exportBtn.textContent = '⏳ Exporting...';
        exportBtn.disabled = true;
        
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ results: books })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // Check if the response is a file download
        const contentType = response.headers.get('content-type');
        
        if (contentType && contentType.includes('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')) {
            // Handle file download
            const blob = await response.blob();
            const filename = response.headers.get('content-disposition')?.match(/filename="?(.+)"?/)?.[1] || 'book_search_results.xlsx';
            
            // Create download link and trigger download
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            showSuccess(`Results exported successfully! File downloaded: ${filename}`);
        } else {
            // Handle JSON response (for backward compatibility)
            const result = await response.json();
            
            if (result.success) {
                if (result.downloadUrl) {
                    // If backend provides a download URL
                    const a = document.createElement('a');
                    a.href = result.downloadUrl;
                    a.download = result.filename || 'book_search_results.xlsx';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    
                    showSuccess(`Results exported successfully! File downloaded: ${result.filename}`);
                } else {
                    showSuccess(`Results exported successfully! File: ${result.filename}`);
                }
            } else {
                throw new Error(result.message || 'Export failed');
            }
        }
        
        // Reset button
        exportBtn.textContent = originalText;
        exportBtn.disabled = false;
        
    } catch (error) {
        console.error('Export error:', error);
        showError('Failed to export results. Please try again.');
        
        // Reset button on error
        const exportBtn = document.querySelector('.export-btn');
        if (exportBtn) {
            exportBtn.textContent = '📊 Export to Excel';
            exportBtn.disabled = false;
        }
    }
}

function selectResult(resultId) {
    showSuccess(`Selected book with ID: ${resultId}. Redirecting to purchase page...`);
    // In a real application, you would redirect to the book's page
}

function addToSearchHistory(formData) {
    const searchEntry = {
        id: Date.now(),
        ...formData,
        displayText: generateSearchDisplayText(formData)
    };
    
    // Add to beginning of array and limit to 10 entries
    searchHistory.unshift(searchEntry);
    searchHistory = searchHistory.slice(0, 10);
    
    // Save to localStorage
    localStorage.setItem('bookSearchHistory', JSON.stringify(searchHistory));
    
    // Update display
    displayRecentSearches();
}

function generateSearchDisplayText(formData) {
    const parts = [];
    if (formData.bookName) parts.push(`Title: "${formData.bookName}"`);
    if (formData.author) parts.push(`Author: "${formData.author}"`);
    if (formData.isbn) parts.push(`ISBN: ${formData.isbn}`);
    return parts.join(' • ');
}

function displayRecentSearches() {
    if (searchHistory.length === 0) {
        recentList.innerHTML = '<p class="no-searches">No recent searches yet</p>';
        clearHistoryBtn.classList.add('hidden');
        return;
    }
    
    clearHistoryBtn.classList.remove('hidden');
    
    recentList.innerHTML = searchHistory.map((search, index) => `
        <div class="recent-item" onclick="repeatSearch(${index})">
            <div class="recent-item-title">${search.displayText}</div>
            <div class="recent-item-details">
                Platform: ${search.site} • ${formatDate(search.timestamp)}
            </div>
        </div>
    `).join('');
}

function repeatSearch(index) {
    const search = searchHistory[index];
    
    // Fill form with previous search data
    bookNameInput.value = search.bookName || '';
    isbnInput.value = search.isbn || '';
    authorInput.value = search.author || '';
    siteSelect.value = search.site || '';
    
    // Highlight the form
    const searchCard = document.querySelector('.search-card');
    searchCard.style.transform = 'scale(1.02)';
    searchCard.style.boxShadow = '0 25px 50px rgba(102, 126, 234, 0.3)';
    
    setTimeout(() => {
        searchCard.style.transform = '';
        searchCard.style.boxShadow = '';
    }, 300);
    
    // Scroll to form
    searchCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    
    showSuccess('Previous search loaded! Click "Search Books" to run it again.');
}

function clearSearchHistory() {
    if (confirm('Are you sure you want to clear your search history?')) {
        searchHistory = [];
        localStorage.removeItem('bookSearchHistory');
        displayRecentSearches();
        showSuccess('Search history cleared!');
    }
}

function formatDate(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
}

function showSuggestions(e) {
    // Simulate auto-suggestions (in real app, this would call an API)
    const input = e.target;
    const value = input.value.trim();
    
    if (value.length > 2) {
        // Add subtle visual feedback
        input.style.borderColor = '#28a745';
        setTimeout(() => {
            input.style.borderColor = '';
        }, 1000);
    }
}

function showError(message) {
    showNotification(message, 'error');
}

function showSuccess(message) {
    showNotification(message, 'success');
}

function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Style the notification
    Object.assign(notification.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        padding: '15px 20px',
        borderRadius: '8px',
        color: 'white',
        fontWeight: '600',
        zIndex: '9999',
        maxWidth: '300px',
        boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
        transform: 'translateX(100%)',
        transition: 'transform 0.3s ease'
    });
    
    if (type === 'error') {
        notification.style.background = 'linear-gradient(135deg, #ff6b6b, #ee5a52)';
    } else {
        notification.style.background = 'linear-gradient(135deg, #51cf66, #40c057)';
    }
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 100);
    
    // Remove after delay
    setTimeout(() => {
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

function shakeForm() {
    const searchCard = document.querySelector('.search-card');
    searchCard.classList.add('shake');
    setTimeout(() => {
        searchCard.classList.remove('shake');
    }, 500);
}

// Utility function for debouncing
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Form auto-save (optional feature)
function autoSaveForm() {
    const formData = getFormData();
    localStorage.setItem('bookSearchDraft', JSON.stringify(formData));
}

function loadFormDraft() {
    const draft = JSON.parse(localStorage.getItem('bookSearchDraft') || '{}');
    if (draft.bookName) bookNameInput.value = draft.bookName;
    if (draft.isbn) isbnInput.value = draft.isbn;
    if (draft.author) authorInput.value = draft.author;
    if (draft.site) siteSelect.value = draft.site;
}

// Auto-save form every 2 seconds when user is typing
setInterval(autoSaveForm, 2000);

// Load draft on page load
document.addEventListener('DOMContentLoaded', loadFormDraft);