# TourismIQ Dashboard

Dashboard interactif Streamlit pour visualiser et analyser les données TourismIQ.

## 🚀 Démarrage

### Prérequis
- L'API FastAPI doit être lancée sur le port 8000
- Python 3.11+

### Lancement

```bash
# Depuis le dossier tourism-iq/
streamlit run dashboard/app.py
```

Le dashboard sera accessible à l'adresse: **http://localhost:8501**

## 📊 Pages Disponibles

### 1. Vue d'ensemble
**Statistiques nationales et KPIs**

- 📍 Total des POIs analysés
- ⭐ Score de qualité moyen
- 🌟 Distribution par niveau de qualité
- 📊 Top 10 types de POIs
- 🗺️ Carte des zones les plus denses

**Visualisations:**
- Graphique en barres de la distribution qualité (LOW/MEDIUM/GOOD/EXCELLENT)
- Diagramme en barres horizontal des types de POIs
- Carte interactive des top 10 zones

---

### 2. Scorer un POI
**Évaluez la qualité d'un point d'intérêt**

Formulaire interactif pour scorer un POI :
- Nom du POI (requis)
- Type de POI
- Description
- Coordonnées GPS (latitude/longitude)
- Informations supplémentaires :
  - Coordonnées de contact
  - Images disponibles
  - Horaires d'ouverture

**Résultats:**
- Score de qualité 0-100
- Niveau (LOW/MEDIUM/GOOD/EXCELLENT)
- Confiance de la prédiction
- Analyse détaillée (complétude, richesse, contexte)
- Recommandations d'amélioration

---

### 3. Opportunités Business
**Gaps de marché détectés**

- 🗺️ Carte interactive des opportunités
- 💡 Liste détaillée des gaps détectés
- 🎯 Filtres par score et nombre d'opportunités

**Informations par opportunité:**
- Type de POI manquant
- Zone géographique
- Gap en pourcentage vs national
- Score d'opportunité
- Nombre de POIs dans la zone
- Qualité moyenne de la zone

---

### 4. Analyse de Zone
**Analysez une zone géographique spécifique**

**Villes prédéfinies:**
- Paris, Marseille, Lyon, Toulouse, Nice, Bordeaux
- Ou coordonnées personnalisées

**Paramètres:**
- Latitude/Longitude
- Rayon d'analyse (1-50 km)

**Résultats:**
- Nombre de POIs dans la zone
- Qualité moyenne
- Opportunités détectées
- Distribution des types de POIs
- Top 5 POIs de la zone

---

## 🎨 Features

### Visualisations Interactives
- **Graphiques Plotly** : Graphiques interactifs avec zoom et sélection
- **Cartes géographiques** : Visualisation des POIs et opportunités sur carte
- **Métriques en temps réel** : KPIs dynamiques avec deltas

### Interface Utilisateur
- **Design moderne** : Interface clean avec CSS custom
- **Navigation intuitive** : Sidebar avec 4 pages principales
- **Responsive** : Layout adaptatif wide
- **Feedback utilisateur** : Spinners, messages d'erreur, confirmations

### Performance
- **Cache intelligent** : @st.cache_data pour optimiser les appels API
- **TTL 5 minutes** : Rafraîchissement automatique des données
- **Lazy loading** : Chargement à la demande

## 📡 Intégration API

Le dashboard consomme l'API TourismIQ via HTTP :

- `GET /health` - Health check
- `GET /benchmark` - Statistiques nationales
- `POST /score-poi` - Scorer un POI
- `GET /opportunities` - Liste des opportunités
- `POST /analyze-zone` - Analyser une zone

**URL API**: `http://localhost:8000`

## 🛠️ Stack Technique

- **Frontend**: Streamlit 1.50.0
- **Visualisation**: Plotly 6.3.1
- **HTTP**: requests
- **Data**: pandas

## 🎯 Cas d'usage

### 1. Analyste Touristique
→ Utilise la vue d'ensemble pour comprendre les tendances nationales
→ Identifie les zones à fort potentiel via les opportunités

### 2. Propriétaire de POI
→ Utilise le scorer pour évaluer la qualité de son POI
→ Applique les recommandations pour améliorer son score

### 3. Investisseur
→ Utilise les opportunités pour identifier les gaps de marché
→ Analyse des zones spécifiques pour valider le potentiel

### 4. Office de Tourisme
→ Analyse sa zone géographique
→ Identifie les types de POIs manquants dans son territoire

## 📝 Notes

- Le dashboard requiert une connexion à l'API FastAPI
- Les données sont mises en cache pendant 5 minutes
- La carte utilise OpenStreetMap (pas de clé API requise)
- Toutes les visualisations sont exportables en PNG

## 🐛 Troubleshooting

**Erreur "API non disponible"**
→ Vérifier que l'API FastAPI tourne sur http://localhost:8000

**Carte ne s'affiche pas**
→ Vérifier la connexion internet (OpenStreetMap)

**Données obsolètes**
→ Forcer le rafraîchissement : `Ctrl + R` ou attendre le TTL (5 min)

## 🚀 Améliorations futures

- [ ] Export des graphiques en PDF
- [ ] Filtres avancés sur la vue d'ensemble
- [ ] Comparaison de plusieurs zones
- [ ] Mode dark/light
- [ ] Authentification utilisateur
- [ ] Sauvegarde des analyses
