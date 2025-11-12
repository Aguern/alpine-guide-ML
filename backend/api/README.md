# TourismIQ API

API REST pour le scoring de POIs touristiques et la détection d'opportunités business.

## 🚀 Démarrage rapide

```bash
# Depuis le dossier tourism-iq/
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

L'API sera accessible à l'adresse: **http://localhost:8000**

Documentation interactive : **http://localhost:8000/docs**

## 📡 Endpoints disponibles

### 1. Health Check
```bash
GET /health
```
Vérifie l'état de l'API et du modèle ML.

**Exemple:**
```bash
curl http://localhost:8000/health
```

**Réponse:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "model_loaded": true,
  "data_loaded": true
}
```

---

### 2. Score POI
```bash
POST /score-poi
```
Score un POI touristique sur une échelle de 0 à 100.

**Exemple:**
```bash
curl -X POST http://localhost:8000/score-poi \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tour Eiffel",
    "type": "Monument",
    "description": "Monument emblematique de Paris",
    "latitude": 48.8584,
    "longitude": 2.2945,
    "has_contact": true,
    "has_images": true,
    "has_opening_hours": true
  }'
```

**Réponse:**
```json
{
  "quality_score": 88.9,
  "quality_level": "EXCELLENT",
  "confidence": 1.0,
  "features_analysis": {
    "completeness": 100.0,
    "richness": 23.8,
    "context": 5.0
  },
  "recommendations": [
    "Excellent POI ! Maintenir la qualité"
  ]
}
```

---

### 3. Opportunités Business
```bash
GET /opportunities?limit=10&min_score=30
```
Liste les opportunités business détectées par le Gap Detector.

**Paramètres:**
- `limit` (optionnel): Nombre max d'opportunités (défaut: 20)
- `min_score` (optionnel): Score minimum (défaut: 0)
- `level` (optionnel): Niveau (LOW/MEDIUM/HIGH)

**Exemple:**
```bash
curl "http://localhost:8000/opportunities?limit=5"
```

**Réponse:**
```json
{
  "total": 5,
  "opportunities": [
    {
      "zone": "Zone 44.4,1.4",
      "lat": 44.4,
      "lon": 1.4,
      "type_manquant": "PlaceOfInterest",
      "gap_pct": 9.6,
      "n_pois_zone": 225,
      "avg_quality_zone": 73.7,
      "opportunity_score": 32.7,
      "opportunity_level": "LOW",
      "raison": "Gap de 9.6% vs national"
    }
  ]
}
```

---

### 4. Analyse de Zone
```bash
POST /analyze-zone
```
Analyse une zone géographique autour d'un point.

**Exemple:**
```bash
curl -X POST http://localhost:8000/analyze-zone \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 48.8566,
    "longitude": 2.3522,
    "radius_km": 5.0
  }'
```

**Réponse:**
```json
{
  "center": {"lat": 48.8566, "lon": 2.3522},
  "radius_km": 5.0,
  "stats": {
    "n_pois": 364,
    "avg_quality": 81.1,
    "types_distribution": {
      "PlaceOfInterest": 104,
      "PointOfInterest": 88
    },
    "top_pois": [...]
  },
  "opportunities": []
}
```

---

### 5. Benchmark National
```bash
GET /benchmark
```
Retourne les statistiques nationales de référence.

**Exemple:**
```bash
curl http://localhost:8000/benchmark
```

**Réponse:**
```json
{
  "total_pois": 50000,
  "avg_quality_score": 69.3,
  "quality_distribution": {
    "LOW": 2,
    "MEDIUM": 15111,
    "GOOD": 23522,
    "EXCELLENT": 11365
  },
  "types_distribution": {
    "PointOfInterest": 23.7,
    "PlaceOfInterest": 18.5
  },
  "top_zones": [...]
}
```

## 🏗️ Architecture

```
api/
├── main.py       # Application FastAPI principale
├── models.py     # Modèles Pydantic
└── README.md     # Cette documentation
```

## 📊 Modèle ML

- **Algorithme**: Gradient Boosting Regressor (scikit-learn)
- **Performance**: R² = 0.9999, MAE = 0.07 points
- **Features**: 16 features (complétude, richesse, contexte, freshness)
- **Target**: Score de qualité 0-100

## 🔧 Stack Technique

- **Framework**: FastAPI 0.120.0
- **ML**: scikit-learn, joblib
- **Data**: pandas, numpy
- **Format**: Parquet (compression snappy)

## 📝 Notes

- L'API charge automatiquement le modèle ML et les données au démarrage
- Les endpoints sont documentés automatiquement via Swagger UI (/docs)
- CORS activé pour tous les domaines (dev uniquement)
