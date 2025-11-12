/**
 * Alpine Guide Widget - Embeddable Chat Widget
 * Widget JavaScript autonome pour intégration marque blanche
 * 
 * Usage:
 * <script src="https://your-domain.com/alpine-guide-widget.js" 
 *         data-territory="annecy" 
 *         data-api-key="your-api-key"></script>
 */

(function() {
    'use strict';
    
    // Configuration globale
    const WIDGET_VERSION = '1.0.0';
    const DEFAULT_API_BASE = 'https://api.alpine-guide.com';
    
    class AlpineGuideWidget {
        constructor(config = {}) {
            // Configuration par défaut
            this.config = {
                apiBase: config.apiBase || DEFAULT_API_BASE,
                territory: config.territory || 'annecy',
                apiKey: config.apiKey || '',
                language: config.language || 'fr',
                
                // Apparence
                position: config.position || 'bottom-right',
                theme: config.theme || 'light',
                primaryColor: config.primaryColor || '#0066CC',
                
                // Comportement
                autoOpen: config.autoOpen || false,
                autoOpenDelay: config.autoOpenDelay || 5000,
                persistHistory: config.persistHistory !== false,
                
                // Personnalisation
                welcomeMessage: config.welcomeMessage || '',
                placeholder: config.placeholder || 'Tapez votre message...',
                
                // Callbacks
                onReady: config.onReady || null,
                onMessage: config.onMessage || null,
                onError: config.onError || null,
                
                // Debug
                debug: config.debug || false
            };
            
            // État du widget
            this.state = {
                isOpen: false,
                isLoading: false,
                sessionId: this.generateSessionId(),
                conversations: [],
                isTyping: false,
                lastActivity: Date.now()
            };
            
            // Éléments DOM
            this.elements = {};
            
            // Configuration du territoire (chargée dynamiquement)
            this.territoryConfig = null;
            
            this.init();
        }
        
        /**
         * Initialisation du widget
         */
        async init() {
            try {
                this.log('Initialisation du widget Alpine Guide', this.config);
                
                // Charger la configuration du territoire
                await this.loadTerritoryConfig();
                
                // Créer l'interface
                this.createWidget();
                
                // Attacher les événements
                this.attachEvents();
                
                // Charger l'historique
                if (this.config.persistHistory) {
                    this.loadHistory();
                }
                
                // Auto-ouverture si configurée
                if (this.config.autoOpen) {
                    setTimeout(() => this.open(), this.config.autoOpenDelay);
                }
                
                // Callback prêt
                if (this.config.onReady) {
                    this.config.onReady(this);
                }
                
                this.log('Widget initialisé avec succès');
                
            } catch (error) {
                this.error('Erreur lors de l\'initialisation', error);
            }
        }
        
        /**
         * Charge la configuration du territoire
         */
        async loadTerritoryConfig() {
            try {
                const response = await fetch(`${this.config.apiBase}/territories/${this.config.territory}/config`);
                
                if (response.ok) {
                    this.territoryConfig = await response.json();
                    this.log('Configuration territoire chargée', this.territoryConfig);
                    
                    // Appliquer la configuration
                    this.applyTerritoryConfig();
                } else {
                    throw new Error(`Erreur ${response.status}: ${response.statusText}`);
                }
                
            } catch (error) {
                this.error('Impossible de charger la configuration du territoire', error);
                // Configuration par défaut
                this.territoryConfig = {
                    name: this.config.territory,
                    primaryColor: this.config.primaryColor,
                    features: ['chat']
                };
            }
        }
        
        /**
         * Applique la configuration du territoire
         */
        applyTerritoryConfig() {
            if (!this.territoryConfig) return;
            
            // Mettre à jour les couleurs
            if (this.territoryConfig.primaryColor) {
                this.config.primaryColor = this.territoryConfig.primaryColor;
            }
            
            // Messages personnalisés
            if (this.territoryConfig.messages) {
                this.config.welcomeMessage = this.territoryConfig.messages.welcome || this.config.welcomeMessage;
                this.config.placeholder = this.territoryConfig.messages.placeholder || this.config.placeholder;
            }
        }
        
        /**
         * Crée l'interface du widget
         */
        createWidget() {
            // Container principal
            const container = document.createElement('div');
            container.id = 'alpine-guide-widget';
            container.className = `alpine-widget alpine-widget-${this.config.position} alpine-widget-${this.config.theme}`;
            
            // Injecter les styles
            this.injectStyles();
            
            // HTML du widget
            container.innerHTML = `
                <!-- Bouton flottant -->
                <div class="alpine-trigger" id="alpine-trigger">
                    <div class="alpine-trigger-icon">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2C13.1 2 14 2.9 14 4C14 5.1 13.1 6 12 6C10.9 6 10 5.1 10 4C10 2.9 10.9 2 12 2ZM21 9V7L15 1H5C3.89 1 3 1.89 3 3V19C3 20.1 3.9 21 5 21H11V19H5V3H13V9H21Z"/>
                        </svg>
                    </div>
                    <div class="alpine-trigger-notification" id="alpine-notification" style="display: none;">1</div>
                </div>
                
                <!-- Interface de chat -->
                <div class="alpine-chat-container" id="alpine-chat-container" style="display: none;">
                    <!-- En-tête -->
                    <div class="alpine-chat-header">
                        <div class="alpine-chat-title">
                            <div class="alpine-chat-avatar">
                                <svg viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M12 2C13.1 2 14 2.9 14 4C14 5.1 13.1 6 12 6C10.9 6 10 5.1 10 4C10 2.9 10.9 2 12 2Z"/>
                                </svg>
                            </div>
                            <div class="alpine-chat-info">
                                <div class="alpine-chat-name">${this.territoryConfig?.name || 'Alpine Guide'}</div>
                                <div class="alpine-chat-status">En ligne</div>
                            </div>
                        </div>
                        <div class="alpine-chat-actions">
                            <button class="alpine-chat-reset" id="alpine-chat-reset" title="Nouvelle conversation">
                                <svg viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z"/>
                                </svg>
                            </button>
                            <button class="alpine-chat-close" id="alpine-chat-close" title="Fermer">
                                <svg viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Messages -->
                    <div class="alpine-chat-messages" id="alpine-chat-messages">
                        <!-- Message de bienvenue -->
                        <div class="alpine-message alpine-message-bot">
                            <div class="alpine-message-content">
                                ${this.config.welcomeMessage || 'Bonjour ! Comment puis-je vous aider ?'}
                            </div>
                        </div>
                    </div>
                    
                    <!-- Indicateur de frappe -->
                    <div class="alpine-typing-indicator" id="alpine-typing-indicator" style="display: none;">
                        <div class="alpine-typing-dots">
                            <span></span>
                            <span></span>
                            <span></span>
                        </div>
                    </div>
                    
                    <!-- Suggestions -->
                    <div class="alpine-suggestions" id="alpine-suggestions" style="display: none;">
                        <!-- Suggestions dynamiques -->
                    </div>
                    
                    <!-- Zone de saisie -->
                    <div class="alpine-chat-input-container">
                        <div class="alpine-chat-input-wrapper">
                            <textarea 
                                id="alpine-chat-input" 
                                class="alpine-chat-input" 
                                placeholder="${this.config.placeholder}"
                                rows="1"
                                maxlength="1000"></textarea>
                            <button class="alpine-chat-send" id="alpine-chat-send" disabled>
                                <svg viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M2,21L23,12L2,3V10L17,12L2,14V21Z"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div class="alpine-chat-footer">
                        <div class="alpine-powered-by">
                            Propulsé par <strong>Alpine Guide</strong>
                        </div>
                    </div>
                </div>
            `;
            
            // Ajouter au DOM
            document.body.appendChild(container);
            
            // Stocker les références
            this.elements = {
                container,
                trigger: container.querySelector('#alpine-trigger'),
                chatContainer: container.querySelector('#alpine-chat-container'),
                messages: container.querySelector('#alpine-chat-messages'),
                input: container.querySelector('#alpine-chat-input'),
                sendButton: container.querySelector('#alpine-chat-send'),
                closeButton: container.querySelector('#alpine-chat-close'),
                resetButton: container.querySelector('#alpine-chat-reset'),
                typingIndicator: container.querySelector('#alpine-typing-indicator'),
                suggestions: container.querySelector('#alpine-suggestions'),
                notification: container.querySelector('#alpine-notification')
            };
        }
        
        /**
         * Injecte les styles CSS
         */
        injectStyles() {
            if (document.getElementById('alpine-widget-styles')) return;
            
            const styles = document.createElement('style');
            styles.id = 'alpine-widget-styles';
            styles.textContent = `
                /* Variables CSS */
                :root {
                    --alpine-primary: ${this.config.primaryColor};
                    --alpine-primary-dark: ${this.darkenColor(this.config.primaryColor, 10)};
                    --alpine-bg: ${this.config.theme === 'dark' ? '#1A1A1A' : '#FFFFFF'};
                    --alpine-surface: ${this.config.theme === 'dark' ? '#2D2D2D' : '#F8FAFC'};
                    --alpine-text: ${this.config.theme === 'dark' ? '#FFFFFF' : '#1A1A1A'};
                    --alpine-text-secondary: ${this.config.theme === 'dark' ? '#B0B0B0' : '#6B7280'};
                    --alpine-border: ${this.config.theme === 'dark' ? '#404040' : '#E5E7EB'};
                }
                
                /* Container principal */
                #alpine-guide-widget {
                    position: fixed;
                    z-index: 999999;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    font-size: 14px;
                    line-height: 1.4;
                }
                
                /* Positionnement */
                .alpine-widget-bottom-right {
                    bottom: 24px;
                    right: 24px;
                }
                
                .alpine-widget-bottom-left {
                    bottom: 24px;
                    left: 24px;
                }
                
                .alpine-widget-top-right {
                    top: 24px;
                    right: 24px;
                }
                
                .alpine-widget-top-left {
                    top: 24px;
                    left: 24px;
                }
                
                /* Bouton flottant */
                .alpine-trigger {
                    width: 60px;
                    height: 60px;
                    background: var(--alpine-primary);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    box-shadow: 0 4px 20px rgba(0, 102, 204, 0.3);
                    transition: all 0.3s ease;
                    position: relative;
                }
                
                .alpine-trigger:hover {
                    background: var(--alpine-primary-dark);
                    transform: scale(1.05);
                    box-shadow: 0 6px 25px rgba(0, 102, 204, 0.4);
                }
                
                .alpine-trigger-icon {
                    width: 24px;
                    height: 24px;
                    color: white;
                }
                
                .alpine-trigger-notification {
                    position: absolute;
                    top: -5px;
                    right: -5px;
                    background: #FF4444;
                    color: white;
                    border-radius: 50%;
                    width: 20px;
                    height: 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 12px;
                    font-weight: bold;
                }
                
                /* Container de chat */
                .alpine-chat-container {
                    width: 380px;
                    height: 600px;
                    background: var(--alpine-bg);
                    border-radius: 16px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
                    display: flex;
                    flex-direction: column;
                    position: absolute;
                    bottom: 80px;
                    right: 0;
                    overflow: hidden;
                    border: 1px solid var(--alpine-border);
                }
                
                .alpine-widget-bottom-left .alpine-chat-container {
                    right: auto;
                    left: 0;
                }
                
                .alpine-widget-top-right .alpine-chat-container,
                .alpine-widget-top-left .alpine-chat-container {
                    bottom: auto;
                    top: 80px;
                }
                
                /* En-tête */
                .alpine-chat-header {
                    padding: 16px 20px;
                    background: var(--alpine-primary);
                    color: white;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                }
                
                .alpine-chat-title {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }
                
                .alpine-chat-avatar {
                    width: 40px;
                    height: 40px;
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                
                .alpine-chat-avatar svg {
                    width: 20px;
                    height: 20px;
                }
                
                .alpine-chat-name {
                    font-weight: 600;
                    font-size: 16px;
                }
                
                .alpine-chat-status {
                    font-size: 12px;
                    opacity: 0.8;
                }
                
                .alpine-chat-actions {
                    display: flex;
                    gap: 4px;
                }
                
                .alpine-chat-reset,
                .alpine-chat-close {
                    background: none;
                    border: none;
                    color: white;
                    cursor: pointer;
                    padding: 8px;
                    border-radius: 4px;
                    transition: background 0.2s;
                }
                
                .alpine-chat-reset:hover,
                .alpine-chat-close:hover {
                    background: rgba(255, 255, 255, 0.1);
                }
                
                .alpine-chat-reset svg,
                .alpine-chat-close svg {
                    width: 20px;
                    height: 20px;
                }
                
                /* Messages */
                .alpine-chat-messages {
                    flex: 1;
                    overflow-y: auto;
                    padding: 20px;
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                }
                
                .alpine-message {
                    display: flex;
                    max-width: 80%;
                }
                
                .alpine-message-bot {
                    align-self: flex-start;
                }
                
                .alpine-message-user {
                    align-self: flex-end;
                }
                
                .alpine-message-content {
                    padding: 12px 16px;
                    border-radius: 18px;
                    word-wrap: break-word;
                }
                
                .alpine-message-bot .alpine-message-content {
                    background: var(--alpine-surface);
                    color: var(--alpine-text);
                    border-bottom-left-radius: 4px;
                }
                
                .alpine-message-user .alpine-message-content {
                    background: var(--alpine-primary);
                    color: white;
                    border-bottom-right-radius: 4px;
                }
                
                /* Indicateur de frappe */
                .alpine-typing-indicator {
                    padding: 12px 20px;
                    background: var(--alpine-surface);
                    border-top: 1px solid var(--alpine-border);
                }
                
                .alpine-typing-dots {
                    display: flex;
                    gap: 4px;
                }
                
                .alpine-typing-dots span {
                    width: 8px;
                    height: 8px;
                    background: var(--alpine-text-secondary);
                    border-radius: 50%;
                    animation: alpine-typing 1.4s infinite ease-in-out;
                }
                
                .alpine-typing-dots span:nth-child(2) {
                    animation-delay: 0.2s;
                }
                
                .alpine-typing-dots span:nth-child(3) {
                    animation-delay: 0.4s;
                }
                
                @keyframes alpine-typing {
                    0%, 80%, 100% {
                        transform: scale(0.8);
                        opacity: 0.5;
                    }
                    40% {
                        transform: scale(1);
                        opacity: 1;
                    }
                }
                
                /* Suggestions */
                .alpine-suggestions {
                    padding: 12px 20px;
                    border-top: 1px solid var(--alpine-border);
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                }
                
                .alpine-suggestion {
                    padding: 6px 12px;
                    background: var(--alpine-surface);
                    border: 1px solid var(--alpine-border);
                    border-radius: 16px;
                    cursor: pointer;
                    font-size: 12px;
                    transition: all 0.2s;
                }
                
                .alpine-suggestion:hover {
                    background: var(--alpine-primary);
                    color: white;
                    border-color: var(--alpine-primary);
                }
                
                /* Zone de saisie */
                .alpine-chat-input-container {
                    padding: 16px 20px;
                    border-top: 1px solid var(--alpine-border);
                    background: var(--alpine-bg);
                }
                
                .alpine-chat-input-wrapper {
                    display: flex;
                    align-items: flex-end;
                    gap: 12px;
                    background: var(--alpine-surface);
                    border-radius: 24px;
                    padding: 8px 12px;
                    border: 1px solid var(--alpine-border);
                }
                
                .alpine-chat-input {
                    flex: 1;
                    border: none;
                    outline: none;
                    background: transparent;
                    color: var(--alpine-text);
                    resize: none;
                    max-height: 120px;
                    min-height: 20px;
                    font-family: inherit;
                    font-size: 14px;
                    line-height: 1.4;
                }
                
                .alpine-chat-input::placeholder {
                    color: var(--alpine-text-secondary);
                }
                
                .alpine-chat-send {
                    width: 32px;
                    height: 32px;
                    border: none;
                    background: var(--alpine-primary);
                    color: white;
                    border-radius: 50%;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: all 0.2s;
                    flex-shrink: 0;
                }
                
                .alpine-chat-send:disabled {
                    background: var(--alpine-border);
                    cursor: not-allowed;
                }
                
                .alpine-chat-send:not(:disabled):hover {
                    background: var(--alpine-primary-dark);
                    transform: scale(1.05);
                }
                
                .alpine-chat-send svg {
                    width: 16px;
                    height: 16px;
                }
                
                /* Footer */
                .alpine-chat-footer {
                    padding: 8px 20px;
                    text-align: center;
                    font-size: 11px;
                    color: var(--alpine-text-secondary);
                    border-top: 1px solid var(--alpine-border);
                }
                
                /* Liens cartographiques */
                .alpine-maps-container {
                    margin-top: 12px;
                    padding: 12px;
                    background: var(--alpine-surface);
                    border-radius: 8px;
                    border: 1px solid var(--alpine-border);
                }
                
                .alpine-maps-title {
                    font-weight: 600;
                    color: var(--alpine-text);
                    margin-bottom: 8px;
                    font-size: 13px;
                }
                
                .alpine-poi-maps {
                    margin-bottom: 12px;
                }
                
                .alpine-poi-maps:last-child {
                    margin-bottom: 0;
                }
                
                .alpine-poi-name {
                    font-weight: 500;
                    color: var(--alpine-text);
                    margin-bottom: 6px;
                    font-size: 12px;
                }
                
                .alpine-maps-buttons {
                    display: flex;
                    gap: 8px;
                    flex-wrap: wrap;
                }
                
                .alpine-map-button {
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    padding: 6px 12px;
                    background: var(--alpine-primary);
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 500;
                    transition: all 0.2s;
                    border: none;
                    cursor: pointer;
                }
                
                .alpine-map-button:hover {
                    background: var(--alpine-primary-dark);
                    transform: translateY(-1px);
                    box-shadow: 0 2px 8px rgba(0, 102, 204, 0.3);
                }
                
                .alpine-map-button:active {
                    transform: translateY(0);
                }
                
                .alpine-map-icon {
                    font-size: 14px;
                }
                
                .alpine-map-label {
                    white-space: nowrap;
                }
                
                .alpine-apple-maps-btn {
                    background: #007AFF;
                }
                
                .alpine-apple-maps-btn:hover {
                    background: #0056CC;
                }
                
                /* Responsive */
                @media (max-width: 480px) {
                    #alpine-guide-widget {
                        bottom: 16px !important;
                        right: 16px !important;
                        left: 16px !important;
                        top: auto !important;
                    }
                    
                    .alpine-chat-container {
                        width: 100% !important;
                        height: 70vh !important;
                        bottom: 80px !important;
                        right: 0 !important;
                        left: 0 !important;
                    }
                }
                
                /* Animations */
                .alpine-widget-fade-in {
                    animation: alpineFadeIn 0.3s ease-out;
                }
                
                .alpine-widget-fade-out {
                    animation: alpineFadeOut 0.2s ease-in;
                }
                
                @keyframes alpineFadeIn {
                    from {
                        opacity: 0;
                        transform: translateY(20px) scale(0.95);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0) scale(1);
                    }
                }
                
                @keyframes alpineFadeOut {
                    from {
                        opacity: 1;
                        transform: translateY(0) scale(1);
                    }
                    to {
                        opacity: 0;
                        transform: translateY(20px) scale(0.95);
                    }
                }
                
                /* Styles pour les POI */
                .poi-item {
                    margin: 12px 0;
                    padding: 12px;
                    background: var(--alpine-surface);
                    border-radius: 8px;
                    border: 1px solid var(--alpine-border);
                }
                
                .poi-item h3 {
                    margin: 0 0 8px 0;
                    font-size: 16px;
                    font-weight: 600;
                    color: var(--alpine-text);
                }
                
                .poi-item p {
                    margin: 0 0 10px 0;
                    color: var(--alpine-text-secondary);
                    line-height: 1.4;
                }
                
                .poi-links {
                    display: flex;
                    gap: 8px;
                    flex-wrap: wrap;
                }
                
                .map-link {
                    display: inline-flex;
                    align-items: center;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 500;
                    text-decoration: none;
                    border-radius: 6px;
                    transition: all 0.2s;
                    gap: 4px;
                }
                
                .map-link.google {
                    background: #4285f4;
                    color: white;
                }
                
                .map-link.google:hover {
                    background: #3367d6;
                    transform: translateY(-1px);
                }
                
                .map-link.apple {
                    background: #007AFF;
                    color: white;
                }
                
                .map-link.apple:hover {
                    background: #0056CC;
                    transform: translateY(-1px);
                }
            `;
            
            document.head.appendChild(styles);
        }
        
        /**
         * Attache les événements
         */
        attachEvents() {
            // Ouvrir/fermer le widget
            this.elements.trigger.addEventListener('click', () => this.toggle());
            this.elements.closeButton.addEventListener('click', () => this.close());
            this.elements.resetButton.addEventListener('click', () => this.resetConversation());
            
            // Envoyer message
            this.elements.sendButton.addEventListener('click', () => this.sendMessage());
            this.elements.input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            
            // Auto-resize du textarea
            this.elements.input.addEventListener('input', () => {
                this.autoResizeTextarea();
                this.updateSendButton();
            });
            
            // Suggestions
            this.elements.suggestions.addEventListener('click', (e) => {
                if (e.target.classList.contains('alpine-suggestion')) {
                    this.selectSuggestion(e.target.textContent);
                }
            });
            
            // Fermer en cliquant à l'extérieur
            document.addEventListener('click', (e) => {
                if (!this.elements.container.contains(e.target) && this.state.isOpen) {
                    // this.close(); // Optionnel
                }
            });
            
            // Raccourcis clavier
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.state.isOpen) {
                    this.close();
                }
            });
        }
        
        /**
         * Ouvre le widget
         */
        open() {
            if (this.state.isOpen) return;
            
            this.state.isOpen = true;
            this.elements.chatContainer.style.display = 'flex';
            this.elements.chatContainer.classList.add('alpine-widget-fade-in');
            
            // Focus sur l'input
            setTimeout(() => {
                this.elements.input.focus();
            }, 300);
            
            // Cacher la notification
            this.elements.notification.style.display = 'none';
            
            this.log('Widget ouvert');
        }
        
        /**
         * Ferme le widget
         */
        close() {
            if (!this.state.isOpen) return;
            
            this.state.isOpen = false;
            this.elements.chatContainer.classList.add('alpine-widget-fade-out');
            
            setTimeout(() => {
                this.elements.chatContainer.style.display = 'none';
                this.elements.chatContainer.classList.remove('alpine-widget-fade-in', 'alpine-widget-fade-out');
            }, 200);
            
            this.log('Widget fermé');
        }
        
        /**
         * Réinitialise la conversation
         */
        resetConversation() {
            // Réinitialiser l'état
            this.state.sessionId = this.generateSessionId();
            this.state.conversations = [];
            this.state.isTyping = false;
            
            // Vider les messages
            this.elements.messages.innerHTML = `
                <div class="alpine-message alpine-message-bot">
                    <div class="alpine-message-content">
                        ${this.config.welcomeMessage || 'Bonjour ! Comment puis-je vous aider ?'}
                    </div>
                </div>
            `;
            
            // Vider l'input
            this.elements.input.value = '';
            this.updateSendButton();
            
            // Cacher les suggestions
            this.elements.suggestions.style.display = 'none';
            
            // Sauvegarder l'historique vide
            if (this.config.persistHistory) {
                this.saveHistory();
            }
            
            this.log('Conversation réinitialisée');
        }
        
        /**
         * Bascule l'état du widget
         */
        toggle() {
            if (this.state.isOpen) {
                this.close();
            } else {
                this.open();
            }
        }
        
        /**
         * Envoie un message
         */
        async sendMessage(text = null) {
            const message = text || this.elements.input.value.trim();
            if (!message || this.state.isLoading) return;
            
            // Ajouter le message utilisateur
            this.addMessage(message, 'user');
            
            // Vider l'input
            this.elements.input.value = '';
            this.autoResizeTextarea();
            this.updateSendButton();
            
            // Indicateur de frappe
            this.showTyping();
            
            try {
                this.state.isLoading = true;
                
                // Appel API
                const response = await fetch(`${this.config.apiBase}/chat`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.config.apiKey}`
                    },
                    body: JSON.stringify({
                        message,
                        session_id: this.state.sessionId,
                        territory: this.config.territory,
                        language: this.config.language
                    })
                });
                
                if (!response.ok) {
                    throw new Error(`Erreur ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                // Cacher l'indicateur de frappe
                this.hideTyping();
                
                // Ajouter la réponse avec données pour liens cartographiques
                this.addMessage(data.message, 'bot', data);
                
                // Suggestions
                if (data.suggestions && data.suggestions.length > 0) {
                    this.showSuggestions(data.suggestions);
                } else {
                    this.hideSuggestions();
                }
                
                // Sauvegarder la conversation
                if (this.config.persistHistory) {
                    this.saveHistory();
                }
                
                // Callback
                if (this.config.onMessage) {
                    this.config.onMessage(data, this);
                }
                
            } catch (error) {
                this.hideTyping();
                this.addMessage('Désolé, une erreur s\'est produite. Veuillez réessayer.', 'bot');
                this.error('Erreur lors de l\'envoi du message', error);
                
                if (this.config.onError) {
                    this.config.onError(error, this);
                }
            } finally {
                this.state.isLoading = false;
            }
        }
        
        /**
         * Ajoute un message à la conversation
         */
        addMessage(text, sender, data = null) {
            const messageEl = document.createElement('div');
            messageEl.className = `alpine-message alpine-message-${sender}`;
            
            const contentEl = document.createElement('div');
            contentEl.className = 'alpine-message-content';
            
            // Utiliser innerHTML pour le rendu HTML des POIs
            if (sender === 'bot' && text.includes('<div class="poi-item">')) {
                contentEl.innerHTML = text;
            } else {
                contentEl.textContent = text;
            }
            
            messageEl.appendChild(contentEl);
            
            // Ajouter les boutons cartographiques si des liens sont disponibles
            if (sender === 'bot' && data && this.hasMapLinks(data)) {
                const mapsContainer = this.createMapsLinksContainer(data);
                if (mapsContainer) {
                    messageEl.appendChild(mapsContainer);
                }
            }
            
            this.elements.messages.appendChild(messageEl);
            
            // Scroll vers le bas
            this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
            
            // Ajouter à l'historique
            this.state.conversations.push({
                text,
                sender,
                timestamp: Date.now(),
                data: data || null
            });
        }
        
        /**
         * Vérifie si les données contiennent des liens cartographiques
         */
        hasMapLinks(data) {
            // Vérifier dans les activités/recommandations
            const activities = data.activities || data.recommendations || [];
            return activities.some(activity => 
                activity.maps_links && activity.maps_links.has_links
            );
        }
        
        /**
         * Crée le conteneur des liens cartographiques
         */
        createMapsLinksContainer(data) {
            const activities = data.activities || data.recommendations || [];
            const activitiesWithLinks = activities.filter(activity => 
                activity.maps_links && activity.maps_links.has_links
            );
            
            if (activitiesWithLinks.length === 0) {
                return null;
            }
            
            const container = document.createElement('div');
            container.className = 'alpine-maps-container';
            
            // Titre si plusieurs POIs
            if (activitiesWithLinks.length > 1) {
                const title = document.createElement('div');
                title.className = 'alpine-maps-title';
                title.textContent = `📍 ${activitiesWithLinks.length} lieu(x) sur la carte`;
                container.appendChild(title);
            }
            
            // Boutons pour chaque POI avec liens
            activitiesWithLinks.forEach((activity, index) => {
                const poiContainer = this.createSinglePOIMapsLinks(activity, index);
                if (poiContainer) {
                    container.appendChild(poiContainer);
                }
            });
            
            return container;
        }
        
        /**
         * Crée les liens cartographiques pour un seul POI
         */
        createSinglePOIMapsLinks(activity, index = 0) {
            const maps = activity.maps_links;
            if (!maps || !maps.has_links) {
                return null;
            }
            
            const container = document.createElement('div');
            container.className = 'alpine-poi-maps';
            
            // Nom du POI
            const poiName = document.createElement('div');
            poiName.className = 'alpine-poi-name';
            poiName.textContent = activity.name || `Lieu ${index + 1}`;
            container.appendChild(poiName);
            
            // Conteneur des boutons
            const buttonsContainer = document.createElement('div');
            buttonsContainer.className = 'alpine-maps-buttons';
            
            // Bouton Google Maps
            if (maps.google_maps) {
                const gmapsButton = this.createMapButton(
                    'Google Maps',
                    maps.google_maps,
                    '🗺️',
                    'alpine-gmaps-btn'
                );
                buttonsContainer.appendChild(gmapsButton);
            }
            
            // Bouton Apple Plans (seulement sur appareils Apple)
            if (maps.apple_maps && this.isAppleDevice()) {
                const appleMapsButton = this.createMapButton(
                    'Plans',
                    maps.apple_maps,
                    '🍎',
                    'alpine-apple-maps-btn'
                );
                buttonsContainer.appendChild(appleMapsButton);
            }
            
            container.appendChild(buttonsContainer);
            return container;
        }
        
        /**
         * Crée un bouton de lien cartographique
         */
        createMapButton(label, url, icon, className) {
            const button = document.createElement('a');
            button.href = url;
            button.target = '_blank';
            button.rel = 'noopener';
            button.className = `alpine-map-button ${className}`;
            
            button.innerHTML = `
                <span class="alpine-map-icon">${icon}</span>
                <span class="alpine-map-label">${label}</span>
            `;
            
            // Analytics : tracker les clics
            button.addEventListener('click', () => {
                this.trackMapClick(label.toLowerCase().replace(' ', '_'), url);
            });
            
            return button;
        }
        
        /**
         * Détecte si l'appareil est un appareil Apple
         */
        isAppleDevice() {
            return /iPad|iPhone|Macintosh/.test(navigator.userAgent);
        }
        
        /**
         * Track les clics sur les liens cartographiques
         */
        trackMapClick(provider, url) {
            // Analytics : envoyer l'événement
            if (this.config.onMapClick) {
                this.config.onMapClick(provider, url, this);
            }
            
            // Console pour debug
            this.log(`Map click: ${provider} -> ${url}`);
        }
        
        /**
         * Affiche l'indicateur de frappe
         */
        showTyping() {
            this.state.isTyping = true;
            this.elements.typingIndicator.style.display = 'block';
            this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
        }
        
        /**
         * Cache l'indicateur de frappe
         */
        hideTyping() {
            this.state.isTyping = false;
            this.elements.typingIndicator.style.display = 'none';
        }
        
        /**
         * Affiche les suggestions
         */
        showSuggestions(suggestions) {
            this.elements.suggestions.innerHTML = '';
            
            suggestions.forEach(suggestion => {
                const suggestionEl = document.createElement('button');
                suggestionEl.className = 'alpine-suggestion';
                suggestionEl.textContent = suggestion;
                this.elements.suggestions.appendChild(suggestionEl);
            });
            
            this.elements.suggestions.style.display = 'flex';
        }
        
        /**
         * Cache les suggestions
         */
        hideSuggestions() {
            this.elements.suggestions.style.display = 'none';
        }
        
        /**
         * Sélectionne une suggestion
         */
        selectSuggestion(text) {
            this.elements.input.value = text;
            this.autoResizeTextarea();
            this.updateSendButton();
            this.hideSuggestions();
            this.sendMessage();
        }
        
        /**
         * Auto-resize du textarea
         */
        autoResizeTextarea() {
            const input = this.elements.input;
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        }
        
        /**
         * Met à jour l'état du bouton d'envoi
         */
        updateSendButton() {
            const hasText = this.elements.input.value.trim().length > 0;
            this.elements.sendButton.disabled = !hasText || this.state.isLoading;
        }
        
        /**
         * Génère un ID de session unique
         */
        generateSessionId() {
            return 'alpine_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        }
        
        /**
         * Assombrit une couleur
         */
        darkenColor(color, percent) {
            const num = parseInt(color.replace("#", ""), 16);
            const amt = Math.round(2.55 * percent);
            const R = (num >> 16) - amt;
            const G = (num >> 8 & 0x00FF) - amt;
            const B = (num & 0x0000FF) - amt;
            return "#" + (0x1000000 + (R < 255 ? R < 1 ? 0 : R : 255) * 0x10000 +
                (G < 255 ? G < 1 ? 0 : G : 255) * 0x100 +
                (B < 255 ? B < 1 ? 0 : B : 255)).toString(16).slice(1);
        }
        
        /**
         * Sauvegarde l'historique
         */
        saveHistory() {
            try {
                const historyKey = `alpine_history_${this.config.territory}`;
                localStorage.setItem(historyKey, JSON.stringify({
                    sessionId: this.state.sessionId,
                    conversations: this.state.conversations.slice(-20), // Garder les 20 derniers
                    timestamp: Date.now()
                }));
            } catch (error) {
                this.log('Impossible de sauvegarder l\'historique', error);
            }
        }
        
        /**
         * Charge l'historique
         */
        loadHistory() {
            try {
                const historyKey = `alpine_history_${this.config.territory}`;
                const saved = localStorage.getItem(historyKey);
                
                if (saved) {
                    const data = JSON.parse(saved);
                    
                    // Vérifier si l'historique n'est pas trop ancien (24h)
                    if (Date.now() - data.timestamp < 86400000) {
                        this.state.sessionId = data.sessionId;
                        this.state.conversations = data.conversations || [];
                        
                        // Restaurer les messages dans l'interface
                        data.conversations.forEach(conv => {
                            this.addMessage(conv.text, conv.sender);
                        });
                    }
                }
            } catch (error) {
                this.log('Impossible de charger l\'historique', error);
            }
        }
        
        /**
         * Logs de debug
         */
        log(...args) {
            if (this.config.debug) {
                console.log('[Alpine Guide Widget]', ...args);
            }
        }
        
        /**
         * Logs d'erreur
         */
        error(...args) {
            console.error('[Alpine Guide Widget]', ...args);
        }
        
        /**
         * API publique
         */
        
        // Envoyer un message par programmation
        sendMessageProgrammatically(message) {
            return this.sendMessage(message);
        }
        
        // Ouvrir/fermer par programmation
        openWidget() {
            this.open();
        }
        
        closeWidget() {
            this.close();
        }
        
        // Obtenir l'état
        getState() {
            return { ...this.state };
        }
        
        // Mettre à jour la configuration
        updateConfig(newConfig) {
            this.config = { ...this.config, ...newConfig };
            this.applyTerritoryConfig();
        }
        
        // Nettoyer l'historique
        clearHistory() {
            this.state.conversations = [];
            this.elements.messages.innerHTML = `
                <div class="alpine-message alpine-message-bot">
                    <div class="alpine-message-content">
                        ${this.config.welcomeMessage || 'Bonjour ! Comment puis-je vous aider ?'}
                    </div>
                </div>
            `;
            
            const historyKey = `alpine_history_${this.config.territory}`;
            localStorage.removeItem(historyKey);
        }
        
        // Détruire le widget
        destroy() {
            if (this.elements.container) {
                this.elements.container.remove();
            }
            
            const styles = document.getElementById('alpine-widget-styles');
            if (styles) {
                styles.remove();
            }
        }
    }
    
    // Auto-initialisation depuis les attributs du script
    function autoInit() {
        const scripts = document.querySelectorAll('script[src*="alpine-guide-widget.js"]');
        const currentScript = scripts[scripts.length - 1];
        
        if (currentScript) {
            const config = {
                territory: currentScript.getAttribute('data-territory') || 'annecy',
                apiKey: currentScript.getAttribute('data-api-key') || '',
                apiBase: currentScript.getAttribute('data-api-base') || DEFAULT_API_BASE,
                language: currentScript.getAttribute('data-language') || 'fr',
                position: currentScript.getAttribute('data-position') || 'bottom-right',
                theme: currentScript.getAttribute('data-theme') || 'light',
                primaryColor: currentScript.getAttribute('data-primary-color') || '#0066CC',
                autoOpen: currentScript.getAttribute('data-auto-open') === 'true',
                debug: currentScript.getAttribute('data-debug') === 'true'
            };
            
            // Attendre que le DOM soit prêt
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => {
                    window.AlpineGuideWidget = new AlpineGuideWidget(config);
                });
            } else {
                window.AlpineGuideWidget = new AlpineGuideWidget(config);
            }
        }
    }
    
    // Exposer la classe globalement
    window.AlpineGuideWidget = AlpineGuideWidget;
    
    // Auto-initialisation
    autoInit();
    
})();