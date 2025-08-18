/**
 * LightRAG JavaScript Client for Lovable Integration
 * 
 * This client provides easy integration with LightRAG API server
 * for use in web forms and chat interfaces.
 */

class LightRAGClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.conversationId = null;
        this.userId = null;
        this.defaultSystemPrompt = null;
    }

    /**
     * Set conversation ID for context
     */
    setConversationId(id) {
        this.conversationId = id;
        return this;
    }

    /**
     * Set user ID for tracking
     */
    setUserId(id) {
        this.userId = id;
        return this;
    }

    /**
     * Set default system prompt
     */
    setSystemPrompt(prompt) {
        this.defaultSystemPrompt = prompt;
        return this;
    }

    /**
     * Send a chat message
     */
    async chat(message, options = {}) {
        try {
            const response = await fetch(`${this.baseUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message,
                    conversation_id: options.conversation_id || this.conversationId,
                    user_id: options.user_id || this.userId,
                    system_prompt: options.system_prompt || this.defaultSystemPrompt,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Update conversation ID if not set
            if (!this.conversationId && data.conversation_id) {
                this.conversationId = data.conversation_id;
            }

            return data;
        } catch (error) {
            console.error('Chat request failed:', error);
            throw error;
        }
    }

    /**
     * Search documents
     */
    async search(query, limit = 5) {
        try {
            const response = await fetch(
                `${this.baseUrl}/documents/search?query=${encodeURIComponent(query)}&limit=${limit}`
            );

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Search request failed:', error);
            throw error;
        }
    }

    /**
     * Insert a document
     */
    async insertDocument(content, documentId = null) {
        try {
            const response = await fetch(`${this.baseUrl}/documents/insert`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content,
                    document_id: documentId,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Document insertion failed:', error);
            throw error;
        }
    }

    /**
     * Get current configuration
     */
    async getConfig() {
        try {
            const response = await fetch(`${this.baseUrl}/config`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Config request failed:', error);
            throw error;
        }
    }

    /**
     * Update configuration
     */
    async updateConfig(config) {
        try {
            const response = await fetch(`${this.baseUrl}/config`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Config update failed:', error);
            throw error;
        }
    }

    /**
     * Check server health
     */
    async healthCheck() {
        try {
            const response = await fetch(`${this.baseUrl}/health`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Health check failed:', error);
            throw error;
        }
    }
}

/**
 * Lovable Integration Helper
 * 
 * Provides specific methods for integrating with Lovable forms
 */
class LovableLightRAGIntegration {
    constructor(apiUrl, options = {}) {
        this.client = new LightRAGClient(apiUrl);
        this.options = {
            autoGenerateConversationId: true,
            showTypingIndicator: true,
            enableStreaming: false,
            ...options
        };
        
        this.setupEventListeners();
    }

    /**
     * Setup event listeners for Lovable forms
     */
    setupEventListeners() {
        // Listen for form submissions
        document.addEventListener('submit', (e) => {
            if (e.target.classList.contains('lovable-form')) {
                e.preventDefault();
                this.handleFormSubmission(e.target);
            }
        });

        // Listen for chat input
        document.addEventListener('keypress', (e) => {
            if (e.target.classList.contains('lovable-chat-input') && e.key === 'Enter') {
                e.preventDefault();
                this.handleChatInput(e.target);
            }
        });
    }

    /**
     * Handle form submission
     */
    async handleFormSubmission(form) {
        const submitButton = form.querySelector('button[type="submit"]');
        const originalText = submitButton.textContent;
        
        try {
            // Disable submit button
            submitButton.disabled = true;
            submitButton.textContent = 'Processing...';

            // Get form data
            const formData = new FormData(form);
            const message = formData.get('message') || formData.get('question') || formData.get('input');
            
            if (!message) {
                throw new Error('No message found in form');
            }

            // Generate conversation ID if needed
            if (this.options.autoGenerateConversationId && !this.client.conversationId) {
                this.client.setConversationId(`conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
            }

            // Send chat request
            const response = await this.client.chat(message);

            // Display response
            this.displayResponse(response, form);

        } catch (error) {
            console.error('Form submission failed:', error);
            this.displayError(error.message, form);
        } finally {
            // Re-enable submit button
            submitButton.disabled = false;
            submitButton.textContent = originalText;
        }
    }

    /**
     * Handle chat input
     */
    async handleChatInput(input) {
        const message = input.value.trim();
        if (!message) return;

        // Clear input
        input.value = '';

        // Show user message
        this.displayUserMessage(message);

        try {
            // Show typing indicator
            if (this.options.showTypingIndicator) {
                this.showTypingIndicator();
            }

            // Generate conversation ID if needed
            if (this.options.autoGenerateConversationId && !this.client.conversationId) {
                this.client.setConversationId(`conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
            }

            // Send chat request
            const response = await this.client.chat(message);

            // Hide typing indicator
            if (this.options.showTypingIndicator) {
                this.hideTypingIndicator();
            }

            // Display response
            this.displayChatResponse(response);

        } catch (error) {
            console.error('Chat input failed:', error);
            this.hideTypingIndicator();
            this.displayChatError(error.message);
        }
    }

    /**
     * Display response in form
     */
    displayResponse(response, form) {
        let responseContainer = form.querySelector('.lightrag-response');
        
        if (!responseContainer) {
            responseContainer = document.createElement('div');
            responseContainer.className = 'lightrag-response';
            form.appendChild(responseContainer);
        }

        responseContainer.innerHTML = `
            <div class="response-content">
                <h4>AI Response:</h4>
                <p>${response.response}</p>
                ${response.sources ? `<p><small>Sources: ${response.sources.length} documents</small></p>` : ''}
                <p><small>Conversation ID: ${response.conversation_id}</small></p>
            </div>
        `;
    }

    /**
     * Display error in form
     */
    displayError(message, form) {
        let errorContainer = form.querySelector('.lightrag-error');
        
        if (!errorContainer) {
            errorContainer = document.createElement('div');
            errorContainer.className = 'lightrag-error';
            form.appendChild(errorContainer);
        }

        errorContainer.innerHTML = `
            <div class="error-content" style="color: red;">
                <h4>Error:</h4>
                <p>${message}</p>
            </div>
        `;
    }

    /**
     * Display user message in chat
     */
    displayUserMessage(message) {
        const chatContainer = this.getChatContainer();
        const messageDiv = document.createElement('div');
        messageDiv.className = 'user-message';
        messageDiv.innerHTML = `<p><strong>You:</strong> ${message}</p>`;
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    /**
     * Display AI response in chat
     */
    displayChatResponse(response) {
        const chatContainer = this.getChatContainer();
        const messageDiv = document.createElement('div');
        messageDiv.className = 'ai-message';
        messageDiv.innerHTML = `
            <p><strong>AI:</strong> ${response.response}</p>
            ${response.sources ? `<p><small>Sources: ${response.sources.length} documents</small></p>` : ''}
        `;
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    /**
     * Display chat error
     */
    displayChatError(message) {
        const chatContainer = this.getChatContainer();
        const messageDiv = document.createElement('div');
        messageDiv.className = 'error-message';
        messageDiv.innerHTML = `<p style="color: red;"><strong>Error:</strong> ${message}</p>`;
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    /**
     * Show typing indicator
     */
    showTypingIndicator() {
        const chatContainer = this.getChatContainer();
        let indicator = chatContainer.querySelector('.typing-indicator');
        
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = 'typing-indicator';
            indicator.innerHTML = '<p><em>AI is typing...</em></p>';
            chatContainer.appendChild(indicator);
        }
        
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    /**
     * Hide typing indicator
     */
    hideTypingIndicator() {
        const chatContainer = this.getChatContainer();
        const indicator = chatContainer.querySelector('.typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    /**
     * Get or create chat container
     */
    getChatContainer() {
        let container = document.querySelector('.lightrag-chat-container');
        
        if (!container) {
            container = document.createElement('div');
            container.className = 'lightrag-chat-container';
            container.style.cssText = `
                max-height: 400px;
                overflow-y: auto;
                border: 1px solid #ccc;
                padding: 10px;
                margin: 10px 0;
            `;
            
            // Insert after the first form or chat input
            const form = document.querySelector('.lovable-form, .lovable-chat-input');
            if (form) {
                form.parentNode.insertBefore(container, form.nextSibling);
            } else {
                document.body.appendChild(container);
            }
        }
        
        return container;
    }
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { LightRAGClient, LovableLightRAGIntegration };
}

// Make available globally
if (typeof window !== 'undefined') {
    window.LightRAGClient = LightRAGClient;
    window.LovableLightRAGIntegration = LovableLightRAGIntegration;
} 