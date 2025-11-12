#!/usr/bin/env node

/**
 * Script de build pour Alpine Guide Widget
 * Combine et minifie les fichiers pour déploiement production
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const CONFIG = {
  inputDir: __dirname,
  outputDir: path.join(__dirname, 'dist'),
  version: process.env.WIDGET_VERSION || '1.0.0',
  apiBase: process.env.API_BASE || 'https://api.alpine-guide.com',
  cdnBase: process.env.CDN_BASE || 'https://cdn.alpine-guide.com'
};

// Couleurs pour les logs
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function error(message) {
  log(`❌ ${message}`, 'red');
}

function success(message) {
  log(`✅ ${message}`, 'green');
}

function info(message) {
  log(`ℹ️  ${message}`, 'blue');
}

function warning(message) {
  log(`⚠️  ${message}`, 'yellow');
}

/**
 * Minifie le JavaScript
 */
function minifyJS(code) {
  try {
    // Simple minification - peut être améliorée avec Terser
    return code
      .replace(/\/\*[\s\S]*?\*\//g, '') // Supprimer les commentaires /* */
      .replace(/\/\/.*$/gm, '') // Supprimer les commentaires //
      .replace(/\s+/g, ' ') // Réduire les espaces multiples
      .replace(/;\s*}/g, '}') // Supprimer les ; avant }
      .replace(/{\s*/g, '{') // Supprimer les espaces après {
      .replace(/}\s*/g, '}') // Supprimer les espaces après }
      .replace(/,\s*/g, ',') // Supprimer les espaces après ,
      .replace(/:\s*/g, ':') // Supprimer les espaces après :
      .trim();
  } catch (err) {
    warning('Impossible de minifier le JavaScript, utilisation de la version non minifiée');
    return code;
  }
}

/**
 * Minifie le CSS
 */
function minifyCSS(code) {
  try {
    return code
      .replace(/\/\*[\s\S]*?\*\//g, '') // Supprimer les commentaires
      .replace(/\s+/g, ' ') // Réduire les espaces
      .replace(/;\s*}/g, '}') // Supprimer les ; avant }
      .replace(/{\s*/g, '{') // Supprimer les espaces après {
      .replace(/}\s*/g, '}') // Supprimer les espaces après }
      .replace(/,\s*/g, ',') // Supprimer les espaces après ,
      .replace(/:\s*/g, ':') // Supprimer les espaces après :
      .replace(/;\s*/g, ';') // Supprimer les espaces après ;
      .trim();
  } catch (err) {
    warning('Impossible de minifier le CSS, utilisation de la version non minifiée');
    return code;
  }
}

/**
 * Génère les variantes du widget
 */
function generateVariants() {
  const jsPath = path.join(CONFIG.inputDir, 'alpine-guide-widget.js');
  const cssPath = path.join(CONFIG.inputDir, 'styles.css');
  
  if (!fs.existsSync(jsPath)) {
    error(`Fichier JS non trouvé: ${jsPath}`);
    process.exit(1);
  }
  
  if (!fs.existsSync(cssPath)) {
    error(`Fichier CSS non trouvé: ${cssPath}`);
    process.exit(1);
  }
  
  const jsContent = fs.readFileSync(jsPath, 'utf8');
  const cssContent = fs.readFileSync(cssPath, 'utf8');
  
  // Remplacer les placeholders
  const processedJS = jsContent
    .replace(/DEFAULT_API_BASE = '[^']*'/, `DEFAULT_API_BASE = '${CONFIG.apiBase}'`)
    .replace(/WIDGET_VERSION = '[^']*'/, `WIDGET_VERSION = '${CONFIG.version}'`);
  
  const variants = [
    {
      name: 'alpine-guide-widget.js',
      content: processedJS,
      minified: false,
      embedded: false
    },
    {
      name: 'alpine-guide-widget.min.js',
      content: minifyJS(processedJS),
      minified: true,
      embedded: false
    },
    {
      name: 'alpine-guide-widget.embed.js',
      content: generateEmbeddedVersion(processedJS, cssContent),
      minified: false,
      embedded: true
    },
    {
      name: 'alpine-guide-widget.embed.min.js',
      content: minifyJS(generateEmbeddedVersion(processedJS, cssContent)),
      minified: true,
      embedded: true
    }
  ];
  
  // Générer les fichiers CSS séparés
  const cssVariants = [
    {
      name: 'alpine-guide-widget.css',
      content: cssContent,
      minified: false
    },
    {
      name: 'alpine-guide-widget.min.css',
      content: minifyCSS(cssContent),
      minified: true
    }
  ];
  
  return { js: variants, css: cssVariants };
}

