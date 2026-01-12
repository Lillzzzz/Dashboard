"""
SPOTIFY A&R Business Intelligence Dashboard
Hinweise:
- zentrale Konfiguration via config.json
- robustes API-Fallback (safe_fetch_spotify)
- Caching für CSV-Daten (lru_cache)
- Filtertransparenz durch Year-Badge
- Vergleichbarkeit durch fixierte Y-Achse
"""


import dash
from dash import dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from pathlib import Path
import requests
import base64
import io
import sys
import os
from dotenv import load_dotenv
import json
import logging
from functools import lru_cache
from datetime import datetime

SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
LASTFM_API_KEY = os.getenv('LASTFM_API_KEY')

# Orjson-Kompatibilität (Plotly Performance-Bibliothek)

import plotly.io._json as pio_json
try:
    import orjson
except Exception:
    pio_json.orjson = None

logging.basicConfig(level=logging.INFO)

load_dotenv()

# CSV von GitHub Release laden falls lokal nicht vorhanden

csv_path = Path('data/spotify_charts_enhanced.csv')
if not csv_path.exists():
    print("Lade spotify_charts_enhanced.csv von GitHub Release...")
    try:
        url = "https://github.com/Lillzzzz/Dashboard/releases/download/v1.0/spotify_charts_enhanced.csv"
        response = requests.get(url, timeout=300)
        response.raise_for_status()
        csv_path.parent.mkdir(exist_ok=True)
        csv_path.write_bytes(response.content)
        print("✅ spotify_charts_enhanced.csv von GitHub Release geladen!")
    except Exception as e:
        print(f"⚠️ Download fehlgeschlagen: {e}")

# Caching für CSV-Daten (beschleunigt Ladevorgänge)

@lru_cache(maxsize=8)
def get_kpi_data():
    return pd.read_csv("data/cleaned_charts_kpi.csv")

@lru_cache(maxsize=8)
def get_enhanced_data():
    return enhanced_df

@lru_cache(maxsize=8)
def get_highpot_data():
    return highpot_df

def clear_cache():
    get_kpi_data.cache_clear()
    get_enhanced_data.cache_clear()
    get_highpot_data.cache_clear()

# Genre-Mapping aus JSON laden
DATA_DIR = Path("data")
genre_mapping_path = DATA_DIR / "genre_mapping.json"
if genre_mapping_path.exists():
    with open(genre_mapping_path, "r", encoding="utf-8") as f:
        GENRE_MAPPING_DASH = json.load(f)
else:
    GENRE_MAPPING_DASH = {}


# Konstanten für Last.fm Gewichtung
# Last.fm Gewichtung: Last.fm-Tracks werden höher gewichtet, da sie auf
# echten Nutzer-Plays (7 Tage) basieren und nicht algorithmus-gesteuert sind.
# Validiert Spotify-Trends gegen Plattform-Bias.
LASTFM_WEIGHT = 1.2  # Last.fm-Tracks höher gewichten: 
                         # Basiert auf echten Nutzer-Plays (7 Tage),
                         # nicht algorithmus-gesteuert. Stabilisiert Trends.

# Rate-Limit Handling
RATE_LIMIT_WAIT = 60  # Sekunden bei 429-Error (erhöht auf 60s)

# Startup: Prüfe ob alle Dateien vorhanden sind

print("\n" + "="*70)
print("SPOTIFY A&R DASHBOARD - STARTUP")
print("="*70)

data_path = Path('./data')

if not data_path.exists():
    print("WARNUNG: './data' Ordner nicht gefunden!")

required_files = {
    'cleaned_charts_kpi.csv': 'KPI-Metriken',
    'spotify_charts_enhanced.csv': 'Audio Features',
    'high_potential_tracks.csv': 'High-Potential Tracks'
}

missing_files = []
for filename, description in required_files.items():
    filepath = data_path / filename
    if not filepath.exists():
        missing_files.append(f"   {filename} ({description})")
    else:
        print(f"   {filename}")

if missing_files:
    print("\nWARNUNG: Folgende CSV-Dateien fehlen:")
    for file in missing_files:
        print(file)
    print("Dashboard startet ohne diese Daten.\n")

try:
    print("Lade Daten...")
    kpi_df = get_kpi_data()
    
    # Enhanced CSV mit reduziertem Memory-Footprint laden
    enhanced_df = pd.read_csv(
        data_path / 'spotify_charts_enhanced.csv',
        dtype={'title': 'category', 'artist': 'category', 'market': 'category', 'genre_harmonized': 'category'},
        low_memory=True
    )
    
    highpot_df = pd.read_csv(data_path / 'high_potential_tracks.csv')
    
    # Market Trends CSV einbinden (falls vorhanden)
    market_trends_path = data_path / 'cleaned_market_trends.csv'
    if market_trends_path.exists():
        market_trends_df = pd.read_csv(market_trends_path)
        print(f"   cleaned_market_trends.csv")
    else:
        market_trends_df = None
        print("   cleaned_market_trends.csv (nicht gefunden, nutze Fallback)")
    
    print(f"\nDATEN GELADEN:")
    print(f"   KPI: {len(kpi_df)} Zeilen")
    print(f"   Enhanced: {len(enhanced_df)} Zeilen")
    print(f"   High-Potential: {len(highpot_df)} Zeilen")
    if market_trends_df is not None:
        print(f"   Market Trends: {len(market_trends_df)} Zeilen")
    
except Exception as e:
    print(f"\nWARNUNG beim Laden der Daten: {str(e)}")
    print("Dashboard startet mit eingeschränkter Funktionalität.\n")


print("="*70)

# Last.fm API-Klasse

import time
from datetime import datetime, timedelta

# Last.fm Country Mapping
LASTFM_COUNTRY_MAP = {
    'DE': 'germany',
    'UK': 'united kingdom', 
    'BR': 'brazil',
    'US': 'united states',
    'FR': 'france',
    'ES': 'spain',
    'IT': 'italy',
    'JP': 'japan'
}

