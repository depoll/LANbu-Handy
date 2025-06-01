/**
 * LANbu Handy PWA - Main Application JavaScript
 * 
 * Phase 0: Basic PWA structure and initialization
 */

class LANbuHandyApp {
    constructor() {
        this.apiBaseUrl = '/api';
        this.init();
    }

    /**
     * Initialize the application
     */
    init() {
        console.log('LANbu Handy PWA initializing...');
        
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.onDOMReady());
        } else {
            this.onDOMReady();
        }
    }

    /**
     * Called when DOM is ready
     */
    onDOMReady() {
        console.log('LANbu Handy PWA ready');
        
        // Register service worker for PWA functionality (future implementation)
        this.registerServiceWorker();
        
        // Add any initial event listeners here
        this.setupEventListeners();
        
        // Show that the app is loaded
        this.showAppStatus('ready');
    }

    /**
     * Register service worker for PWA functionality
     * (Placeholder for future implementation)
     */
    async registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                // Service worker registration will be implemented in future phases
                console.log('Service worker support detected');
            } catch (error) {
                console.warn('Service worker registration failed:', error);
            }
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Add click handler for feature cards to provide feedback
        const featureCards = document.querySelectorAll('.feature-card');
        featureCards.forEach(card => {
            card.addEventListener('click', (e) => {
                console.log('Feature card clicked:', card.querySelector('h3').textContent);
            });
        });
    }

    /**
     * Show application status
     * @param {string} status - The status to show
     */
    showAppStatus(status) {
        console.log(`LANbu Handy status: ${status}`);
        
        // Add visual indication that the app is ready
        if (status === 'ready') {
            document.body.classList.add('app-ready');
        }
    }

    /**
     * Test backend connectivity (for future use)
     */
    async testBackendConnection() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/health`);
            const data = await response.json();
            console.log('Backend health check:', data);
            return data;
        } catch (error) {
            console.error('Backend connection failed:', error);
            return null;
        }
    }
}

// Initialize the app when script loads
const app = new LANbuHandyApp();

// Make app available globally for debugging
window.LANbuHandyApp = app;