#!/bin/bash

# Script d'installation Alpine Guide Widget
# Installation complète et automatisée pour déploiement marque blanche

set -euo pipefail

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration par défaut
DEFAULT_DOMAIN="localhost"
DEFAULT_EMAIL="admin@example.com"
DEFAULT_ENVIRONMENT="production"

# Variables globales
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INSTALL_LOG="/tmp/alpine-guide-install.log"

# Fonctions utilitaires
log() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$INSTALL_LOG"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$INSTALL_LOG"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$INSTALL_LOG"
    exit 1
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        error "Commande '$1' non trouvée. Veuillez l'installer."
    fi
}

# Banner d'installation
show_banner() {
    echo -e "${BLUE}"
    cat << "EOF"
    ╔═══════════════════════════════════════════╗
    ║        🏔️  Alpine Guide Widget          ║
    ║      Installation & Déploiement          ║
    ║                                           ║
    ║    Déploiement Marque Blanche Rapide     ║
    ╚═══════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# Vérification des prérequis
check_prerequisites() {
    log "Vérification des prérequis..."
    
    # Vérifier Docker
    if ! command -v docker &> /dev/null; then
        error "Docker n'est pas installé. Veuillez installer Docker: https://docs.docker.com/get-docker/"
    fi
    
    # Vérifier Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error "Docker Compose n'est pas installé. Veuillez installer Docker Compose."
    fi
    
    # Vérifier que Docker fonctionne
    if ! docker info &> /dev/null; then
        error "Docker n'est pas démarré ou vous n'avez pas les permissions nécessaires."
    fi
    
    # Vérifier Node.js pour le build du widget
    if ! command -v node &> /dev/null; then
        warn "Node.js n'est pas installé. Le widget sera buildé dans Docker."
    fi
    
    log "✅ Tous les prérequis sont satisfaits"
}

# Configuration interactive
configure_installation() {
    log "Configuration de l'installation..."
    
    echo
    echo -e "${BLUE}Configuration du déploiement${NC}"
    echo "================================"
    
    # Domaine
    read -p "Domaine du widget (défaut: $DEFAULT_DOMAIN): " DOMAIN
    DOMAIN=${DOMAIN:-$DEFAULT_DOMAIN}
    
    # Email pour SSL
    read -p "Email pour les certificats SSL (défaut: $DEFAULT_EMAIL): " EMAIL
    EMAIL=${EMAIL:-$DEFAULT_EMAIL}
    
    # Environnement
    read -p "Environnement (production/development, défaut: $DEFAULT_ENVIRONMENT): " ENVIRONMENT
    ENVIRONMENT=${ENVIRONMENT:-$DEFAULT_ENVIRONMENT}
    
    # Clé API Gemini
    echo
    echo -e "${YELLOW}Clés API requises:${NC}"
    while [[ -z "${GEMINI_API_KEY:-}" ]]; do
        read -s -p "Clé API Gemini (obligatoire): " GEMINI_API_KEY
        echo
        if [[ -z "$GEMINI_API_KEY" ]]; then
            error "La clé API Gemini est obligatoire"
        fi
    done
    
    # Clé API météo (optionnelle)
    read -s -p "Clé API OpenWeatherMap (optionnelle): " OPENWEATHER_API_KEY
    echo
    
    # Configuration base de données (optionnelle)
    read -p "URL de base de données (optionnelle, pour persistance avancée): " DATABASE_URL
    
    # Monitoring
    read -p "Activer le monitoring (Prometheus/Grafana) ? (y/N): " ENABLE_MONITORING
    ENABLE_MONITORING=${ENABLE_MONITORING:-n}
    
    # Mot de passe Grafana
    if [[ "$ENABLE_MONITORING" =~ ^[Yy]$ ]]; then
        read -s -p "Mot de passe Grafana (défaut: admin123): " GRAFANA_PASSWORD
        echo
        GRAFANA_PASSWORD=${GRAFANA_PASSWORD:-admin123}
    fi
    
    log "✅ Configuration terminée"
}

# Génération du fichier .env
generate_env_file() {
    log "Génération du fichier de configuration..."
    
    cat > "$SCRIPT_DIR/.env" << EOF
# Configuration Alpine Guide Widget
# Généré le $(date)

# Domaine et environnement
DOMAIN=$DOMAIN
EMAIL=$EMAIL
ENVIRONMENT=$ENVIRONMENT

# APIs clés
GEMINI_API_KEY=$GEMINI_API_KEY
OPENWEATHER_API_KEY=${OPENWEATHER_API_KEY:-}

# Base de données (optionnelle)
DATABASE_URL=${DATABASE_URL:-}

# Monitoring
GRAFANA_PASSWORD=${GRAFANA_PASSWORD:-admin123}

# Configuration avancée
CORS_ORIGINS=*
LOG_LEVEL=info
CACHE_DEFAULT_TTL=1800

# Ne pas modifier
COMPOSE_PROJECT_NAME=alpine-guide
EOF
    
    # Sécuriser le fichier .env
    chmod 600 "$SCRIPT_DIR/.env"
    
    log "✅ Fichier .env créé"
}

# Génération de la configuration Nginx
generate_nginx_config() {
    log "Configuration du serveur web..."
    
    cat > "$SCRIPT_DIR/locations.conf" << 'EOF'
# Configuration des locations Nginx pour Alpine Guide Widget

# Healthcheck
location /health {
    access_log off;
    return 200 'OK';
    add_header Content-Type text/plain;
}

# API Routes - Proxy vers l'API FastAPI
location /api/ {
    limit_req zone=api burst=20 nodelay;
    
    proxy_pass http://alpine_api;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cache_bypass $http_upgrade;
    
    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    
    # CORS pour API
    if ($cors_origin != "") {
        add_header Access-Control-Allow-Origin $cors_origin always;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;
        add_header Access-Control-Allow-Credentials true always;
    }
    
    # Préflight CORS
    if ($request_method = 'OPTIONS') {
        add_header Access-Control-Allow-Origin $cors_origin;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
        add_header Access-Control-Allow-Headers "Content-Type, Authorization";
        add_header Access-Control-Max-Age 86400;
        return 204;
    }
}

# Widget JavaScript et assets
location /widget/ {
    limit_req zone=widget burst=100 nodelay;
    
    alias /usr/share/nginx/html/widget/;
    
    # Cache headers
    add_header Cache-Control $cache_control;
    add_header X-Content-Type-Options nosniff;
    
    # CORS pour widget embeddable
    if ($cors_origin != "") {
        add_header Access-Control-Allow-Origin $cors_origin always;
        add_header Access-Control-Allow-Methods "GET" always;
    }
    
    # Fallback pour les fichiers manquants
    try_files $uri $uri/ =404;
    
    # Compression spécifique
    location ~* \.(js|css)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        gzip_static on;
    }
}

# Territoire configurations
location /territories/ {
    proxy_pass http://alpine_api;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    
    # Cache pour les configurations
    proxy_cache_valid 200 10m;
    proxy_cache_use_stale error timeout updating;
}

# Interface d'administration
location /admin/ {
    alias /usr/share/nginx/html/widget/admin/;
    try_files $uri $uri/ /admin/index.html;
    
    # Sécurité - restriction IP (optionnelle)
    # allow 192.168.1.0/24;
    # deny all;
    
    # Protection basique
    add_header X-Frame-Options "DENY";
    add_header X-Content-Type-Options "nosniff";
}

# Documentation (si présente)
location /docs/ {
    alias /usr/share/nginx/html/widget/docs/;
    try_files $uri $uri/ =404;
    
    # Cache pour la documentation
    expires 1h;
    add_header Cache-Control "public, max-age=3600";
}

# Redirect root vers la documentation ou admin
location = / {
    return 302 /admin/;
}

# Favicon
location = /favicon.ico {
    alias /usr/share/nginx/html/widget/favicon.ico;
    expires 1y;
    access_log off;
}

# Robots.txt
location = /robots.txt {
    return 200 "User-agent: *\nDisallow: /api/\nDisallow: /admin/\n";
    add_header Content-Type text/plain;
    access_log off;
}
EOF

    log "✅ Configuration Nginx générée"
}

