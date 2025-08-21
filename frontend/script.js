// API base URL - use relative path to work from any host
const API_URL = '/api';

// Global state
let currentSessionId = null;
let currentAbortController = null;  // Track the current request's abort controller

// DOM elements
let chatMessages, chatInput, sendButton, totalCourses, courseTitles, newChatButton, themeToggle;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements after page loads
    chatMessages = document.getElementById('chatMessages');
    chatInput = document.getElementById('chatInput');
    sendButton = document.getElementById('sendButton');
    totalCourses = document.getElementById('totalCourses');
    courseTitles = document.getElementById('courseTitles');
    newChatButton = document.getElementById('newChatButton');
    themeToggle = document.getElementById('themeToggle');
    
    setupEventListeners();
    initializeTheme();
    createNewSession();
    loadCourseStats();
});

// Event Listeners
function setupEventListeners() {
    // Chat functionality
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    
    // New chat button
    if (newChatButton) {
        newChatButton.addEventListener('click', () => {
            clearCurrentSession();
        });
    }
    
    // Suggested questions
    document.querySelectorAll('.suggested-item').forEach(button => {
        button.addEventListener('click', (e) => {
            const question = e.target.getAttribute('data-question');
            chatInput.value = question;
            sendMessage();
        });
    });
    
    // Theme toggle
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
        themeToggle.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleTheme();
            }
        });
    }
}


// Chat Functions
async function sendMessage() {
    const query = chatInput.value.trim();
    if (!query) return;

    // Cancel any existing request
    if (currentAbortController) {
        currentAbortController.abort();
    }

    // Create new abort controller for this request
    currentAbortController = new AbortController();

    // Disable input
    chatInput.value = '';
    chatInput.disabled = true;
    sendButton.disabled = true;

    // Add user message
    addMessage(query, 'user');

    // Add loading message - create a unique container for it
    const loadingMessage = createLoadingMessage();
    chatMessages.appendChild(loadingMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                session_id: currentSessionId
            }),
            signal: currentAbortController.signal  // Pass abort signal to fetch
        });

        if (!response.ok) throw new Error('Query failed');

        const data = await response.json();
        
        // Update session ID if new
        if (!currentSessionId) {
            currentSessionId = data.session_id;
        }

        // Replace loading message with response
        loadingMessage.remove();
        addMessage(data.answer, 'assistant', data.sources, data.source_links);

    } catch (error) {
        // Remove loading message
        if (loadingMessage && loadingMessage.parentNode) {
            loadingMessage.remove();
        }
        
        // Only show error if it's not an abort
        if (error.name !== 'AbortError') {
            addMessage(`Error: ${error.message}`, 'assistant');
        }
    } finally {
        // Clear the abort controller if this was the current request
        if (currentAbortController && currentAbortController.signal.aborted === false) {
            currentAbortController = null;
        }
        
        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
    }
}

function createLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="loading">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    return messageDiv;
}

function addMessage(content, type, sources = null, sourceLinks = null, isWelcome = false) {
    const messageId = Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}${isWelcome ? ' welcome-message' : ''}`;
    messageDiv.id = `message-${messageId}`;
    
    // Convert markdown to HTML for assistant messages
    const displayContent = type === 'assistant' ? marked.parse(content) : escapeHtml(content);
    
    let html = `<div class="message-content">${displayContent}</div>`;
    
    if (sources && sources.length > 0) {
        // Create clickable source links with better visual separation
        const uniqueSources = {};
        sources.forEach((source, index) => {
            if (!uniqueSources[source]) {
                uniqueSources[source] = sourceLinks && sourceLinks[index];
            }
        });
        
        const sourcesHtml = Object.entries(uniqueSources).map(([source, link]) => {
            if (link) {
                // Create clickable link that opens in new tab with icon
                return `<div class="source-item">
                    <a href="${link}" target="_blank" class="source-link">
                        ${source}
                        <svg class="link-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                            <polyline points="15 3 21 3 21 9"></polyline>
                            <line x1="10" y1="14" x2="21" y2="3"></line>
                        </svg>
                    </a>
                </div>`;
            } else {
                // No link available, just show text
                return `<div class="source-item"><span class="source-text">${source}</span></div>`;
            }
        }).join('');
        
        html += `
            <details class="sources-collapsible">
                <summary class="sources-header">📚 Sources (${Object.keys(uniqueSources).length})</summary>
                <div class="sources-content">${sourcesHtml}</div>
            </details>
        `;
    }
    
    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageId;
}

// Helper function to escape HTML for user messages
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Removed removeMessage function - no longer needed since we handle loading differently

async function createNewSession() {
    currentSessionId = null;
    chatMessages.innerHTML = '';
    addMessage('Welcome to the Course Materials Assistant! I can help you with questions about courses, lessons and specific content. What would you like to know?', 'assistant', null, null, true);
}

function clearCurrentSession() {
    // Abort any pending requests first
    if (currentAbortController) {
        currentAbortController.abort();
        currentAbortController = null;
    }
    
    // Store the session ID for background cleanup
    const sessionToClear = currentSessionId;
    
    // Reset the frontend IMMEDIATELY - don't wait for backend
    createNewSession();
    
    // Clear and re-enable the input field immediately
    if (chatInput) {
        chatInput.value = '';
        chatInput.disabled = false;
        chatInput.focus();
    }
    
    // Re-enable send button immediately
    if (sendButton) {
        sendButton.disabled = false;
    }
    
    // Clear the session on the backend in the background (don't await)
    if (sessionToClear) {
        fetch(`${API_URL}/session/clear`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionToClear
            })
        }).catch(error => {
            console.error('Error clearing session on backend:', error);
        });
    }
}

// Load course statistics
async function loadCourseStats() {
    try {
        console.log('Loading course stats...');
        const response = await fetch(`${API_URL}/courses`);
        if (!response.ok) throw new Error('Failed to load course stats');
        
        const data = await response.json();
        console.log('Course data received:', data);
        
        // Update stats in UI
        if (totalCourses) {
            totalCourses.textContent = data.total_courses;
        }
        
        // Update course titles
        if (courseTitles) {
            if (data.course_titles && data.course_titles.length > 0) {
                courseTitles.innerHTML = data.course_titles
                    .map(title => `<div class="course-title-item">${title}</div>`)
                    .join('');
            } else {
                courseTitles.innerHTML = '<span class="no-courses">No courses available</span>';
            }
        }
        
    } catch (error) {
        console.error('Error loading course stats:', error);
        // Set default values on error
        if (totalCourses) {
            totalCourses.textContent = '0';
        }
        if (courseTitles) {
            courseTitles.innerHTML = '<span class="error">Failed to load courses</span>';
        }
    }
}

// Theme Functions
function initializeTheme() {
    // Check for saved theme preference or default to dark
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = savedTheme || (prefersDark ? 'dark' : 'light');
    
    applyTheme(theme);
    
    // Update aria-label based on current theme
    updateThemeToggleLabel();
}

function toggleTheme() {
    const currentTheme = document.body.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    applyTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeToggleLabel();
}

function applyTheme(theme) {
    document.body.setAttribute('data-theme', theme);
}

function updateThemeToggleLabel() {
    if (themeToggle) {
        const currentTheme = document.body.getAttribute('data-theme');
        themeToggle.setAttribute('aria-label', 
            currentTheme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'
        );
    }
}