/**
 * Génère la version avec CSS intégré
 */
function generateEmbeddedVersion(jsContent, cssContent) {
  const minifiedCSS = minifyCSS(cssContent);
  
  // Échapper les guillemets et retours à la ligne dans le CSS
  const escapedCSS = minifiedCSS
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/"/g, '\\"');
  
  // Injecter le CSS dans le JS
  const embeddedJS = jsContent.replace(
    'this.injectStyles();',
    `this.injectEmbeddedStyles('${escapedCSS}');`
  );
  
  // Ajouter la méthode d'injection de styles intégrés
  const methodToAdd = `
        injectEmbeddedStyles(cssContent) {
            if (document.getElementById('alpine-widget-styles')) return;
            const styles = document.createElement('style');
            styles.id = 'alpine-widget-styles';
            styles.textContent = cssContent;
            document.head.appendChild(styles);
        }`;
  
  return embeddedJS.replace(
    'injectStyles() {',
    `injectEmbeddedStyles(cssContent) {
            if (document.getElementById('alpine-widget-styles')) return;
            const styles = document.createElement('style');
            styles.id = 'alpine-widget-styles';
            styles.textContent = cssContent;
            document.head.appendChild(styles);
        }
        
        injectStyles() {`
  );
}

/**
 * Génère les fichiers d'intégration
 */
function generateIntegrationFiles() {
  const files = [];
  
  // Fichier d'intégration simple
  files.push({
    name: 'integration-simple.html',
    content: `<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alpine Guide Widget - Intégration Simple</title>
</head>
<body>
    <h1>Votre site web</h1>
    <p>Le widget Alpine Guide apparaît en bas à droite.</p>
    
    <!-- Widget Alpine Guide -->
    <script src="${CONFIG.cdnBase}/alpine-guide-widget.min.js" 
            data-territory="annecy" 
            data-api-key="your-api-key"
            data-language="fr"></script>
</body>
</html>`
  });
  
  // Fichier d'intégration avancée
  files.push({
    name: 'integration-advanced.html',
    content: `<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alpine Guide Widget - Intégration Avancée</title>
</head>
<body>
    <h1>Intégration personnalisée</h1>
    
    <div id="custom-widget-container"></div>
    
    <script src="${CONFIG.cdnBase}/alpine-guide-widget.min.js"></script>
    <script>
        // Configuration personnalisée
        const widget = new AlpineGuideWidget({
            territory: 'annecy',
            apiKey: 'your-api-key',
            position: 'bottom-left',
            theme: 'light',
            primaryColor: '#0066CC',
            autoOpen: false,
            
            // Callbacks
            onReady: function(widget) {
                console.log('Widget prêt !', widget);
            },
            
            onMessage: function(response, widget) {
                console.log('Nouvelle réponse:', response);
            },
            
            onError: function(error, widget) {
                console.error('Erreur widget:', error);
            }
        });
        
        // Contrôler le widget par programmation
        document.getElementById('open-widget').addEventListener('click', () => {
            widget.openWidget();
        });
        
        document.getElementById('send-message').addEventListener('click', () => {
            widget.sendMessageProgrammatically('Bonjour !');
        });
    </script>
    
    <button id="open-widget">Ouvrir le widget</button>
    <button id="send-message">Envoyer un message</button>
</body>
</html>`
  });
  
  // Documentation d'intégration
  files.push({
    name: 'README-integration.md',
    content: `# Alpine Guide Widget - Guide d'intégration

## Installation rapide

### Méthode 1 : Script simple
\`\`\`html
<script src="${CONFIG.cdnBase}/alpine-guide-widget.min.js" 
        data-territory="annecy" 
        data-api-key="your-api-key"></script>
\`\`\`

### Méthode 2 : Configuration avancée
\`\`\`html
<script src="${CONFIG.cdnBase}/alpine-guide-widget.min.js"></script>
<script>
const widget = new AlpineGuideWidget({
    territory: 'annecy',
    apiKey: 'your-api-key',
    position: 'bottom-right',
    theme: 'light',
    primaryColor: '#0066CC'
});
</script>
\`\`\`

## Options de configuration

| Option | Type | Défaut | Description |
|--------|------|--------|-------------|
| \`territory\` | string | 'annecy' | Territoire à utiliser |
| \`apiKey\` | string | '' | Clé API (obligatoire) |
| \`position\` | string | 'bottom-right' | Position du widget |
| \`theme\` | string | 'light' | Thème (light/dark/auto) |
| \`primaryColor\` | string | '#0066CC' | Couleur principale |
| \`autoOpen\` | boolean | false | Ouverture automatique |
| \`language\` | string | 'fr' | Langue par défaut |

## API JavaScript

### Méthodes publiques
- \`openWidget()\` : Ouvre le widget
- \`closeWidget()\` : Ferme le widget
- \`sendMessageProgrammatically(message)\` : Envoie un message
- \`clearHistory()\` : Efface l'historique
- \`getState()\` : Récupère l'état actuel
- \`destroy()\` : Détruit le widget

### Événements
- \`onReady\` : Widget initialisé
- \`onMessage\` : Nouveau message reçu
- \`onError\` : Erreur survenue

## Personnalisation CSS

Le widget utilise des variables CSS personnalisables :

\`\`\`css
:root {
  --alpine-primary: #0066CC;
  --alpine-primary-dark: #0052A3;
  --alpine-bg: #FFFFFF;
  --alpine-text: #1A1A1A;
}
\`\`\`

## Support

- Documentation : https://docs.alpine-guide.com
- Support : support@alpine-guide.com
- GitHub : https://github.com/alpine-guide/widget
`
  });
  
  return files;
}