# Préparation des dossiers
setup_directories() {
    log "Préparation des dossiers..."
    
    # Créer les dossiers nécessaires
    mkdir -p "$SCRIPT_DIR"/{logs,ssl,data,backups}
    mkdir -p "$SCRIPT_DIR"/logs/{nginx,api}
    
    # Configuration Redis
    cat > "$SCRIPT_DIR/redis.conf" << 'EOF'
# Configuration Redis pour Alpine Guide Widget
bind 0.0.0.0
protected-mode yes
port 6379
timeout 300
tcp-keepalive 300
daemonize no
supervised no
loglevel notice
databases 16
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir ./
maxmemory 256mb
maxmemory-policy allkeys-lru
EOF
    
    log "✅ Dossiers préparés"
}

# Build du widget
build_widget() {
    log "Build du widget JavaScript..."
    
    if command -v node &> /dev/null; then
        # Build local si Node.js est disponible
        cd "$PROJECT_ROOT/widget"
        if [[ -f "build.js" ]]; then
            node build.js
            log "✅ Widget buildé localement"
        else
            warn "Script de build non trouvé, utilisation du build Docker"
        fi
    else
        log "Build via Docker (Node.js non disponible localement)"
    fi
}

# Déploiement Docker
deploy_services() {
    log "Déploiement des services Docker..."
    
    cd "$SCRIPT_DIR"
    
    # Charger les variables d'environnement
    export $(cat .env | grep -v '^#' | xargs)
    
    # Profils Docker Compose
    COMPOSE_PROFILES="default"
    if [[ "$ENABLE_MONITORING" =~ ^[Yy]$ ]]; then
        COMPOSE_PROFILES="$COMPOSE_PROFILES,monitoring"
    fi
    
    # Pull des images
    log "Téléchargement des images Docker..."
    COMPOSE_PROFILES="$COMPOSE_PROFILES" docker-compose pull
    
    # Build des images personnalisées
    log "Build des images personnalisées..."
    COMPOSE_PROFILES="$COMPOSE_PROFILES" docker-compose build
    
    # Démarrage des services
    log "Démarrage des services..."
    COMPOSE_PROFILES="$COMPOSE_PROFILES" docker-compose up -d
    
    # Attendre que les services soient prêts
    log "Vérification du démarrage des services..."
    sleep 10
    
    # Vérifier la santé des services
    for service in alpine-api alpine-redis alpine-web; do
        if docker-compose ps | grep -q "$service.*Up.*healthy\|$service.*Up"; then
            log "✅ Service $service démarré"
        else
            warn "⚠️  Service $service en cours de démarrage..."
        fi
    done
    
    log "✅ Déploiement terminé"
}

