class TravelChatApp {
    constructor() {
        this.baseURL = window.location.origin;
        this.isTyping = false;
        this.init();
    }

    init() {
        this.initializeEventListeners();
        this.checkServerHealth();
        this.focusInput();
    }

    initializeEventListeners() {
        // Send button click
        const sendButton = document.getElementById('sendButton');
        if (sendButton) {
            sendButton.addEventListener('click', () => this.sendMessage());
        }

        // Enter key in input
        const chatInput = document.getElementById('chatInput');
        if (chatInput) {
            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            // Update send button state based on input
            chatInput.addEventListener('input', () => {
                this.updateSendButtonState();
            });
        }

        // Suggestion buttons
        const suggestionBtns = document.querySelectorAll('.suggestion-btn');
        suggestionBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const suggestion = btn.getAttribute('data-suggestion');
                if (suggestion) {
                    chatInput.value = suggestion;
                    this.sendMessage();
                }
            });
        });

        console.log('✅ Event listeners initialized');
    }

    updateSendButtonState() {
        const chatInput = document.getElementById('chatInput');
        const sendButton = document.getElementById('sendButton');
        const hasText = chatInput.value.trim().length > 0;
        
        if (hasText && !this.isTyping) {
            sendButton.disabled = false;
            sendButton.classList.remove('opacity-50', 'cursor-not-allowed');
        } else {
            sendButton.disabled = true;
            sendButton.classList.add('opacity-50', 'cursor-not-allowed');
        }
    }

    async checkServerHealth() {
        try {
            const response = await fetch(`${this.baseURL}/health`);
            const health = await response.json();
            
            this.updateStatus(health.status, health.message);
            
            if (health.status === 'warning') {
                this.addSystemMessage('⚠️ Some features may not work properly. Please check your API keys.');
            } else if (health.status === 'healthy') {
                console.log('✅ Server is healthy');
            }
        } catch (error) {
            console.error('❌ Health check failed:', error);
            this.updateStatus('error', 'Server connection failed');
            this.addSystemMessage('❌ Unable to connect to server. Please check if the backend is running.');
        }
    }

    async sendMessage() {
        const chatInput = document.getElementById('chatInput');
        const message = chatInput.value.trim();

        if (!message || this.isTyping) {
            return;
        }

        try {
            console.log('🚀 Sending message:', message);
            console.log('📡 BaseURL:', this.baseURL);
            console.log('🔗 Full URL:', `${this.baseURL}/chat`);
            
            // Add user message to chat
            this.addMessage(message, 'user');
            chatInput.value = '';
            this.updateSendButtonState();
            this.focusInput();

            // Show typing indicator
            this.showTypingIndicator(true);
            this.isTyping = true;
            this.updateSendButtonState();

            // Send message to backend
            const response = await fetch(`${this.baseURL}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message })
            });

            console.log('📬 Response status:', response.status);
            console.log('📬 Response headers:', response.headers);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            console.log('✅ Response received:', result);
            
            // Add bot response to chat with enhanced formatting
            this.addEnhancedMessage(result.response, 'bot');

        } catch (error) {
            console.error('❌ Error sending message:', error);
            this.addMessage(`Sorry, I encountered an error: ${error.message}`, 'bot', true);
        } finally {
            this.showTypingIndicator(false);
            this.isTyping = false;
            this.updateSendButtonState();
        }
    }

    // Enhanced message handler that displays HTML responses directly
    async addEnhancedMessage(message, type, isError = false) {
        // For itinerary responses (containing HTML), display directly
        if (message.includes('<div class="itinerary-container"')) {
            this.addHtmlMessage(message, type);
        } else {
            // For regular messages, use standard display
            this.addMessage(message, type, isError);
        }
    }

    // Add HTML message directly
    addHtmlMessage(htmlContent, type) {
        const chatMessages = document.getElementById('chatMessages');
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flex items-start space-x-3 animate-slide-up';
        
        // Add avatar
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'flex-shrink-0 w-10 h-10 bg-gradient-to-r from-primary to-secondary rounded-full flex items-center justify-center text-white text-lg shadow-md';
        avatarDiv.textContent = '🗺️';
        
        // Add content
        const contentDiv = document.createElement('div');
        contentDiv.className = 'flex-1 max-w-5xl';
        
        const textDiv = document.createElement('div');
        textDiv.className = 'bg-transparent rounded-2xl rounded-tl-md p-0';
        textDiv.innerHTML = htmlContent;
        
        contentDiv.appendChild(textDiv);
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom with smooth animation
        this.scrollToBottom();
    }

    addMessage(message, type, isError = false) {
        const chatMessages = document.getElementById('chatMessages');
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `flex items-start space-x-3 animate-slide-up ${type === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`;
        
        // Add avatar
        const avatarDiv = document.createElement('div');
        if (type === 'user') {
            avatarDiv.className = 'flex-shrink-0 w-10 h-10 bg-gradient-to-r from-accent to-green-600 rounded-full flex items-center justify-center text-white text-lg shadow-md';
            avatarDiv.textContent = '👤';
        } else {
            avatarDiv.className = 'flex-shrink-0 w-10 h-10 bg-gradient-to-r from-primary to-secondary rounded-full flex items-center justify-center text-white text-lg shadow-md';
            avatarDiv.textContent = '🤖';
        }
        
        // Add content
        const contentDiv = document.createElement('div');
        contentDiv.className = 'flex-1 max-w-3xl';
        
        const textDiv = document.createElement('div');
        
        if (type === 'user') {
            textDiv.className = 'bg-gradient-to-r from-primary to-secondary text-white rounded-2xl rounded-tr-md shadow-sm p-4';
        } else {
            textDiv.className = 'bg-white rounded-2xl rounded-tl-md shadow-sm border border-gray-100 p-4';
        }
        
        if (isError) {
            textDiv.className = 'bg-red-50 border border-red-200 text-red-800 rounded-2xl rounded-tl-md shadow-sm p-4';
        }
        
        // Format message with better typography
        textDiv.innerHTML = `<div class="text-gray-800 leading-relaxed">${this.formatMessage(message)}</div>`;
        if (type === 'user') {
            textDiv.innerHTML = `<div class="text-white leading-relaxed">${this.formatMessage(message)}</div>`;
        }
        
        contentDiv.appendChild(textDiv);
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom with smooth animation
        this.scrollToBottom();
    }

    addSystemMessage(message) {
        const chatMessages = document.getElementById('chatMessages');
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flex items-start space-x-3 animate-slide-up';
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'flex-shrink-0 w-10 h-10 bg-gradient-to-r from-yellow-400 to-orange-500 rounded-full flex items-center justify-center text-white text-lg shadow-md';
        avatarDiv.textContent = '🔧';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'flex-1 max-w-3xl';
        
        const textDiv = document.createElement('div');
        textDiv.className = 'bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-2xl rounded-tl-md shadow-sm p-4';
        textDiv.innerHTML = `<div class="leading-relaxed">${this.formatMessage(message)}</div>`;
        
        contentDiv.appendChild(textDiv);
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        
        this.scrollToBottom();
    }

    showTypingIndicator(show) {
        const chatMessages = document.getElementById('chatMessages');
        let typingIndicator = document.querySelector('.typing-indicator');
        
        if (show && !typingIndicator) {
            typingIndicator = document.createElement('div');
            typingIndicator.className = 'typing-indicator flex items-start space-x-3 animate-slide-up';
            
            const avatarDiv = document.createElement('div');
            avatarDiv.className = 'flex-shrink-0 w-10 h-10 bg-gradient-to-r from-primary to-secondary rounded-full flex items-center justify-center text-white text-lg shadow-md';
            avatarDiv.textContent = '🤖';
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'flex-1 max-w-3xl';
            
            const textDiv = document.createElement('div');
            textDiv.className = 'bg-gray-100 rounded-2xl rounded-tl-md shadow-sm border border-gray-200 p-4';
            textDiv.innerHTML = '<div class="text-gray-600 italic flex items-center space-x-2"><div class="flex space-x-1"><div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div><div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div><div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div></div><span class="ml-2">Thinking...</span></div>';
            
            contentDiv.appendChild(textDiv);
            typingIndicator.appendChild(avatarDiv);
            typingIndicator.appendChild(contentDiv);
            chatMessages.appendChild(typingIndicator);
            
            this.scrollToBottom();
        } else if (!show && typingIndicator) {
            typingIndicator.remove();
        }
    }

    formatMessage(message) {
        // Convert line breaks to HTML
        return message.replace(/\n/g, '<br>');
    }

    focusInput() {
        const chatInput = document.getElementById('chatInput');
        if (chatInput) {
            setTimeout(() => chatInput.focus(), 100);
        }
    }

    scrollToBottom() {
        const chatMessages = document.getElementById('chatMessages');
        setTimeout(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }, 100);
    }

    updateStatus(status, message) {
        const statusIndicator = document.getElementById('statusIndicator');
        const statusDot = statusIndicator.querySelector('div');
        const statusText = statusIndicator.querySelector('span');
        
        // Reset classes
        statusDot.className = 'w-2 h-2 rounded-full';
        
        switch (status) {
            case 'healthy':
                statusDot.classList.add('bg-green-500', 'animate-pulse-slow');
                statusText.textContent = 'Connected';
                break;
            case 'warning':
                statusDot.classList.add('bg-yellow-500', 'animate-pulse');
                statusText.textContent = 'Limited functionality';
                break;
            case 'error':
                statusDot.classList.add('bg-red-500', 'animate-pulse');
                statusText.textContent = 'Connection failed';
                break;
            default:
                statusDot.classList.add('bg-gray-400');
                statusText.textContent = 'Unknown status';
        }
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 max-w-sm animate-slide-up`;
        
        switch (type) {
            case 'success':
                notification.classList.add('bg-green-500', 'text-white');
                break;
            case 'error':
                notification.classList.add('bg-red-500', 'text-white');
                break;
            case 'warning':
                notification.classList.add('bg-yellow-500', 'text-black');
                break;
            default:
                notification.classList.add('bg-blue-500', 'text-white');
        }
        
        notification.textContent = message;
        document.body.appendChild(notification);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.add('opacity-0', 'transform', 'translate-x-full');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Initializing Travel Chat App...');
    window.travelChatApp = new TravelChatApp();
});

// Handle page visibility changes to reconnect if needed
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        // Page became visible again, could check connection here
        console.log('Page visible - ready for interaction');
    }
}); 