/**
 * Génère les métadonnées
 */
function generateMetadata() {
  return {
    version: CONFIG.version,
    buildDate: new Date().toISOString(),
    apiBase: CONFIG.apiBase,
    cdnBase: CONFIG.cdnBase,
    files: {}
  };
}

/**
 * Calcule la taille d'un fichier
 */
function getFileSize(content) {
  const bytes = Buffer.byteLength(content, 'utf8');
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Fonction principale de build
 */
function build() {
  log('🚀 Démarrage du build Alpine Guide Widget', 'bright');
  info(`Version: ${CONFIG.version}`);
  info(`API Base: ${CONFIG.apiBase}`);
  info(`CDN Base: ${CONFIG.cdnBase}`);
  
  // Créer le dossier de sortie
  if (!fs.existsSync(CONFIG.outputDir)) {
    fs.mkdirSync(CONFIG.outputDir, { recursive: true });
    success(`Dossier de sortie créé: ${CONFIG.outputDir}`);
  }
  
  try {
    // Générer les variantes
    info('Génération des variantes du widget...');
    const variants = generateVariants();
    const metadata = generateMetadata();
    
    // Écrire les fichiers JavaScript
    variants.js.forEach(variant => {
      const filePath = path.join(CONFIG.outputDir, variant.name);
      fs.writeFileSync(filePath, variant.content);
      
      const size = getFileSize(variant.content);
      const tags = [
        variant.minified ? 'minifié' : 'dev',
        variant.embedded ? 'CSS intégré' : 'CSS externe'
      ].join(', ');
      
      success(`${variant.name} généré (${size}) - ${tags}`);
      
      metadata.files[variant.name] = {
        size: size,
        minified: variant.minified,
        embedded: variant.embedded
      };
    });
    
    // Écrire les fichiers CSS
    variants.css.forEach(variant => {
      const filePath = path.join(CONFIG.outputDir, variant.name);
      fs.writeFileSync(filePath, variant.content);
      
      const size = getFileSize(variant.content);
      const tags = variant.minified ? 'minifié' : 'dev';
      
      success(`${variant.name} généré (${size}) - ${tags}`);
      
      metadata.files[variant.name] = {
        size: size,
        minified: variant.minified
      };
    });
    
    // Générer les fichiers d'intégration
    info('Génération des fichiers d\'intégration...');
    const integrationFiles = generateIntegrationFiles();
    
    integrationFiles.forEach(file => {
      const filePath = path.join(CONFIG.outputDir, file.name);
      fs.writeFileSync(filePath, file.content);
      success(`${file.name} généré`);
    });
    
    // Écrire les métadonnées
    const metadataPath = path.join(CONFIG.outputDir, 'metadata.json');
    fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));
    success('metadata.json généré');
    
    // Résumé final
    log('\\n📦 Build terminé avec succès !', 'green');
    log('\\nFichiers générés:', 'bright');
    
    Object.entries(metadata.files).forEach(([filename, info]) => {
      log(`  • ${filename} (${info.size})`);
    });
    
    log('\\nUtilisation recommandée:', 'bright');
    log(`  Production: ${CONFIG.cdnBase}/alpine-guide-widget.min.js`, 'cyan');
    log(`  Développement: ${CONFIG.cdnBase}/alpine-guide-widget.js`, 'cyan');
    log(`  Version tout-en-un: ${CONFIG.cdnBase}/alpine-guide-widget.embed.min.js`, 'cyan');
    
  } catch (err) {
    error(`Erreur lors du build: ${err.message}`);
    console.error(err);
    process.exit(1);
  }
}

// Exécuter le build si appelé directement
if (require.main === module) {
  build();
}

module.exports = { build, CONFIG };