# Configuration SSL (Let's Encrypt)
setup_ssl() {
    if [[ "$DOMAIN" != "localhost" && "$ENVIRONMENT" == "production" ]]; then
        log "Configuration SSL avec Let's Encrypt..."
        
        # Vérifier si certbot est disponible
        if command -v certbot &> /dev/null; then
            # Générer les certificats
            certbot certonly --standalone \
                --email "$EMAIL" \
                --agree-tos \
                --no-eff-email \
                -d "$DOMAIN"
            
            # Copier les certificats
            cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$SCRIPT_DIR/ssl/cert.pem"
            cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$SCRIPT_DIR/ssl/key.pem"
            
            # Configuration du renouvellement automatique
            (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
            
            log "✅ SSL configuré"
        else
            warn "Certbot non installé, certificats SSL non configurés"
            warn "Installez certbot pour activer HTTPS automatiquement"
        fi
    else
        log "SSL ignoré (domaine localhost ou environnement development)"
    fi
}

# Tests post-déploiement
run_tests() {
    log "Tests post-déploiement..."
    
    # Test de l'API
    if curl -sf "http://localhost:8000/health" > /dev/null; then
        log "✅ API accessible"
    else
        warn "⚠️  API non accessible"
    fi
    
    # Test du widget
    if curl -sf "http://localhost/widget/alpine-guide-widget.min.js" > /dev/null; then
        log "✅ Widget accessible"
    else
        warn "⚠️  Widget non accessible"
    fi
    
    # Test Redis
    if docker-compose exec -T alpine-redis redis-cli ping | grep -q PONG; then
        log "✅ Redis fonctionnel"
    else
        warn "⚠️  Redis non accessible"
    fi
    
    log "✅ Tests terminés"
}

# Affichage des informations finales
show_completion_info() {
    echo
    echo -e "${GREEN}🎉 Installation terminée avec succès !${NC}"
    echo
    echo -e "${BLUE}Informations d'accès:${NC}"
    echo "================================"
    echo "• Widget JavaScript: http://$DOMAIN/widget/alpine-guide-widget.min.js"
    echo "• Interface Admin: http://$DOMAIN/admin/"
    echo "• API Backend: http://$DOMAIN/api/"
    echo "• Documentation: http://$DOMAIN/docs/"
    
    if [[ "$ENABLE_MONITORING" =~ ^[Yy]$ ]]; then
        echo "• Monitoring Grafana: http://$DOMAIN:3000 (admin / $GRAFANA_PASSWORD)"
        echo "• Métriques Prometheus: http://$DOMAIN:9090"
    fi
    
    echo
    echo -e "${BLUE}Commandes utiles:${NC}"
    echo "================================"
    echo "• Voir les logs: docker-compose logs -f"
    echo "• Redémarrer: docker-compose restart"
    echo "• Arrêter: docker-compose down"
    echo "• Mettre à jour: docker-compose pull && docker-compose up -d"
    
    echo
    echo -e "${BLUE}Intégration sur votre site:${NC}"
    echo "================================"
    echo '<script src="http://'$DOMAIN'/widget/alpine-guide-widget.min.js"'
    echo '        data-territory="annecy"'
    echo '        data-api-key="your-api-key"></script>'
    
    echo
    echo -e "${YELLOW}N'oubliez pas:${NC}"
    echo "• Configurer votre nom de domaine DNS"
    echo "• Obtenir vos clés API (Gemini, OpenWeather)"
    echo "• Personnaliser les territoires via l'interface admin"
    echo "• Configurer les sauvegardes régulières"
    
    if [[ "$DOMAIN" != "localhost" ]]; then
        echo "• Configurer SSL/HTTPS pour la production"
    fi
    
    echo
    echo "📖 Documentation complète: https://docs.alpine-guide.com"
    echo "🐛 Support: https://github.com/alpine-guide/widget/issues"
}

# Fonction principale
main() {
    # Initialisation
    show_banner
    echo "Installation démarrée le $(date)" > "$INSTALL_LOG"
    
    # Étapes d'installation
    check_prerequisites
    configure_installation
    generate_env_file
    generate_nginx_config
    setup_directories
    build_widget
    deploy_services
    setup_ssl
    run_tests
    show_completion_info
    
    log "🎉 Installation Alpine Guide Widget terminée !"
    log "📋 Log d'installation: $INSTALL_LOG"
}

# Gestion des signaux
trap 'error "Installation interrompue"' INT TERM

# Point d'entrée
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi