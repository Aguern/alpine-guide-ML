#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TourismIQ Dashboard - Streamlit Application

Dashboard interactif pour visualiser les données TourismIQ
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional

# Configuration de la page
st.set_page_config(
    page_title="TourismIQ Dashboard",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration API
API_URL = "http://localhost:8000"

# Style CSS custom
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #555;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stAlert {
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

@st.cache_data(ttl=300)
def get_health():
    """Vérifie l'état de l'API"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}


@st.cache_data(ttl=300)
def get_benchmark():
    """Récupère les statistiques nationales"""
    try:
        response = requests.get(f"{API_URL}/benchmark", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de la récupération du benchmark: {e}")
        return None


def score_poi(poi_data: dict):
    """Score un POI via l'API"""
    try:
        response = requests.post(f"{API_URL}/score-poi", json=poi_data, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors du scoring: {e}")
        return None


@st.cache_data(ttl=300)
def get_opportunities(limit: int = 50, min_score: float = 0):
    """Récupère les opportunités business"""
    try:
        response = requests.get(
            f"{API_URL}/opportunities",
            params={"limit": limit, "min_score": min_score},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de la récupération des opportunités: {e}")
        return None


def analyze_zone(lat: float, lon: float, radius_km: float):
    """Analyse une zone géographique"""
    try:
        response = requests.post(
            f"{API_URL}/analyze-zone",
            json={"latitude": lat, "longitude": lon, "radius_km": radius_km},
            timeout=15
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de l'analyse de zone: {e}")
        return None


# ============================================================================
# SIDEBAR
# ============================================================================

st.sidebar.markdown("# 🗺️ TourismIQ")
st.sidebar.markdown("### Intelligence Touristique")

# Health check
health = get_health()
if health.get("status") == "healthy":
    st.sidebar.success("✅ API opérationnelle")
else:
    st.sidebar.error("❌ API non disponible")
    st.sidebar.info("Lancer l'API: `python3 -m uvicorn api.main:app --port 8000`")

st.sidebar.markdown("---")

# Navigation
page = st.sidebar.radio(
    "Navigation",
    ["📊 Vue d'ensemble", "🎯 Scorer un POI", "💡 Opportunités", "🗺️ Analyse de zone"]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### À propos")
st.sidebar.info(
    "TourismIQ utilise le Machine Learning pour scorer la qualité des POIs "
    "touristiques et identifier les opportunités business."
)

# ============================================================================
# PAGE 1: VUE D'ENSEMBLE
# ============================================================================

if page == "📊 Vue d'ensemble":
    st.markdown('<div class="main-header">📊 TourismIQ Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Vue d\'ensemble des données touristiques</div>', unsafe_allow_html=True)

    # Récupérer les données
    benchmark = get_benchmark()

    if benchmark:
        # Métriques principales
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="📍 Total POIs",
                value=f"{benchmark['total_pois']:,}".replace(',', ' ')
            )

        with col2:
            st.metric(
                label="⭐ Score Moyen",
                value=f"{benchmark['avg_quality_score']}/100"
            )

        with col3:
            excellent = benchmark['quality_distribution']['EXCELLENT']
            pct = (excellent / benchmark['total_pois'] * 100)
            st.metric(
                label="🌟 Excellents",
                value=f"{excellent:,}".replace(',', ' '),
                delta=f"{pct:.1f}%"
            )

        with col4:
            low = benchmark['quality_distribution']['LOW']
            st.metric(
                label="⚠️ Faibles",
                value=f"{low:,}".replace(',', ' ')
            )

        st.markdown("---")

        # Graphiques
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Distribution de la Qualité")

            quality_dist = benchmark['quality_distribution']
            df_quality = pd.DataFrame({
                'Niveau': list(quality_dist.keys()),
                'Nombre': list(quality_dist.values())
            })

            # Ordre des niveaux
            order = ['LOW', 'MEDIUM', 'GOOD', 'EXCELLENT']
            df_quality['Niveau'] = pd.Categorical(df_quality['Niveau'], categories=order, ordered=True)
            df_quality = df_quality.sort_values('Niveau')

            # Couleurs
            colors = {'LOW': '#ff4444', 'MEDIUM': '#ffaa00', 'GOOD': '#88cc00', 'EXCELLENT': '#00cc44'}
            df_quality['Couleur'] = df_quality['Niveau'].map(colors)

            fig = px.bar(
                df_quality,
                x='Niveau',
                y='Nombre',
                color='Niveau',
                color_discrete_map=colors,
                text='Nombre'
            )
            fig.update_traces(texttemplate='%{text:,}', textposition='outside')
            fig.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Top 10 Types de POIs")

            types_dist = benchmark['types_distribution']
            df_types = pd.DataFrame({
                'Type': list(types_dist.keys()),
                'Pourcentage': list(types_dist.values())
            }).head(10)

            fig = px.bar(
                df_types,
                x='Pourcentage',
                y='Type',
                orientation='h',
                text='Pourcentage'
            )
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

        # Carte des zones
        st.markdown("---")
        st.subheader("🗺️ Top 10 Zones les Plus Denses")

        top_zones = benchmark['top_zones']
        df_zones = pd.DataFrame(top_zones)

        fig = px.scatter_mapbox(
            df_zones,
            lat='lat',
            lon='lon',
            size='n_pois',
            color='n_pois',
            hover_name='n_pois',
            hover_data={'lat': True, 'lon': True, 'n_pois': True},
            color_continuous_scale='Viridis',
            size_max=30,
            zoom=5
        )
        fig.update_layout(
            mapbox_style="open-street-map",
            height=500,
            margin={"r": 0, "t": 0, "l": 0, "b": 0}
        )
        st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# PAGE 2: SCORER UN POI
# ============================================================================

elif page == "🎯 Scorer un POI":
    st.markdown('<div class="main-header">🎯 Scorer un POI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Évaluez la qualité d\'un point d\'intérêt touristique</div>', unsafe_allow_html=True)

    st.markdown("---")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Informations du POI")

        # Formulaire
        with st.form("poi_form"):
            name = st.text_input("Nom du POI *", placeholder="Ex: Tour Eiffel")
            poi_type = st.text_input("Type de POI", placeholder="Ex: Monument, Restaurant, Hôtel")

            description = st.text_area(
                "Description",
                placeholder="Décrivez le POI en quelques phrases...",
                height=100
            )

            col_a, col_b = st.columns(2)
            with col_a:
                latitude = st.number_input("Latitude", value=48.8566, format="%.4f")
            with col_b:
                longitude = st.number_input("Longitude", value=2.3522, format="%.4f")

            st.markdown("**Informations supplémentaires**")
            col_c, col_d, col_e = st.columns(3)
            with col_c:
                has_contact = st.checkbox("Coordonnées de contact", value=True)
            with col_d:
                has_images = st.checkbox("Images disponibles", value=True)
            with col_e:
                has_opening_hours = st.checkbox("Horaires d'ouverture", value=False)

            submitted = st.form_submit_button("🎯 Calculer le Score", type="primary")

        if submitted:
            if not name:
                st.error("⚠️ Le nom du POI est obligatoire")
            else:
                # Préparer les données
                poi_data = {
                    "name": name,
                    "type": poi_type if poi_type else None,
                    "description": description if description else None,
                    "latitude": latitude,
                    "longitude": longitude,
                    "has_contact": has_contact,
                    "has_images": has_images,
                    "has_opening_hours": has_opening_hours
                }

                # Scorer le POI
                with st.spinner("Calcul du score en cours..."):
                    result = score_poi(poi_data)

                if result:
                    st.session_state['last_score'] = result

    with col2:
        st.subheader("Résultats")

        if 'last_score' in st.session_state:
            result = st.session_state['last_score']

            # Score principal
            score = result['quality_score']
            level = result['quality_level']

            # Couleur selon le niveau
            color_map = {
                'EXCELLENT': '#00cc44',
                'GOOD': '#88cc00',
                'MEDIUM': '#ffaa00',
                'LOW': '#ff4444'
            }
            color = color_map.get(level, '#888')

            st.markdown(f"""
            <div style="background-color: {color}; padding: 2rem; border-radius: 1rem; text-align: center; margin-bottom: 1rem;">
                <div style="font-size: 3rem; font-weight: bold; color: white;">{score}</div>
                <div style="font-size: 1.5rem; color: white;">{level}</div>
            </div>
            """, unsafe_allow_html=True)

            # Confiance
            confidence = result['confidence'] * 100
            st.metric("Confiance", f"{confidence:.0f}%")

            st.markdown("---")

            # Analyse des features
            st.subheader("Analyse Détaillée")
            features = result['features_analysis']

            st.metric("Complétude", f"{features['completeness']:.1f}/100")
            st.progress(features['completeness'] / 100)

            st.metric("Richesse", f"{features['richness']:.1f}/100")
            st.progress(features['richness'] / 100)

            st.metric("Contexte", f"{features['context']:.1f}/100")
            st.progress(features['context'] / 100)

            st.markdown("---")

            # Recommandations
            st.subheader("💡 Recommandations")
            for rec in result['recommendations']:
                st.info(rec)


# ============================================================================
# PAGE 3: OPPORTUNITÉS
# ============================================================================

elif page == "💡 Opportunités":
    st.markdown('<div class="main-header">💡 Opportunités Business</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Gaps de marché détectés par l\'algorithme</div>', unsafe_allow_html=True)

    st.markdown("---")

    # Filtres
    col1, col2 = st.columns([1, 3])

    with col1:
        limit = st.slider("Nombre d'opportunités", 5, 50, 20)
        min_score = st.slider("Score minimum", 0, 100, 0)

    # Récupérer les opportunités
    opps_data = get_opportunities(limit=limit, min_score=min_score)

    if opps_data:
        opportunities = opps_data['opportunities']

        if len(opportunities) == 0:
            st.warning("Aucune opportunité trouvée avec ces critères")
        else:
            # Carte des opportunités
            df_opps = pd.DataFrame(opportunities)

            fig = px.scatter_mapbox(
                df_opps,
                lat='lat',
                lon='lon',
                size='gap_pct',
                color='opportunity_score',
                hover_name='type_manquant',
                hover_data={
                    'zone': True,
                    'gap_pct': ':.1f',
                    'n_pois_zone': True,
                    'opportunity_score': ':.1f'
                },
                color_continuous_scale='RdYlGn',
                size_max=20,
                zoom=5
            )
            fig.update_layout(
                mapbox_style="open-street-map",
                height=500,
                margin={"r": 0, "t": 0, "l": 0, "b": 0}
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")

            # Tableau des opportunités
            st.subheader(f"📋 Top {len(opportunities)} Opportunités")

            for i, opp in enumerate(opportunities[:10], 1):
                with st.expander(f"#{i} - {opp['type_manquant']} - {opp['zone']}"):
                    col_a, col_b, col_c = st.columns(3)

                    with col_a:
                        st.metric("Score d'opportunité", f"{opp['opportunity_score']:.1f}/100")
                        st.metric("Gap détecté", f"{opp['gap_pct']:.1f}%")

                    with col_b:
                        st.metric("POIs dans la zone", opp['n_pois_zone'])
                        st.metric("Qualité moyenne zone", f"{opp['avg_quality_zone']:.1f}/100")

                    with col_c:
                        st.info(f"**Raison:** {opp['raison']}")
                        st.info(f"**Niveau:** {opp['opportunity_level']}")


# ============================================================================
# PAGE 4: ANALYSE DE ZONE
# ============================================================================

elif page == "🗺️ Analyse de zone":
    st.markdown('<div class="main-header">🗺️ Analyse de Zone</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Analysez une zone géographique spécifique</div>', unsafe_allow_html=True)

    st.markdown("---")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Paramètres")

        # Villes prédéfinies
        cities = {
            "Paris": (48.8566, 2.3522),
            "Marseille": (43.2965, 5.3698),
            "Lyon": (45.7640, 4.8357),
            "Toulouse": (43.6047, 1.4442),
            "Nice": (43.7102, 7.2620),
            "Bordeaux": (44.8378, -0.5792),
            "Personnalisé": None
        }

        city = st.selectbox("Ville", list(cities.keys()))

        if cities[city] is not None:
            default_lat, default_lon = cities[city]
        else:
            default_lat, default_lon = 48.8566, 2.3522

        latitude = st.number_input("Latitude", value=default_lat, format="%.4f")
        longitude = st.number_input("Longitude", value=default_lon, format="%.4f")
        radius_km = st.slider("Rayon d'analyse (km)", 1, 50, 10)

        analyze_btn = st.button("🔍 Analyser la zone", type="primary")

    with col2:
        if analyze_btn:
            with st.spinner("Analyse en cours..."):
                result = analyze_zone(latitude, longitude, radius_km)

            if result:
                st.session_state['zone_analysis'] = result

        if 'zone_analysis' in st.session_state:
            result = st.session_state['zone_analysis']
            stats = result['stats']

            # Métriques
            st.subheader("📊 Statistiques de la zone")

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("POIs", stats['n_pois'])
            with col_b:
                st.metric("Qualité moyenne", f"{stats['avg_quality']:.1f}/100")
            with col_c:
                opps_count = len(result['opportunities'])
                st.metric("Opportunités", opps_count)

            st.markdown("---")

            # Distribution des types
            st.subheader("Distribution des Types")
            df_types = pd.DataFrame({
                'Type': list(stats['types_distribution'].keys()),
                'Nombre': list(stats['types_distribution'].values())
            }).head(10)

            fig = px.pie(df_types, values='Nombre', names='Type', hole=0.4)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

            # Top POIs
            if stats['top_pois']:
                st.markdown("---")
                st.subheader("🌟 Top 5 POIs de la zone")

                for i, poi in enumerate(stats['top_pois'], 1):
                    col_x, col_y = st.columns([3, 1])
                    with col_x:
                        st.markdown(f"**{i}. {poi['name']}**")
                        st.caption(f"{poi['type']}")
                    with col_y:
                        st.metric("Score", f"{poi['quality_score']:.1f}")

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #888; padding: 1rem;">
        TourismIQ Dashboard v1.0 | Powered by FastAPI + Streamlit + ML
    </div>
    """,
    unsafe_allow_html=True
)