class LastFmAPI:
    def __init__(self):
        self.api_key = LASTFM_API_KEY
        self.base_url = "http://ws.audioscrobbler.com/2.0/"
        self.status = "Verbindung wird hergestellt..."
        self.cache = {}
        self.cache_duration = timedelta(minutes=15)  # 15min cache
        
        if self.api_key:
            # Test-Call um Status zu verifizieren
            test = self._test_connection()
            if test:
                self.status = "Verbunden"
                print("Last.fm API verbunden")
            else:
                self.status = "Verbindung fehlgeschlagen"
                print("Last.fm API nicht verfügbar")
        else:
            self.status = "API Key fehlt (.env)"
            print("LASTFM_API_KEY nicht in .env gefunden")
    
    def _test_connection(self):
        """Test ob API erreichbar ist"""
        try:
            params = {
                'method': 'geo.getTopTracks',
                'country': 'germany',
                'api_key': self.api_key,
                'format': 'json',
                'limit': 1
            }
            resp = requests.get(self.base_url, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return 'error' not in data
            return False
        except:
            return False
    
    def _get_cache_key(self, country, limit):
        """Cache-Key mit 15min Zeitslot"""
        now = datetime.utcnow()
        timeslot = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        return f"{country}_{limit}_{timeslot.isoformat()}"
    
    def get_top_tracks(self, country, limit=15):
        """
        Last.fm Top Tracks mit:
        - 15min Caching
        - Retry bei 429/5xx
        - Error logging
        """
        if not self.api_key:
            return []
        
        # Cache check
        cache_key = self._get_cache_key(country, limit)
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if datetime.utcnow() - cached_time < self.cache_duration:
                return cached_data
        
        params = {
            'method': 'geo.getTopTracks',
            'country': country,
            'api_key': self.api_key,
            'format': 'json',
            'limit': limit
        }
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                resp = requests.get(self.base_url, params=params, timeout=10)
                
                # Rate Limit (429)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get('Retry-After', 30))
                    print(f"Last.fm Rate Limit ({country}), warte {retry_after}s...")
                    if attempt < max_retries - 1:
                        time.sleep(retry_after)
                        continue
                    else:
                        print(f"Last.fm Rate Limit überschritten ({country})")
                        return []
                
                # Server Error (5xx)
                if 500 <= resp.status_code < 600:
                    print(f"Last.fm Server Error {resp.status_code} ({country})")
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    else:
                        return []
                
                # Success
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # API Error in Response Body
                    if 'error' in data:
                        error_code = data.get('error', 'unknown')
                        error_msg = data.get('message', 'No message')
                        print(f"Last.fm API Error ({country}): Code {error_code} - {error_msg}")
                        return []
                    
                    tracks = data.get('tracks', {}).get('track', [])
                    if not tracks:
                        return []
                    
                    # Format tracks
                    result = []
                    for t in tracks:
                        result.append({
                            'name': t.get('name', ''),
                            'artist': t.get('artist', {}).get('name', '') if isinstance(t.get('artist'), dict) else str(t.get('artist', '')),
                            'playcount': int(t.get('playcount', 0)),
                            'weight': LASTFM_WEIGHT
                        })
                    
                    # Cache result
                    self.cache[cache_key] = (result, datetime.utcnow())
                    return result
                
                # Other error
                print(f"Last.fm error ({country}): Status {resp.status_code}")
                try:
                    print(f"Response: {resp.text[:300]}")
                except:
                    pass
                return []
                
            except requests.Timeout:
                print(f"Last.fm Timeout ({country}), Versuch {attempt+1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return []
            except Exception as e:
                print(f"Last.fm Fehler ({country}): {e}")
                return []
        
        return []

# Initialize Last.fm API
lastfm_api = LastFmAPI()

def get_lastfm_toptracks(country, limit=15):
    """Wrapper für Kompatibilität"""
    return lastfm_api.get_top_tracks(country, limit)



# Spotify API-Klasse

class SpotifyAPI:
    def __init__(self):
        self.client_id = SPOTIFY_CLIENT_ID
        self.client_secret = SPOTIFY_CLIENT_SECRET
        self.token = None
        self.token_expiry = 0
        self.status = "Verbindung wird hergestellt..."
        
        if self.client_id and self.client_secret:
            self.token = self._get_token()
            if self.token:
                self.status = "Verbunden"
                print("Spotify API verbunden")
            else:
                self.status = "Verbindung fehlgeschlagen"
                print("Spotify API nicht verfügbar")
        else:
            self.status = "Credentials fehlen (.env)"
            print("SPOTIFY_CLIENT_ID/SECRET nicht in .env gefunden")
    
    def _get_token(self):
        """Token holen und Expiry setzen"""
        import time
        try:
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_bytes = auth_string.encode('utf-8')
            auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')
            
            url = "https://accounts.spotify.com/api/token"
            headers = {
                'Authorization': f'Basic {auth_base64}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            data = {'grant_type': 'client_credentials'}
            
            response = requests.post(url, headers=headers, data=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                self.token_expiry = time.time() + result.get('expires_in', 3600) - 300
                print(f"Token erneuert (gültig ~{result.get('expires_in', 3600)//60} min)")
                return result['access_token']
            return None
        except Exception as e:
            print(f"Token-Fehler: {e}")
            return None
    
    def _ensure_token(self):
        """Prueft Token und erneuert wenn noetig"""
        import time
        if not self.token or time.time() >= self.token_expiry:
            print("Token abgelaufen, erneuere...")
            self.token = self._get_token()
            return self.token is not None
        return True
    
    def get_featured_tracks(self, market='DE', limit=10):
        """Holt neue Tracks je nach Markt"""
        if not self._ensure_token():
            return []
        
        try:
            headers = {'Authorization': f'Bearer {self.token}'}
            
            market_codes = {
                'DE': 'DE',
                'UK': 'GB',
                'BR': 'BR'
            }
            
            api_market = market_codes.get(market, 'DE')
            
            # Query-Strategie: 2024-2025 für aktuelle Charts-Relevanz
            # Defensiv genug um immer Daten zu bekommen
            url = f"https://api.spotify.com/v1/search?q=year:2024-2025&type=track&market={api_market}&limit={limit}"
            response = requests.get(url, headers=headers, timeout=10)
            
            # Fallback nur dann, wenn die erste Antwort zwar ok war, aber keine Items hatte
            if response.status_code == 200 and len(response.json().get('tracks', {}).get('items', [])) == 0:
                url = f"https://api.spotify.com/v1/search?q=year:2024&type=track&market={api_market}&limit={limit}"
                response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 401:
                self.token = self._get_token()
                if self.token:
                    headers = {'Authorization': f'Bearer {self.token}'}
                    response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 429:
                import time
                retry_after = int(response.headers.get('Retry-After', RATE_LIMIT_WAIT))
                time.sleep(retry_after)
                return self.get_featured_tracks(market, limit)
            
            if response.status_code != 200:
                print(f"API Error {api_market}: Status {response.status_code}")
                return []
            
            tracks = []
            for track in response.json().get('tracks', {}).get('items', [])[:limit]:
                album_image = None
                if track.get('album', {}).get('images'):
                    album_image = track['album']['images'][0]['url']
                
                tracks.append({
                    'name': track.get('name', 'Unbekannt'),
                    'artist': ', '.join([a['name'] for a in track.get('artists', [])]),
                    'popularity': track.get('popularity', 0),
                    'market': market,
                    'image': album_image,
                    'source': 'spotify'
                })
            
            return tracks
        except Exception as e:
            print(f"API Fehler fuer {market}: {e}")
            return []

spotify_api = SpotifyAPI()

# Fallback wenn Spotify API nicht erreichbar

def safe_fetch_spotify():
    """Wrapper mit Fallback für Spotify API"""
    try:
        data = spotify_api.get_featured_tracks()
        logging.info("Spotify API data fetched successfully.")
        return data
    except Exception as e:
        logging.warning(f"Spotify API failed: {e}")
        return [
            {"name": "Fallback Track 1", "artist": "Lokale Daten", "popularity": 0, "market": "DE", "image": None, "source": "fallback"},
            {"name": "Fallback Track 2", "artist": "Lokale Daten", "popularity": 0, "market": "UK", "image": None, "source": "fallback"},
            {"name": "Fallback Track 3", "artist": "Lokale Daten", "popularity": 0, "market": "BR", "image": None, "source": "fallback"}
        ]


# Dash App initialisieren

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)
app.title = "Spotify A&R Intelligence"

# Server-Variable für Deployment (z.B. Render.com)
server = app.server


def hex_to_rgba(hex_color, alpha=0.15):
    """Konvertiert HEX zu RGBA, falls kaputt Standard"""
    try:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return f'rgba({r}, {g}, {b}, {alpha})'
        return 'rgba(29, 185, 84, 0.15)'  # Fallback Spotify-Grün
    except:
        return 'rgba(29, 185, 84, 0.15)'

# Helper-Funktionen für Plotly Theme

def create_plotly_theme():
    return dict(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(15,20,30,0.9)',
        font=dict(family='Inter', color='#FFFFFF', size=12),
        margin=dict(l=60, r=60, t=80, b=60),
        hovermode='closest',
        hoverlabel=dict(bgcolor='rgba(29, 185, 84, 0.95)', font_size=13),
        xaxis=dict(gridcolor='rgba(29,185,84,0.15)', showgrid=True),
        yaxis=dict(gridcolor='rgba(29,185,84,0.15)', showgrid=True)
    )

def get_market_label(markets):
    if not markets or set(markets) == {'DE', 'UK', 'BR'}:
        return "Alle Märkte"
    labels = {'DE': 'Deutschland', 'UK': 'UK', 'BR': 'Brasilien'}
    return " + ".join([labels.get(m, m) for m in sorted(markets)])

def get_market_colors():
    return {
        'DE': '#1DB954',
        'UK': '#FF6B6B',
        'BR': '#4ECDC4'
    }

def get_pill_style(pill_type='default'):
    """Einheitliche Pill-Styles für alle Status-Pills"""
    base_style = {
        'fontSize': '11px',
        'fontWeight': '600',
        'padding': '6px 12px',
        'borderRadius': '20px',
        'whiteSpace': 'nowrap'
    }
    if pill_type == 'booming':
        return {**base_style, 'background': 'rgba(78, 205, 196, 0.2)', 'color': '#4ECDC4', 'border': '1px solid #4ECDC4'}
    elif pill_type == 'declining':
        return {**base_style, 'background': 'rgba(255, 107, 157, 0.2)', 'color': '#FF6B9D', 'border': '1px solid #FF6B9D'}
    elif pill_type == 'neutral':
        return {**base_style, 'background': 'rgba(127, 127, 127, 0.2)', 'color': '#7F8C8D', 'border': '1px solid #7F8C8D'}
    else:
        return {**base_style, 'background': 'rgba(20, 25, 40, 0.9)', 'color': '#B3B3B3', 'border': '1px solid rgba(29, 185, 84, 0.3)'}

# Einheitliche Badge-Styles für Live-Karten
def get_live_badge_style(badge_type='connected'):
    """Einheitliche Badge-Styles für Verbunden und Markt-Badges"""
    base_style = {
        'fontSize': '11px',
        'fontWeight': '600',
        'padding': '4px 10px',
        'borderRadius': '12px',
        'whiteSpace': 'nowrap'
    }
    if badge_type == 'connected':
        return {**base_style, 'marginRight': '6px'}
    else:  # market badge
        return base_style

def get_accessible_colors():
    """Farbenblindenfreundliche Farbpalette (Wong 2011) - für zukünftige Nutzung"""
    return {
        'orange': '#E69F00',
        'sky_blue': '#56B4E9',
        'bluish_green': '#009E73',
        'yellow': '#F0E442',
        'blue': '#0072B2',
        'vermillion': '#D55E00',
        'reddish_purple': '#CC79A7',
        'black': '#000000'
    }

# Custom CSS in HTML Head einfügen

app.index_string = f'''
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        {{%css%}}
        <style>
.dark-dropdown .Select-control {{
    background-color: #1e1e1e !important;
    border: 1px solid #1db954 !important;
    color: #1db954 !important;
}}
.dark-dropdown .Select-value-label,
.dark-dropdown .Select-placeholder {{
    color: #1db954 !important;
}}
.dark-dropdown .Select-menu-outer {{
    background-color: #1e1e1e !important;
    border: 1px solid #1db954 !important;
    z-index: 9999 !important;
}}
.dark-dropdown .VirtualizedSelectOption {{
    background-color: #1e1e1e !important;
    color: #ffffff !important;
}}
.dark-dropdown .VirtualizedSelectFocusedOption {{
    background-color: #1db954 !important;
    color: #0f141e !important;
}}
@media (max-width: 768px) {{
    .market-badge {{
        flex-wrap: wrap;
        max-width: 100%;
        margin-bottom: 4px;
    }}
    .chart-header {{
        gap: 6px;
        flex-direction: column;
        align-items: flex-start !important;
    }}
    .sidebar {{
        display: none;
    }}
    .main-content {{
        padding: 10px !important;
    }}
}}
        </style>
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>
'''

# Layout-Definition

app.layout = dbc.Container([
    dbc.Row([
        # SIDEBAR
        dbc.Col([
            html.Div([
                html.Div([
                    html.Div([
                        
                        html.Div([
                            html.H3("SPOTIFY", style={
                                'color': '#1DB954',
                                'marginBottom': '2px',
                                'fontWeight': '900',
                                'fontSize': '26px',
                                'letterSpacing': '2px'
                            }),
                            html.Div(style={
                                'width': '60px',
                                'height': '3px',
                                'background': 'linear-gradient(90deg, #1DB954 0%, transparent 100%)',
                                'marginBottom': '10px',
                                'borderRadius': '2px'
                            }),
                            html.P("A&R Intelligence", style={
                                'color': '#7F8C8D',
                                'fontSize': '12px',
                                'marginBottom': '8px',
                                'fontWeight': '500',
                                'letterSpacing': '0.5px'
                            }),
                            html.P("Marktanalyse für datenbasierte Artist & Repertoire-Entscheidungen. Analysiert Genre-Performance, Audio-Charakteristiken und High-Potential Tracks über Deutschland, UK und Brasilien.", style={
                                'color': '#5A6169',
                                'fontSize': '10px',
                                'fontStyle': 'italic',
                                'marginBottom': '0',
                                'lineHeight': '1.5'
                            })
                        ])
                    ], style={
                        'padding': '20px',
                        'background': 'linear-gradient(135deg, rgba(29, 185, 84, 0.08) 0%, rgba(15, 20, 30, 0.95) 100%)',
                        'borderRadius': '14px',
                        'border': '1px solid rgba(29, 185, 84, 0.25)',
                        'marginBottom': '24px',
                        'boxShadow': '0 4px 16px rgba(0, 0, 0, 0.3)'
                    })
                ]),
                
                html.Div([
                    html.H4("MARKT FILTER", className='filter-title'),
                    html.P([
                        "Wählen Sie einen einzelnen Markt, zwei Märkte im direkten Vergleich oder alle drei Märkte zusammen. ",
                        "So lassen sich regionale Unterschiede in Genre-Präferenzen, Audio-Features und Künstler-Performance ",
                        "gezielt analysieren und marktspezifische Trends identifizieren."
                    ], style={'fontSize': '11px', 'color': '#7F8C8D', 'marginBottom': '16px', 'lineHeight': '1.6'}),
                    
                    dbc.Button("ALLE MÄRKTE", id='btn-all', className='market-button', n_clicks=0),
                    dbc.Button("DEUTSCHLAND", id='btn-de', className='market-button', n_clicks=0),
                    dbc.Button("UK", id='btn-uk', className='market-button', n_clicks=0),
                    dbc.Button("BRASILIEN", id='btn-br', className='market-button', n_clicks=0),
                    
                    html.Div([
                        html.H4("JAHRES-FILTER (OPTIONAL)", className='filter-title', style={'marginTop': '20px'}),
                        dcc.Dropdown(
                            id="year-filter",
                            options=[
                                {"label": "Gesamter Zeitraum", "value": "ALL"}
                            ] + [{"label": str(y), "value": y} for y in [2017, 2018, 2019, 2020, 2021]],
                            value=None,
                            clearable=True,
                            placeholder="Jahr wählen (optional)",
                            className="dark-dropdown",
                            style={
                                "backgroundColor": "rgba(6, 8, 14, 0.9)",
                                "color": "#ffffff",
                                "border": "1px solid rgba(29, 185, 84, 0.35)",
                                "borderRadius": "6px",
                                "fontSize": "12px",
                                "zIndex": 9999
                            }
                        ),
                        html.P(
                            "Hinweis: Der Jahresfilter wirkt nur auf zeitabhängige Visualisierungen (z. B. Markt-Trends, Genre-Entwicklung).",
                            style={
                                'color': '#5A6169',
                                'fontSize': '10px',
                                'fontStyle': 'italic',
                                'marginTop': '8px',
                                'marginBottom': '0',
                                'lineHeight': '1.4'
                            }
                        )
                    ])
                ], className='filter-card'),
                
                html.Div([
                    html.H5([
                        html.Span("", style={
                            'color': '#1DB954',
                            'fontSize': '14px',
                            'marginRight': '8px',
                            'animation': 'blink 2s ease-in-out infinite'
                        }),
                        "API STATUS"
                    ], style={'color': '#1DB954', 'fontSize': '13px', 'marginBottom': '10px', 'fontWeight': '700'}),
                    html.P(id='api-status-text', style={'fontSize': '11px', 'color': '#B3B3B3'})
                ], style={
                    'padding': '14px',
                    'background': 'rgba(29,185,84,0.05)',
                    'borderRadius': '10px',
                    'border': '1px solid rgba(29,185,84,0.2)',
                    'marginTop': '20px'
                })
            ], className='sidebar')
        ], width=3, className='p-0'),
        
        # MAIN CONTENT
        dbc.Col([
            html.Div([
                # Header
                html.Div([
                    html.H1("SPOTIFY A&R MARKET INTELLIGENCE", className='header-title'),
                    html.P([
                        "Dieses Dashboard kombiniert historische Musikmarkt-Analysen (2017–2021) mit ",
                        "Live-Daten aus Spotify und Last.fm, um Markttrends, Erfolgsfaktoren und ",
                        "aktuelle Streaming-Bewegungen in Echtzeit zu visualisieren."
                    ], style={'fontSize': '13px', 'color': '#B3B3B3', 'fontStyle': 'italic', 'marginTop': '8px', 'lineHeight': '1.6'})
                ], className='header-section'),
                
                
                
               # MOBILE FILTER
                html.Div([
                    html.H4("FILTER", style={'color': '#1DB954', 'fontSize': '14px', 'fontWeight': '700', 'marginBottom': '12px'}),
                    
                    dcc.Dropdown(
                        id='market-dropdown-mobile',
                        options=[
                            {'label': 'Alle Märkte', 'value': 'ALL'},
                            {'label': 'Deutschland', 'value': 'DE'},
                            {'label': 'UK', 'value': 'UK'},
                            {'label': 'Brasilien', 'value': 'BR'}
                        ],
                        value='ALL',
                        clearable=False,
                        className="dark-dropdown",
                        style={
                            "backgroundColor": "rgba(6, 8, 14, 0.9)",
                            "marginBottom": "12px"
                        }
                    ),
                    
                    dcc.Dropdown(
                        id="year-dropdown-mobile",
                        options=[
                            {"label": "Alle Jahre", "value": "ALL"}
                        ] + [{"label": str(y), "value": y} for y in [2017, 2018, 2019, 2020, 2021]],
                        value="ALL",
                        clearable=False,
                        className="dark-dropdown",
                        style={
                            "backgroundColor": "rgba(6, 8, 14, 0.9)"
                        }
                    )
                ], className='d-block d-md-none', style={
                    'background': 'rgba(15,20,30,0.9)',
                    'border': '2px solid rgba(29,185,84,0.3)',
                    'borderRadius': '12px',
                    'padding': '16px',
                    'marginBottom': '16px'
                }),
                
                # KPI Row
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Div("SHANNON DIVERSITÄT", className='kpi-label'),
                            html.Div(id='kpi-shannon', className='kpi-value', title="Genrekonzentration, höher = vielfältiger Markt"),
                            html.Div([
                                "Misst Genre-Vielfalt. ",
                                html.Strong("Hohe Werte (>2.0)"), " = vielfältiger Markt mit vielen Genres. ",
                                html.Strong("Niedrige Werte (<1.5)"), " = konzentrierter Markt, wenige dominante Genres."
                            ], className='kpi-desc')
                        ], className='kpi-card')
                    ], xl=3, lg=6, md=6, sm=12, className='mb-4'),
                    dbc.Col([
                        html.Div([
                            html.Div("WACHSTUMS-MOMENTUM", className='kpi-label'),
                            html.Div(id='kpi-growth', className='kpi-value', title="Index relativ zu 2017, 100 = gleichbleibend"),
                            html.Div([
                                "Index für Marktwachstum. ",
                                html.Strong(">100"), " = überdurchschnittliches Wachstum. ",
                                html.Strong("<100"), " = unterdurchschnittlich. ",
                                html.Strong("100"), " = Durchschnitt."
                            ], className='kpi-desc')
                        ], className='kpi-card')
                    ], xl=3, lg=6, md=6, sm=12, className='mb-4'),
                    dbc.Col([
                        html.Div([
                            html.Div("ERFOLGSQUOTE", className='kpi-label'),
                            html.Div(id='kpi-success', className='kpi-value', title="Anteil Tracks mit Success Score ≥ 65"),
                            html.Div([
                                "Prozent Tracks mit Score >= 65. ",
                                html.Strong("Hoch (>30%)"), " = viele erfolgreiche Tracks. ",
                                html.Strong("Niedrig (<20%)"), " = schwieriger Markt."
                            ], className='kpi-desc')
                        ], className='kpi-card')
                    ], xl=3, lg=6, md=6, sm=12, className='mb-4'),
                    dbc.Col([
                        html.Div([
                            html.Div("TOP GENRE", className='kpi-label'),
                            html.Div(id='kpi-genre', className='kpi-value', style={'fontSize': '24px'}, title="Genre mit höchstem mittleren Marktanteil"),
                            html.Div([
                                "Dominantes Genre mit größtem Marktanteil. ",
                                "Zeigt aktuelle Präferenzen und Portfolio-Fokus des Marktes."
                            ], className='kpi-desc')
                        ], className='kpi-card')
                    ], xl=3, lg=6, md=6, sm=12, className='mb-4')
                ], className='mb-4', style={'padding': '8px', 'background': 'rgba(29,185,84,0.03)', 'borderRadius': '12px', 'border': '1px solid rgba(29,185,84,0.15)'}),
                
                
                
                
                # Row 1: Genre + Correlation
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.H3("Genre-Marktanteile (Grouped Bar Chart)", className='chart-title', style={'fontSize': '18px', 'fontWeight': '700', 'marginBottom': '8px'}),
                                    html.Div([
                                        html.Div(id='market-label-1', className='market-badge'),
                                        html.Span(id='year-badge-1', className='market-badge', style={'marginLeft': '6px'})
                                    ], style={'display': 'flex', 'alignItems': 'center'})
                                ], style={'display': 'flex', 'justifyContent': 'space-between'}),
                                html.P([
                                    "Durchschnittliche Marktanteile der Top-Genres. ",
                                    html.Strong("Hohe Balken"), " = dominante Genres. ",
                                    html.Strong("Niedrige Balken"), " = Nischen mit Potenzial. ",
                                    html.Span("Datenbasis (Historie): 2017–2021", style={'fontStyle': 'italic', 'color': '#95A5A6'})
                                ], className='chart-explanation')
                            ], className='chart-header'),
                            dcc.Loading(
                                id="loading-genre",
                                type="circle",
                                color="#1DB954",
                                children=dcc.Graph(id='chart-genre-shares', config={'displayModeBar': False}, style={'height': '400px', 'width': '100%'})
                            )
                        ], className='chart-card')
                    ], xl=6, lg=6, md=12, className='mb-4'),
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.H3("Audio-Feature Korrelation (Heatmap)", className='chart-title', style={'fontSize': '18px', 'fontWeight': '700', 'marginBottom': '8px'}),
                                    html.Div(id='market-label-2', className='market-badge')
                                ], style={'display': 'flex', 'justifyContent': 'space-between'}),
                                html.P([
                                    "Korrelations-Heatmap zeigt Zusammenhänge zwischen Audio-Features. ",
                                    html.Strong("Intensiv (nahe 1)"), " = Features treten gemeinsam auf. ",
                                    html.Strong("Blass (nahe 0)"), " = kein Zusammenhang. ",
                                    html.Span("Datenbasis (Historie): 2017–2021", style={'fontStyle': 'italic', 'color': '#95A5A6'})
                                ], className='chart-explanation')
                            ], className='chart-header'),
                            dcc.Loading(
                                id="loading-correlation",
                                type="circle",
                                color="#1DB954",
                                children=dcc.Graph(id='chart-correlation', config={'displayModeBar': False}, style={'height': '400px', 'width': '100%'})
                            )
                        ], className='chart-card')
                    ], xl=6, lg=6, md=12, className='mb-4')
                ], className='mb-4'),
                
                # Row 2: Audio Scatter + Market Trends
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.H3("Audio-Features vs. Erfolg (Scatter Plot)", className='chart-title', style={'fontSize': '18px', 'fontWeight': '700', 'marginBottom': '8px'}),
                                    html.Div(id='market-label-3', className='market-badge')
                                ], style={'display': 'flex', 'justifyContent': 'space-between'}),
                                html.P([
                                    "Tanzbarkeit (X) vs. Energie (Y). ",
                                    html.Strong("Größere Punkte"), " = höherer Score. ",
                                    html.Strong("Rechts oben"), " = Party-Hits. ",
                                    html.Strong("Links unten"), " = Balladen. ",
                                    html.Span("Datenbasis (Historie): 2017–2021", style={'fontStyle': 'italic', 'color': '#95A5A6'})
                                ], className='chart-explanation')
                            ], className='chart-header'),
                            dcc.Loading(
                                id="loading-scatter",
                                type="circle",
                                color="#1DB954",
                                children=dcc.Graph(id='chart-audio-scatter', config={'displayModeBar': False}, style={'height': '400px', 'width': '100%'})
                            )
                        ], className='chart-card')
                    ], xl=6, lg=6, md=12, className='mb-4'),
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.H3("Markt-Vergleich nach Jahr (Line Chart)", className='chart-title', style={'fontSize': '18px', 'fontWeight': '700', 'marginBottom': '8px'}),
                                    html.Div([
                                        html.Div(id='market-label-4', className='market-badge'),
                                        html.Span(id='year-badge-2', className='market-badge', style={'marginLeft': '6px'})
                                    ], style={'display': 'flex', 'alignItems': 'center'})
                                ], style={'display': 'flex', 'justifyContent': 'space-between'}),
                                html.P([
                                    "Entwicklung der Marktanteile über Jahre. ",
                                    html.Strong("Steigende Linien"), " = Wachstumsmarkt. ",
                                    html.Strong("Fallende Linien"), " = schrumpfender Markt. ",
                                    html.Strong("Stabil"), " = etabliert. ",
                                    html.Span("Datenbasis (Historie): 2017–2021", style={'fontStyle': 'italic', 'color': '#95A5A6'})
                                ], className='chart-explanation')
                            ], className='chart-header'),
                            dcc.Loading(
                                id="loading-trends",
                                type="circle",
                                color="#1DB954",
                                children=dcc.Graph(id='chart-market-trends', config={'displayModeBar': False}, style={'height': '400px', 'width': '100%'})
                            )
                        ], className='chart-card')
                    ], xl=6, lg=6, md=12, className='mb-4')
                ], className='mb-4'),
                
                # Row 3: High-Potential + Histogram
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.H3("Top 20 High-Potential Tracks (Ranking)", className='chart-title', style={'fontSize': '18px', 'fontWeight': '700', 'marginBottom': '8px'}),
                                    html.Div(id='market-label-5', className='market-badge', style=get_live_badge_style('market'))
                                ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'}),
                                html.P([
                                    "Ranking basierend auf historischen Erfolgsfaktoren (2017–2021). ",
                                    html.Strong("Score >80"), " = sehr hohes Hit-Potenzial. ",
                                    html.Strong("60-80"), " = solide. ",
                                    html.Strong("<60"), " = moderat. ",
                                    html.Span("Datenbasis (Historie): 2017–2021", style={'fontStyle': 'italic', 'color': '#95A5A6'})
                                ], className='chart-explanation')
                            ], className='chart-header'),
                            html.Div(
                                id='highpot-table-container',
                                style={
                                    'maxHeight': '400px',
                                    'overflowY': 'auto',
                                    'overflowX': 'hidden'
                                }
                            )
                        ], className='chart-card')
                    ], xl=6, lg=6, md=12, className='mb-4'),
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.H3("Erfolgs-Verteilung (Histogram)", className='chart-title', style={'fontSize': '18px', 'fontWeight': '700', 'marginBottom': '8px'}),
                                    html.Div(id='market-label-6', className='market-badge', style=get_live_badge_style('market'))
                                ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'}),
                                html.P([
                                    "Verteilung der Success-Scores. ",
                                    html.Strong("Median (orange)"), " = typischer Score. ",
                                    html.Strong("Rechts"), " = Hit-Markt. ",
                                    html.Strong("Links"), " = schwieriger Markt. ",
                                    html.Span("Datenbasis (Historie): 2017–2021", style={'fontStyle': 'italic', 'color': '#95A5A6'})
                                ], className='chart-explanation')
                            ], className='chart-header'),
                            dcc.Loading(
                                id="loading-histogram",
                                type="circle",
                                color="#1DB954",
                                children=dcc.Graph(id='chart-success-hist', config={'displayModeBar': False}, style={'height': '400px', 'width': '100%'})
                            )
                        ], className='chart-card')
                    ], xl=6, lg=6, md=12, className='mb-4')
                ], className='mb-4'),
                
                # Row 4: Live API Charts (Spotify + Genre Trend)
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.H3([html.Span("● ", style={"animation": "live-blink 1.5s ease-in-out infinite", "color": "#1DB954", "display": "inline-block", "marginRight": "5px"}), "Spotify Live Tracks (API Integration)"], 
                                           className='chart-title', style={'fontSize': '18px', 'fontWeight': '700', 'marginBottom': '8px'}),
                                    html.Div(id='market-label-spotify-live', className='market-badge', style=get_live_badge_style('market'))
                                ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '12px'}),
                                html.Div(id='live-timestamp-spotify', style={'fontSize': '11px', 'color': '#7F8C8D', 'marginBottom': '8px'}),
                                html.P([
                                    "Aktuelle populäre Titel direkt aus der Spotify API (Live-Anbindung). ",
                                    html.Strong("Popularity >80"), " = sehr populär. ",
                                    html.Strong("60-80"), " = solide. ",
                                    html.Strong("<60"), " = Nische/aufsteigend. "
                                ], className='chart-explanation')
                            ], className='chart-header'),
                            dcc.Loading(
                                id="loading-spotify",
                                type="circle",
                                color="#1DB954",
                                children=html.Div(
                                    id='spotify-live-tracks',
                                    style={
                                        'maxHeight': '400px',
                                        'overflowY': 'auto',
                                        'overflowX': 'hidden'
                                    }
                                )
                            )
                        ], className='chart-card')
                    ], xl=6, lg=6, md=12, className='mb-4'),
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.H5([html.Span("● ", style={"animation": "live-blink 1.5s ease-in-out infinite", "color": "#1DB954"}), "Live Genre Trend-Analyse (API Integration)"], 
                                       className="chart-title", style={'fontSize': '18px', 'fontWeight': '700', 'marginBottom': '8px'}),
                                html.Div(id='market-label-deviation', className="market-badge", style=get_live_badge_style('market'))
                            ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '12px'}),
                            html.Div(id='live-timestamp-genre', style={'fontSize': '11px', 'color': '#7F8C8D', 'marginBottom': '8px'}),
                            html.P([
                                "Vergleicht aktuelle Genre-Popularität (Live) mit historischem Durchschnitt (2017–2021). ",
                                html.Strong("Türkis (+)"), " = Trend steigt. ",
                                html.Strong("Pink (-)"), " = Trend sinkt. ",
                                "Last.fm validiert Spotify-Trends (7 Tage Nutzer-Plays). ",
                                "Genres werden konsistent über Keyword-Matching aus Titel und Künstler bestimmt."
                            ], className="chart-explanation", style={'marginBottom': '15px'}),
                    dcc.Loading(
                        id="loading-deviation",
                        type="circle",
                        color="#4ECDC4",
                        children=dcc.Graph(id='chart-genre-deviation', config={'displayModeBar': False}, style={'height': '400px', 'width': '100%'})
                    ),
                            html.Div(id='validation-stats'),
                            html.Div("Quellen: Spotify (Live-Tracks) · Last.fm (7-Tage Nutzer-Daten) · Historik (2017–2021)", 
                                     style={'color': '#A0A0A0', 'fontSize': '11px', 'marginTop': '10px', 'textAlign': 'center'})
                        ], className="chart-card")
                    ], xl=6, lg=6, md=12, className='mb-4')
                ], className='mb-4')
                
            ], className='main-content')
        ], xs=12, sm=12, md=9, lg=9, xl=9, className='p-0')
    ], className='g-0'),
    
    # Footer
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Small(
                    [
                        "Quelle: Spotify & Last.fm APIs – aggregierte, historische Auswertung. ",
                        "Datenstand siehe ",
                        html.Code("data/data_journal.csv", style={'color': '#1DB954'}),
                        " – Konfiguration über ",
                        html.Code("config.json", style={'color': '#1DB954'}),
                        " (Basis: historische Analyse 2017–2021). ",
                        "Methodische Hinweise: Kennzahlen sind als vergleichende Marktindikatoren zu verstehen und ersetzen kein detailliertes A&R-Listening."
                    ],
                    style={
                        'color': '#95a5a6',
                        'fontSize': '11px',
                        'textAlign': 'center',
                        'display': 'block',
                        'padding': '15px 15px 8px 15px',
                        'marginTop': '10px',
                        'borderTop': '1px solid rgba(29,185,84,0.2)'
                    }
                ),
                html.Div([
                    html.Span("Platform Bias: Nur Spotify", style={'backgroundColor': '#2C3E50', 'color': '#BDC3C7', 'padding': '3px 8px', 'borderRadius': '12px', 'fontSize': '9px', 'marginRight': '6px'}),
                    html.Span("Temporal Scope: 2017-2021", style={'backgroundColor': '#2C3E50', 'color': '#BDC3C7', 'padding': '3px 8px', 'borderRadius': '12px', 'fontSize': '9px', 'marginRight': '6px'}),
                    html.Span("Genre Prediction: Keyword-based", style={'backgroundColor': '#2C3E50', 'color': '#BDC3C7', 'padding': '3px 8px', 'borderRadius': '12px', 'fontSize': '9px'})
                ], style={'textAlign': 'center', 'paddingBottom': '15px'})
            ])
        ], width=12)
    ], className='g-0'),
    
    dcc.Interval(id='interval-refresh', interval=60000, n_intervals=0),
    dcc.Store(id='selected-markets', data=['DE', 'UK', 'BR'])
    
], fluid=True, className='p-0', style={'maxWidth': '100%'})

# Callbacks für Interaktivität

def predict_genre_simple(track_name, artist):
    """
    Vereinfachte Genre-Prädiktion basierend auf Keywords.
    Konsistentes Keyword-Matching aus Titel und Künstler für reproduzierbare Kategorisierung.
    """
    try:
        text = ((str(track_name) or "") + " " + (str(artist) or "")).lower()
    except Exception:
        return "Other"
    
    # 1) Zuerst Mapping aus JSON nutzen
    for sub, main in GENRE_MAPPING_DASH.items():
        if sub.lower() in text:
            return main
    
    # 2) Bisherige einfache Keyword-Regeln als Fallback
    genre_keywords = {
        "Pop": ["pop", "love", "baby", "heart", "girl", "boy", "dance"],
        "Hip-Hop": ["rap", "hip hop", "feat", "ft.", "lil ", "young", "gang"],
        "Rock": ["rock", "band", "guitar", "wild", "fire", "electric"],
        "Dance/Electronic": ["house", "techno", "edm", "beat", "bass", "club", "party", "electronic"],
        "Latin": ["latin", "reggaeton", "salsa", "bachata", "fiesta", "corazón", "sertanejo"],
        "R&B": ["r&b", "soul", "rhythm", "blues", "slow jam"],
        "Country": ["country", "cowboy", "truck", "whiskey"],
        "Jazz": ["jazz", "piano", "saxophone", "swing"],
    }
    
    # Keyword-Matching
    for genre, keywords in genre_keywords.items():
        if any(k in text for k in keywords):
            return genre
    
    # Fallback wenn kein Keyword matched
    return "Other"

# ==================== CALLBACKS ====================

@app.callback(
    Output('api-status-text', 'children'),
    [Input('interval-refresh', 'n_intervals')]
)
def update_api_status(n):
    """Zeigt API-Verbindungsstatus für Spotify und Last.fm"""
    try:
        status_parts = []
        
        # Spotify Status
        if spotify_api.status == "Verbunden":
            status_parts.append(html.Span([html.Span("● ", style={"animation": "live-blink 1.5s ease-in-out infinite", "color": "#1DB954", "display": "inline-block", "marginRight": "5px"}), "Spotify verbunden"]))
        else:
            status_parts.append(f"Spotify {spotify_api.status}")
        
        # Last.fm Status - nutzt echten API Test
        if lastfm_api.status == "Verbunden":
            status_parts.append(html.Span([html.Span("● ", style={"animation": "live-blink 1.5s ease-in-out infinite", "color": "#1DB954", "display": "inline-block", "marginRight": "5px"}), "Last.fm verbunden"]))
        else:
            status_parts.append(f"Last.fm {lastfm_api.status}")
        
        # Erstelle ein Div mit den Status-Teilen
        result = []
        for i, part in enumerate(status_parts):
            if i > 0:
                result.append(" | ")
            result.append(part)
        
        return result
    except:
        return "Verbindung unterbrochen"

@app.callback(
    [Output('live-timestamp-spotify', 'children'),
     Output('live-timestamp-genre', 'children')],
    Input('interval-refresh', 'n_intervals')
)
def update_live_timestamps(n):
    """Aktualisiert Live-Zeitstempel"""
    ts = datetime.now().strftime("%d.%m.%Y - %H:%M:%S")
    return f"Stand: {ts}", f"Stand: {ts}"

@app.callback(
    [Output('selected-markets', 'data'),
     Output('btn-all', 'className'),
     Output('btn-de', 'className'),
     Output('btn-uk', 'className'),
     Output('btn-br', 'className')],
    [Input('btn-all', 'n_clicks'),
     Input('btn-de', 'n_clicks'),
     Input('btn-uk', 'n_clicks'),
     Input('btn-br', 'n_clicks')],
    [State('selected-markets', 'data')]
)
def update_market_selection(n_all, n_de, n_uk, n_br, current_markets):
    try:
        if not ctx.triggered:
            return ['DE', 'UK', 'BR'], 'market-button active', 'market-button', 'market-button', 'market-button'
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'btn-all':
            markets = ['DE', 'UK', 'BR']
        else:
            market_map = {'btn-de': 'DE', 'btn-uk': 'UK', 'btn-br': 'BR'}
            market = market_map.get(button_id)
            
            if set(current_markets) == {'DE', 'UK', 'BR'}:
                markets = [market]
            elif market in current_markets:
                markets = [m for m in current_markets if m != market]
                if not markets:
                    markets = ['DE', 'UK', 'BR']
            else:
                markets = current_markets + [market]
                if len(markets) > 2:
                    markets = ['DE', 'UK', 'BR']
        
        is_all = set(markets) == {'DE', 'UK', 'BR'}
        
        classes = {
            'btn-all': 'market-button active' if is_all else 'market-button',
            'btn-de': 'market-button active' if 'DE' in markets else 'market-button',
            'btn-uk': 'market-button active' if 'UK' in markets else 'market-button',
            'btn-br': 'market-button active' if 'BR' in markets else 'market-button'
        }
        
        return markets, classes['btn-all'], classes['btn-de'], classes['btn-uk'], classes['btn-br']
    except Exception as e:
        print(f"Fehler in update_market_selection: {e}")
        return ['DE', 'UK', 'BR'], 'market-button active', 'market-button', 'market-button', 'market-button'





@app.callback(
    [Output('selected-markets', 'data', allow_duplicate=True),
     Output('btn-all', 'className', allow_duplicate=True),
     Output('btn-de', 'className', allow_duplicate=True),
     Output('btn-uk', 'className', allow_duplicate=True),
     Output('btn-br', 'className', allow_duplicate=True),
     Output('market-dropdown-mobile', 'value'),
     Output('year-filter', 'value', allow_duplicate=True)],
    [Input('market-dropdown-mobile', 'value'),
     Input('year-dropdown-mobile', 'value')],
    prevent_initial_call=True
)
def update_from_mobile_filters(market_val, year_val):
    """Mobile Dropdowns ändern Desktop Filter"""
    # Markt setzen
    if market_val == 'ALL':
        markets = ['DE', 'UK', 'BR']
    else:
        markets = [market_val]
    
    is_all = set(markets) == {'DE', 'UK', 'BR'}
    classes = {
        'btn-all': 'market-button active' if is_all else 'market-button',
        'btn-de': 'market-button active' if 'DE' in markets else 'market-button',
        'btn-uk': 'market-button active' if 'UK' in markets else 'market-button',
        'btn-br': 'market-button active' if 'BR' in markets else 'market-button'
    }
    
    # Jahr = None wenn "ALL" gewählt
    year_output = None if year_val == "ALL" else year_val
    
    return markets, classes['btn-all'], classes['btn-de'], classes['btn-uk'], classes['btn-br'], market_val, year_output

@app.callback(
    [Output('kpi-shannon', 'children'),
     Output('kpi-growth', 'children'),
     Output('kpi-success', 'children'),
     Output('kpi-genre', 'children')],
    [Input('selected-markets', 'data')]
)
def update_kpis(markets):
    """
    Berechnet und aktualisiert die vier Haupt-KPIs basierend auf ausgewählten Märkten.
    Sichere Version mit Spaltenprüfung und Jahr+Markt-Gruppierung.
    """
    try:
        # Märkte filtern (ohne .copy() da nur gefiltert wird)
        if set(markets) != {"DE", "UK", "BR"}:
            df_kpi = kpi_df[kpi_df["market"].isin(markets)]
            df_enh = enhanced_df[enhanced_df["market"].isin(markets)]
        else:
            df_kpi = kpi_df
            df_enh = enhanced_df

        if df_kpi.empty:
            return "N/A", "N/A", "0%", "N/A"

        # Wenn year vorhanden: erst pro Markt+Jahr mitteln
        if "year" in df_kpi.columns:
            grouped = (
                df_kpi
                .groupby(["market", "year"], as_index=False)
                .agg({
                    "shannon_diversity": "mean",
                    "growth_momentum_index": "mean"
                })
            )
            shannon = grouped["shannon_diversity"].mean()
            growth = grouped["growth_momentum_index"].mean()
        else:
            # Fallback: altes Verhalten
            shannon = df_kpi["shannon_diversity"].mean()
            growth = df_kpi["growth_momentum_index"].mean()

        # Erfolgsquote aus enhanced
        if df_enh is not None and not df_enh.empty and "success_score" in df_enh.columns:
            success = (df_enh["success_score"] >= 65).sum() / len(df_enh) * 100
        else:
            success = 0

        # Top-Genre sicher bestimmen
        if "genre_harmonized" in df_kpi.columns and "market_share_percent" in df_kpi.columns:
            top_genre = (
                df_kpi
                .groupby("genre_harmonized")["market_share_percent"]
                .mean()
                .sort_values(ascending=False)
                .index[0]
            )
        else:
            top_genre = "N/A"

        return f"{shannon:.2f}", f"{growth:.0f}", f"{success:.1f}%", top_genre
    except Exception as e:
        print(f"Fehler in update_kpis: {e}")
        import traceback
        traceback.print_exc()
        return "N/A", "N/A", "N/A", "N/A"

market_label_outputs = [Output(f'market-label-{i}', 'children') for i in range(1, 7)] + [Output('market-label-spotify-live', 'children')]

@app.callback(
    market_label_outputs,
    [Input('selected-markets', 'data')]
)
def update_market_labels(markets):
    # Bei mehr als 2 Märkten automatisch "Alle Märkte" anzeigen
    if len(markets) > 2:
        label = "Alle Märkte"
    else:
        label = get_market_label(markets)
    return [label] * 7

@app.callback(
    [Output('year-badge-1', 'children'),
     Output('year-badge-2', 'children'),
     Output('year-badge-1', 'style'),
     Output('year-badge-2', 'style')],
    Input('year-filter', 'value')
)
def update_year_badges(year):
    if not year or year == "ALL":
        hidden = {'display': 'none'}
        return None, None, hidden, hidden
    shown = {
        'display': 'inline-flex',
        'marginLeft': '6px'
    }
    text = f"Jahr: {year}"
    return text, text, shown, shown

@app.callback(
    Output('chart-genre-shares', 'figure'),
    [Input('selected-markets', 'data'),
     Input('year-filter', 'value')]
)
def update_genre_shares(markets, year):
    """
    Erstellt Grouped Bar Chart mit Top-Genres nach Marktanteil.
    
    Zeigt durchschnittliche Marktanteile pro Genre und Markt.
    Hover-Tooltip enthält zusätzlich Wachstums-Index und Shannon-Diversität.
    """
    try:
        if set(markets) != {'DE', 'UK', 'BR'}:
            df = kpi_df[kpi_df['market'].isin(markets)]
        else:
            df = kpi_df
        
        # Jahresfilter anwenden falls vorhanden
        if year not in (None, "ALL") and "year" in df.columns:
            df = df[df["year"] == year]
        
        # Leerdaten-Check
        if df.empty:
            fig = go.Figure()
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                annotations=[dict(text="Keine Daten für diesen Filter", showarrow=False, x=0.5, y=0.5, font=dict(size=16, color="#1DB954"))]
            )
            return fig
        
        # Berechne zusätzliche Metriken für Tooltip (mean statt sum)
        df_tooltip = df.groupby(['genre_harmonized', 'market']).agg({
            'market_share_percent': 'mean',
            'growth_momentum_index': 'mean',
            'shannon_diversity': 'mean'
        }).reset_index()
        
        # Top 5 Genres basierend auf Gesamt-Durchschnitt
        genre_avg = df_tooltip.groupby('genre_harmonized')['market_share_percent'].mean().nlargest(5)
        top_genres = genre_avg.index
        df_tooltip = df_tooltip[df_tooltip['genre_harmonized'].isin(top_genres)]
        
        colors = get_market_colors()
        
        # Grouped Bar Chart mit erweiterten Hover-Daten
        fig = px.bar(
            df_tooltip,
            x='genre_harmonized',
            y='market_share_percent',
            color='market',
            barmode='group',
            color_discrete_map=colors,
            hover_data={
                'market_share_percent': ':.2f',
                'growth_momentum_index': ':.0f',
                'shannon_diversity': ':.2f'
            },
            labels={'market_share_percent': 'Marktanteil (%)', 'genre_harmonized': 'Genre', 'market': 'Markt'}
        )
        
        # Custom Tooltip Template
        fig.update_traces(
            hovertemplate="<b>%{x}</b><br>" +
                         "Marktanteil: %{y:.2f}%<br>" +
                         "Wachstum-Index: %{customdata[1]:.0f}<br>" +
                         "Diversität: %{customdata[2]:.2f}<br>" +
                         "<extra></extra>"
        )
        
        fig.update_layout(create_plotly_theme())
        fig.update_xaxes(title='Genre')
        fig.update_yaxes(title='Marktanteil (%)', range=[0, 100], ticksuffix="%")
        
        return fig
    except Exception as e:
        print(f"Fehler in update_genre_shares: {e}")
        import traceback
        traceback.print_exc()
        return go.Figure()

@app.callback(
    Output('chart-correlation', 'figure'),
    [Input('selected-markets', 'data')]
)
def update_correlation(markets):
    """
    Erstellt Korrelations-Heatmap für Audio-Features.
    
    Analysiert statistische Zusammenhänge zwischen 8 Audio-Charakteristiken.
    Farbskala passt sich automatisch an gewählte Märkte an.
    """
    try:
        df = enhanced_df[enhanced_df['market'].isin(markets)] if set(markets) != {'DE', 'UK', 'BR'} else enhanced_df
        
        audio_cols = ['danceability', 'energy', 'valence', 'acousticness', 
                      'instrumentalness', 'liveness', 'speechiness', 'tempo']
        
        corr = df[audio_cols].corr()
        
        # Markt-spezifische Farbskala
        if set(markets) == {'DE'}:
            colorscale = [
                [0.0, '#0a3d20'],
                [0.25, '#0d5028'],
                [0.5, '#146634'],
                [0.75, '#1a7f3d'],
                [1.0, '#1DB954']
            ]
        elif set(markets) == {'UK'}:
            colorscale = [
                [0.0, '#4a0a0a'],
                [0.25, '#6b1010'],
                [0.5, '#9a1e1e'],
                [0.75, '#cc3333'],
                [1.0, '#FF6B6B']
            ]
        elif set(markets) == {'BR'}:
            colorscale = [
                [0.0, '#0a3a3a'],
                [0.25, '#0f5555'],
                [0.5, '#1a7070'],
                [0.75, '#2a9999'],
                [1.0, '#4ECDC4']
            ]
        else:
            # Multi-Markt oder alle Märkte: Standard Grün
            colorscale = [
                [0.0, '#0a3d20'],
                [0.25, '#0d5028'],
                [0.5, '#146634'],
                [0.75, '#1a7f3d'],
                [1.0, '#1DB954']
            ]
        
        fig = go.Figure(data=go.Heatmap(
            z=corr.values,
            x=corr.columns,
            y=corr.columns,
            colorscale=colorscale,
            zmid=0,
            text=np.round(corr.values, 2),
            texttemplate='%{text}',
            textfont=dict(size=10, color='white'),
            colorbar=dict(title="Korrelation")
        ))
        
        fig.update_layout(create_plotly_theme())
        fig.update_xaxes(title='Audio Features')
        fig.update_yaxes(title='Audio Features')
        fig.update_layout(height=400)
        
        return fig
    except Exception as e:
        print(f"Fehler in update_correlation: {e}")
        import traceback
        traceback.print_exc()
        return go.Figure()

@app.callback(
    Output('chart-audio-scatter', 'figure'),
    [Input('selected-markets', 'data')]
)
def update_audio_scatter(markets):
    try:
        df = enhanced_df[enhanced_df['market'].isin(markets)] if set(markets) != {'DE', 'UK', 'BR'} else enhanced_df
        
        # Reproduzierbares Sampling mit random_state
        df_sample = df.sample(min(1000, len(df)), random_state=42)
        
        colors = get_market_colors()
        
        fig = px.scatter(
            df_sample,
            x='danceability',
            y='energy',
            color='market',
            size='success_score',
            opacity=0.6,
            color_discrete_map=colors,
            labels={'danceability': 'Tanzbarkeit', 'energy': 'Energie', 'market': 'Markt'},
            hover_data=['success_score']
        )
        
        fig.update_layout(create_plotly_theme())
        
        return fig
    except Exception as e:
        print(f"Fehler in update_audio_scatter: {e}")
        import traceback
        traceback.print_exc()
        return go.Figure()

@app.callback(
    Output('chart-market-trends', 'figure'),
    [Input('selected-markets', 'data'),
     Input('year-filter', 'value')]
)
def update_market_trends(markets, year):
    """
    Market Trends Chart - nutzt cleaned_market_trends.csv falls vorhanden
    Zeigt ECHTE Marktverläufe mit sichtbaren Unterschieden
    """
    try:
        # Falls Market Trends CSV vorhanden, nutze diese
        if market_trends_df is not None:
            df = market_trends_df[market_trends_df['market'].isin(markets)] if set(markets) != {'DE', 'UK', 'BR'} else market_trends_df
            
            # Jahresfilter anwenden falls vorhanden
            if year not in (None, "ALL") and "year" in df.columns:
                df = df[df["year"] == year]
            
            if len(df) == 0:
                fig = go.Figure()
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor='rgba(0,0,0,0)',
                    annotations=[dict(text="Keine Daten für diesen Filter", showarrow=False, x=0.5, y=0.5, font=dict(size=16, color="#1DB954"))]
                )
                return fig
            
            df = df.copy()  # erst jetzt kopieren vor Mutation
            df['year'] = df['year'].astype(int)
            df_grouped = df.sort_values(['market', 'year'])
            
        else:
            # Fallback auf KPI Daten
            df = kpi_df[kpi_df['market'].isin(markets)] if set(markets) != {'DE', 'UK', 'BR'} else kpi_df
            
            # Jahresfilter anwenden falls vorhanden
            if year not in (None, "ALL") and "year" in df.columns:
                df = df[df["year"] == year]
            
            if df.empty:
                fig = go.Figure()
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor='rgba(0,0,0,0)',
                    annotations=[dict(text="Keine Daten für diesen Filter", showarrow=False, x=0.5, y=0.5, font=dict(size=16, color="#1DB954"))]
                )
                return fig
            
            # MEAN für durchschnittliche Genre-Anteile
            df_grouped = df.groupby(['year', 'market'])['market_share_percent'].mean().reset_index()
        
        colors = get_market_colors()
        market_names = {'DE': 'Deutschland', 'UK': 'UK', 'BR': 'Brasilien'}
        
        fig = go.Figure()
        
        # Chart für jeden Markt
        for market in sorted(df_grouped['market'].unique()):
            df_market = df_grouped[df_grouped['market'] == market].sort_values('year')
            
            fig.add_trace(go.Scatter(
                x=df_market['year'],
                y=df_market['market_share_percent'],
                mode='lines+markers',
                name=market_names[market],
                line=dict(
                    color=colors[market], 
                    width=3,
                    shape='spline',  # Glatte Kurven
                    smoothing=1.0
                ),
                marker=dict(size=10, symbol='circle'),
                hovertemplate='<b>%{fullData.name}</b><br>Jahr: %{x}<br>Marktanteil: %{y:.1f}%<extra></extra>'
            ))
        
        fig.update_layout(create_plotly_theme())
        fig.update_xaxes(
            title='Jahr', 
            dtick=1,
            gridcolor='rgba(29,185,84,0.15)'
        )
        
        # Y-Achse so skalieren dass Unterschiede SICHTBAR sind
        y_values = df_grouped['market_share_percent'].values
        y_min = y_values.min()
        y_max = y_values.max()
        y_range = y_max - y_min
        
        # Wenn Variation sehr klein, trotzdem Unterschiede zeigen
        if y_range < 5:
            y_mid = (y_min + y_max) / 2
            y_axis_min = max(0, y_mid - 3)
            y_axis_max = y_mid + 3
        else:
            y_padding = y_range * 0.15
            y_axis_min = max(0, y_min - y_padding)
            y_axis_max = y_max + y_padding
        
        fig.update_yaxes(
            title='Marktanteil (%)',
            range=[y_axis_min, y_axis_max],
            tickformat='.1f',
            gridcolor='rgba(29,185,84,0.15)'
        )
        
        fig.update_layout(
            showlegend=True,
            legend=dict(
                orientation="h", 
                yanchor="bottom", 
                y=1.02, 
                xanchor="right", 
                x=1,
                bgcolor='rgba(15,20,30,0.9)',
                bordercolor='rgba(29,185,84,0.3)',
                borderwidth=1
            ),
            hovermode='x unified'
        )
        
        return fig
    except Exception as e:
        print(f"Fehler in update_market_trends: {e}")
        import traceback
        traceback.print_exc()
        return go.Figure()

@app.callback(
    Output('highpot-table-container', 'children'),
    [Input('selected-markets', 'data')]
)
def update_highpot_table(markets):
    try:
        df = highpot_df[highpot_df['market'].isin(markets)] if set(markets) != {'DE', 'UK', 'BR'} else highpot_df
        
        df_top = df.nlargest(20, 'success_score')
        
        colors = get_market_colors()
        market_names = {'DE': 'Deutschland', 'UK': 'UK', 'BR': 'Brasilien'}
        
        rows = []
        for i, row in enumerate(df_top.itertuples(), 1):
            track_display = f"{row.track_name[:35]}..." if len(row.track_name) > 35 else row.track_name
            artist_display = f"{row.artist[:25]}..." if len(row.artist) > 25 else row.artist
            
            # Sichere Farb-Zugriffe
            color = colors.get(row.market, '#1DB954')
            market_name = market_names.get(row.market, row.market)
            
            rows.append(
                html.Div([
                    html.Div(f"#{i}", style={
                        'fontSize': '11px',
                        'fontWeight': '900',
                        'color': '#1DB954',
                        'minWidth': '40px',
                        'textAlign': 'center'
                    }),
                    html.Div([
                        html.Div(track_display, style={
                            'fontSize': '13px',
                            'fontWeight': '700',
                            'color': '#FFFFFF',
                            'marginBottom': '2px',
                            'whiteSpace': 'nowrap',
                            'overflow': 'hidden',
                            'textOverflow': 'ellipsis',
                            'maxWidth': '200px'
                        }),
                        html.Div(f"von {artist_display}", style={
                            'fontSize': '11px',
                            'color': '#B3B3B3',
                            'whiteSpace': 'nowrap',
                            'overflow': 'hidden',
                            'textOverflow': 'ellipsis',
                            'maxWidth': '200px'
                        })
                    ], style={'flex': '1'}),
                    html.Div([
                        html.Span(market_name, style={
                            'fontSize': '10px',
                            'color': color,
                            'fontWeight': '600',
                            'padding': '2px 8px',
                            'background': hex_to_rgba(color, 0.15),
                            'borderRadius': '6px',
                            'marginRight': '6px'
                        }),
                        html.Span(f"Score: {row.success_score:.0f}", style={
                            'fontSize': '10px',
                            'color': '#1DB954',
                            'fontWeight': '600',
                            'padding': '2px 8px',
                            'background': 'rgba(29,185,84,0.15)',
                            'borderRadius': '6px'
                        })
                    ], style={'display': 'flex', 'gap': '4px'})
                ], style={
                    'display': 'flex',
                    'alignItems': 'flex-start',
                    'gap': '8px',
                    'padding': '10px 14px',
                    'marginBottom': '8px',
                    'background': 'rgba(20,25,40,0.8)',
                    'borderLeft': '4px solid #1DB954',
                    'borderRadius': '8px'
                })
            )
        
        return html.Div(rows)
    except Exception as e:
        print(f"Fehler in update_highpot_table: {e}")
        import traceback
        traceback.print_exc()
        return html.Div("Keine Daten verfügbar")

@app.callback(
    Output('chart-success-hist', 'figure'),
    [Input('selected-markets', 'data')]
)
def update_success_hist(markets):
    try:
        df = enhanced_df[enhanced_df['market'].isin(markets)] if set(markets) != {'DE', 'UK', 'BR'} else enhanced_df
        
        median = df['success_score'].median()
        colors = get_market_colors()
        
        fig = go.Figure()
        
        # Separate Histogramme pro Markt mit Farben
        for market in sorted(df['market'].unique()):
            df_market = df[df['market'] == market]
            fig.add_trace(go.Histogram(
                x=df_market['success_score'],
                nbinsx=40,
                marker_color=colors[market],
                opacity=0.7,
                name=market
            ))
        
        # Barmode: overlay bei 1 Markt, group bei mehreren
        barmode = 'overlay' if len(df['market'].unique()) == 1 else 'group'
        fig.update_layout(barmode=barmode)
        
        fig.add_vline(
            x=median,
            line_dash='dash',
            line_color='#F39C12',
            line_width=3,
            annotation_text=f'Median: {median:.1f}',
            annotation_position='top right'
        )
        
        fig.update_layout(create_plotly_theme())
        fig.update_xaxes(title='Success-Score')
        fig.update_yaxes(title='Anzahl Tracks')
        
        return fig
    except Exception as e:
        print(f"Fehler in update_success_hist: {e}")
        import traceback
        traceback.print_exc()
        return go.Figure()

@app.callback(
    Output('spotify-live-tracks', 'children'),
    [Input('interval-refresh', 'n_intervals'),
     Input('selected-markets', 'data')]
)
def update_spotify_live(n, markets):
    """
    Lädt aktuelle Trending-Tracks von der Spotify API basierend auf gewählten Märkten.
    
    Zeigt bis zu 10 unique Tracks sortiert nach Popularity.
    Aktualisiert sich automatisch alle 60 Sekunden (Interval).
    """
    try:
        seen_tracks = set()
        unique_tracks = []
        
        if set(markets) == {'DE', 'UK', 'BR'}:
            for market in ['DE', 'UK', 'BR']:
                tracks = spotify_api.get_featured_tracks(market, 7)
                for track in tracks:
                    track_id = f"{track['name']}_{track['artist']}"
                    if track_id not in seen_tracks:
                        seen_tracks.add(track_id)
                        unique_tracks.append(track)
        else:
            for market in markets:
                tracks = spotify_api.get_featured_tracks(market, 10 // len(markets) + 2)
                for track in tracks:
                    track_id = f"{track['name']}_{track['artist']}"
                    if track_id not in seen_tracks:
                        seen_tracks.add(track_id)
                        unique_tracks.append(track)
        
        # Sortiere nach Popularity, dann limitiere auf 20
        unique_tracks = sorted(unique_tracks, key=lambda x: x.get('popularity', 0), reverse=True)
        unique_tracks = unique_tracks[:20]
        
        if not unique_tracks:
            fallback_tracks = safe_fetch_spotify()
            if fallback_tracks:
                unique_tracks = fallback_tracks
        
        if not unique_tracks:
            return html.Div("API-Daten werden geladen...", 
                           style={'textAlign': 'center', 'color': '#7F8C8D', 'padding': '30px'})
        
        colors = get_market_colors()
        market_names = {'DE': 'Deutschland', 'UK': 'UK', 'BR': 'Brasilien'}
        
        track_elements = []
        for i, track in enumerate(unique_tracks, 1):
            # Sichere Farb-Zugriffe
            color = colors.get(track['market'], '#1DB954')
            market_name = market_names.get(track['market'], track['market'])
            
            track_elements.append(
                html.Div([
                    # Linke Spalte: Bild + Nummer
                    html.Div([
                        html.Img(src=track['image'], style={
                            'width': '45px',
                            'height': '45px',
                            'borderRadius': '6px',
                            'objectFit': 'cover',
                            'display': 'block'
                        }) if track.get('image') else html.Div(style={'width': '45px', 'height': '45px'}),
                        html.Span(f"#{i}", style={
                            'fontSize': '11px',
                            'fontWeight': '900',
                            'color': '#1DB954',
                            'textAlign': 'center',
                            'display': 'block',
                            'marginTop': '2px'
                        })
                    ], style={'minWidth': '45px', 'marginRight': '10px'}),
                    
                    # Rechte Spalte: Track Info kompakt
                    html.Div([
                        html.Div([
                            html.Div(track['name'], style={
                                'fontSize': '13px',
                                'fontWeight': '700',
                                'color': '#FFFFFF',
                                'whiteSpace': 'nowrap',
                                'overflow': 'hidden',
                                'textOverflow': 'ellipsis',
                                'maxWidth': '180px'
                            }),
                            html.Div(track['artist'], style={
                                'fontSize': '11px',
                                'color': '#B3B3B3',
                                'whiteSpace': 'nowrap',
                                'overflow': 'hidden',
                                'textOverflow': 'ellipsis',
                                'maxWidth': '180px'
                            })
                        ]),
                        html.Div([
                            html.Span(market_name, style={
                                'fontSize': '10px',
                                'color': color,
                                'fontWeight': '600',
                                'padding': '2px 8px',
                                'background': hex_to_rgba(color, 0.15),
                                'borderRadius': '6px',
                                'marginRight': '6px'
                            }),
                            html.Span(f"Pop: {track['popularity']}", style={
                                'fontSize': '10px',
                                'color': '#1DB954',
                                'fontWeight': '600',
                                'padding': '2px 8px',
                                'background': 'rgba(29,185,84,0.15)',
                                'borderRadius': '6px'
                            })
                        ], style={'display': 'flex', 'gap': '4px', 'marginTop': '4px'})
                    ], style={'flex': '1'})
                ], style={
                    'display': 'flex',
                    'alignItems': 'flex-start',
                    'gap': '8px',
                    'padding': '10px 14px',
                    'marginBottom': '8px',
                    'background': 'rgba(20,25,40,0.8)',
                    'borderLeft': '4px solid #1DB954',
                    'borderRadius': '8px'
                })
            )
        
        return html.Div(track_elements)
    except Exception as e:
        print(f"Spotify Live Error: {e}")
        import traceback
        traceback.print_exc()
        return html.Div("API temporär nicht verfügbar", 
                       style={'textAlign': 'center', 'color': '#7F8C8D', 'padding': '30px'})

# ==================== LIVE GENRE DEVIATION MONITOR ====================

@app.callback(
    [Output('chart-genre-deviation', 'figure'),
     Output('validation-stats', 'children'),
     Output('market-label-deviation', 'children')],
    [Input('selected-markets', 'data'),
     Input('interval-refresh', 'n_intervals')]
)
def update_genre_deviation(markets, n_intervals):
    """Live Genre Deviation Monitor"""
    try:
        df_hist = kpi_df[kpi_df['market'].isin(markets)] if set(markets) != {'DE', 'UK', 'BR'} else kpi_df
        
        hist_genre_share = df_hist.groupby('genre_harmonized')['market_share_percent'].mean()
        
        current_tracks = []
        for m in markets:
            spotify_tracks = spotify_api.get_featured_tracks(m, 10) or []  # reduziert von 20
            current_tracks.extend(spotify_tracks)
        
        for m in markets:
            country = LASTFM_COUNTRY_MAP.get(m)
            if country:
                lastfm_tracks = get_lastfm_toptracks(country, 10) or []  # reduziert von 15
                for t in lastfm_tracks:
                    t['weight'] = LASTFM_WEIGHT
                current_tracks.extend(lastfm_tracks)
        
        if not current_tracks:
            fig = go.Figure()
            fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', title="Keine Live-Daten", height=400)
            stats = html.Div([html.Span("API nicht verfügbar", className="val-pill", style={'background': 'rgba(255, 107, 157, 0.2)', 'color': '#FF6B9D', 'border': '1px solid #FF6B9D'})])
            badge = "Alle Märkte"
            return fig, stats, badge
        
        genre_counter = {}
        for track in current_tracks:
            g = predict_genre_simple(track.get('name', ''), track.get('artist', ''))
            weight = track.get('weight', 1.0)
            genre_counter[g] = genre_counter.get(g, 0) + weight
        
        total_live = sum(genre_counter.values())
        live_genre_share = {g: (c / total_live) * 100 for g, c in genre_counter.items()}
        
        deviation_rows = []
        # Nur Genres anzeigen, die sowohl historisch als auch live vorkommen
        for g in hist_genre_share.index:
            if g not in live_genre_share:  # Genre hat keine Live-Treffer → überspringen
                continue
            hist_val = float(hist_genre_share[g])
            live_val = float(live_genre_share[g])
            dev = live_val - hist_val
            status = "BOOMING" if dev > 2 else "DECLINING" if dev < -2 else "STABLE"
            deviation_rows.append({"genre": g, "historical_share": hist_val, "current_share": live_val, "deviation": dev, "status": status})
        
        # Edge-Case: Keine Genres nach Filterung
        if not deviation_rows:
            fig = go.Figure()
            fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', title="Keine Live-Genres erkennbar", height=400)
            stats = html.Div([html.Span("Keine Daten", className="val-pill", style=get_pill_style('neutral'))])
            market_labels = {'DE': 'Deutschland', 'UK': 'UK', 'BR': 'Brasilien'}
            badge = " + ".join([market_labels.get(m, m) for m in sorted(markets)]) if len(markets) <= 2 else "Alle Märkte"
            return fig, stats, badge
        
        df_dev = pd.DataFrame(deviation_rows).sort_values("deviation", ascending=False)
        
        color_map = {"BOOMING": "#4ECDC4", "DECLINING": "#FF6B9D", "STABLE": "#95A5A6"}
        # Sortiere nach absoluter Abweichung (stärkste Ausschläge oben)
        df_dev = df_dev.reindex(df_dev['deviation'].abs().sort_values(ascending=False).index)
        
        colors = [color_map[s] for s in df_dev["status"]]
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=df_dev['genre'], 
            x=df_dev['deviation'], 
            orientation='h', 
            marker_color=colors,
            opacity=0.9,
            customdata=df_dev[['historical_share', 'current_share', 'status']].values,
            hovertemplate=(
                "Genre: %{y}<br>" +
                "Aktuell: %{customdata[1]:.1f}%<br>" +
                "Historisch: %{customdata[0]:.1f}%<br>" +
                "Abweichung: %{x:.1f} Prozentpunkte<br>" +
                "Status: %{customdata[2]}<extra></extra>"
            )
        ))
        
        fig.update_layout(
            template='plotly_dark', 
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(15,20,30,0.9)',
            title=(
                '<b>Live Genre Trend-Analyse (Spotify + Last.fm Validation)</b><br>' +
                '<i>Aktuelle vs. historische Popularitätsverteilung 2017–2021</i>'
            ),
            xaxis_title='Abweichung (Prozentpunkte ggü. 2017–2021)',
            yaxis_title='Musikgenre',
            height=400, 
            showlegend=False, 
            margin=dict(l=60, r=60, t=90, b=60),
            transition_duration=500
        )
        fig.update_xaxes(range=[-50, 60], zeroline=False)  # Fixierte X-Achse verhindert Verspringen
        fig.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.5)
        
        deviation_index = df_dev['deviation'].abs().mean()
        booming = df_dev[df_dev['status'] == 'BOOMING']
        top_boom = booming.iloc[0]['genre'] if len(booming) > 0 else "Keines"
        top_boom_val = booming.iloc[0]['deviation'] if len(booming) > 0 else 0
        
        declining = df_dev[df_dev['status'] == 'DECLINING'].nsmallest(1, 'deviation')
        top_decl = declining.iloc[0]['genre'] if len(declining) > 0 else "Keines"
        top_decl_val = declining.iloc[0]['deviation'] if len(declining) > 0 else 0
        
        stats = html.Div([
            html.Span(f"Deviation Index: {deviation_index:.1f}%", className="val-pill", style=get_pill_style()),
            html.Span(f"Top Booming: {top_boom} (+{top_boom_val:.1f}%)", className="val-pill", style=get_pill_style('booming')),
            html.Span(f"Top Declining: {top_decl} ({top_decl_val:+.1f}%)", className="val-pill", style=get_pill_style('declining')),
        ], style={'display': 'flex', 'gap': '10px', 'flexWrap': 'wrap', 'marginTop': '15px'})
        
        market_labels = {'DE': 'Deutschland', 'UK': 'UK', 'BR': 'Brasilien'}
        badge = " + ".join([market_labels.get(m, m) for m in sorted(markets)]) if len(markets) <= 2 else "Alle Märkte"
        return fig, stats, badge
        
    except Exception as e:
        print(f"Fehler in Genre Deviation: {e}")
        import traceback
        traceback.print_exc()
        fig = go.Figure()
        fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', title="Fehler", height=400)
        return fig, html.Div("Fehler", className="val-pill", style={'background': 'rgba(255, 107, 157, 0.2)', 'color': '#FF6B9D', 'border': '1px solid #FF6B9D'}), ""

# Server-Variable für Render Deployment

# Expose server for Gunicorn
server = app.server

if __name__ == '__main__':
    print("\nDashboard: http://127.0.0.1:8050")
    print("="*70 + "\n")
    
    # Use PORT environment variable for Render, fallback to 8050 for local
    port = int(os.environ.get('PORT', 8050))
    app.run_server(debug=False, host='0.0.0.0', port=port)
