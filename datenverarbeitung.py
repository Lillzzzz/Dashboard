
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
from datetime import datetime
import json

warnings.filterwarnings('ignore')

# KONFIGURATION

CONFIG_PATH = Path("config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

MARKETS = CONFIG["markets"]
MIN_YEAR = CONFIG["min_year"]
MAX_YEAR = CONFIG["max_year"]
PATHS = CONFIG["paths"]
OUTPUT_DIR = Path(PATHS["output_folder"])
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = OUTPUT_DIR
MARKET_CODES = {"Germany": "DE", "United Kingdom": "UK", "Brazil": "BR"}

# Genre Mapping aus JSON laden (falls vorhanden) oder als Fallback hardcoded
genre_mapping_path = Path(PATHS["genre_mapping"])
if genre_mapping_path.exists():
    with open(genre_mapping_path, "r", encoding="utf-8") as f:
        GENRE_MAPPING = json.load(f)
else:
    GENRE_MAPPING = {
        "pop": "Pop", "dance pop": "Pop", "electropop": "Pop", "indie pop": "Pop",
        "synth-pop": "Pop", "teen pop": "Pop", "k-pop": "Pop", "latin pop": "Pop",
        "hip hop": "Hip-Hop", "rap": "Hip-Hop", "trap": "Hip-Hop", "cloud rap": "Hip-Hop",
        "emo rap": "Hip-Hop", "gangster rap": "Hip-Hop", "german hip hop": "Hip-Hop",
        "dfw rap": "Hip-Hop", "deep german hip hop": "Hip-Hop",
        "edm": "Electronic", "electronic": "Electronic", "house": "Electronic",
        "techno": "Electronic", "dubstep": "Electronic", "trance": "Electronic",
        "deep house": "Electronic", "progressive house": "Electronic", "big room": "Electronic",
        "rock": "Rock", "alternative rock": "Rock", "indie rock": "Rock",
        "hard rock": "Rock", "punk rock": "Rock", "classic rock": "Rock",
        "r&b": "R&B", "r & b": "R&B", "soul": "R&B", "neo soul": "R&B",
        "latin": "Latin", "reggaeton": "Latin", "bachata": "Latin", "salsa": "Latin",
        "sertanejo": "Latin", "funk carioca": "Latin", "forro": "Latin",
        "country": "Country", "country pop": "Country", "bluegrass": "Country",
        "jazz": "Jazz", "bebop": "Jazz", "smooth jazz": "Jazz"
    }

# DATA JOURNAL TRACKING

JOURNAL_LOG = []

def log_step(step_num, action, source, target, description, rows_before=None, rows_after=None, extra_info=None):
    """Protokolliert einen Verarbeitungsschritt für das Data Journal"""
    timestamp = datetime.utcnow().isoformat() + "Z"
    rows_removed = None
    if rows_before is not None and rows_after is not None:
        rows_removed = rows_before - rows_after
    
    JOURNAL_LOG.append({
        'step': step_num,
        'timestamp': timestamp,
        'action': action,
        'source': source if source else '',
        'target': target if target else '',
        'description': description,
        'rows_before': rows_before if rows_before is not None else '',
        'rows_after': rows_after if rows_after is not None else '',
        'rows_removed': rows_removed if rows_removed is not None else '',
        'extra_info': extra_info if extra_info else ''
    })

def save_journal():
    """Speichert das Data Journal als CSV"""
    journal_df = pd.DataFrame(JOURNAL_LOG)
    journal_path = OUTPUT_DIR / "data_journal.csv"
    journal_df.to_csv(journal_path, index=False, encoding='utf-8-sig')
    print(f"\n📝 Data Journal: {journal_path} ({len(JOURNAL_LOG)} Schritte)")

# HILFSFUNKTIONEN

def print_section(title):
    print(f"\n{'='*80}\n  {title}\n{'='*80}")

def clean_numeric_column(series, col_name, clip_min=None, clip_max=None):
    """Bereinigt numerische Spalte von korrupten Werten"""
    clean_series = pd.to_numeric(series, errors='coerce')
    
    if clip_min is not None and clip_max is not None:
        clean_series = clean_series.clip(clip_min, clip_max)
    elif clip_min is not None:
        clean_series = clean_series.clip(lower=clip_min)
    
    corrupt_count = series.notna().sum() - clean_series.notna().sum()
    if corrupt_count > 0:
        print(f"   ⚠️ {col_name}: {corrupt_count} korrupte Werte bereinigt")
    
    return clean_series

def harmonize_genre(genre_str):
    """Mappt Genres auf Hauptkategorien"""
    if pd.isna(genre_str):
        return "Other"
    genre_lower = str(genre_str).lower().strip()
    if genre_lower in GENRE_MAPPING:
        return GENRE_MAPPING[genre_lower]
    for key, category in GENRE_MAPPING.items():
        if key in genre_lower:
            return category
    return "Other"

def calculate_shannon_diversity(series):
    """
    Shannon-Diversität (Shannon-Wiener Index) für Genre-Vielfalt.
    
    FORMEL: H = -Σ(p_i * ln(p_i))
    - p_i = Anteil Genre i (z.B. 0.35 für 35% Pop)
    - ln = natürlicher Logarithmus
    - Σ = Summe über alle Genres
    
    INTERPRETATION:
    - H = 0.0: Nur ein Genre (keine Vielfalt)
    - H = 1.0-1.5: 1-2 Genres dominieren (z.B. 60% Pop, 30% Hip-Hop)
    - H = 1.5-2.0: Mehrere relevante Genres (typisch für Musikmärkte)
    - H > 2.0: Viele Genres gleichverteilt
    
    BEISPIEL:
    ['Pop', 'Pop', 'Pop', 'Hip-Hop', 'Rock']
    → Pop: 60%, Hip-Hop: 20%, Rock: 20%
    → H = -(0.6*ln(0.6) + 0.2*ln(0.2) + 0.2*ln(0.2)) ≈ 0.95
    
    1e-12 verhindert log(0) Fehler bei Genres mit 0%.
    """
    counts = series.value_counts()
    proportions = counts / counts.sum()
    shannon = -np.sum(proportions * np.log(proportions + 1e-12))
    return shannon

def calculate_success_score(df):
    """Berechnet Success-Score (0-100)"""
    scores = pd.Series(0.0, index=df.index)
    
    if 'rank' in df.columns:
        rank_clean = clean_numeric_column(df['rank'], 'rank', clip_min=1, clip_max=200)
        rank_score = (200 - rank_clean) / 200 * 100
        scores += rank_score.fillna(0) * 0.25
    
    if 'streams' in df.columns:
        streams_clean = clean_numeric_column(df['streams'], 'streams', clip_min=0)
        streams_log = np.log1p(streams_clean.fillna(0))
        if streams_log.max() > 0:
            streams_score = (streams_log / streams_log.max()) * 100
            scores += streams_score * 0.15
    
    if 'danceability' in df.columns:
        dance_clean = clean_numeric_column(df['danceability'], 'danceability', clip_min=0, clip_max=1)
        scores += dance_clean.fillna(0) * 100 * 0.15
    
    if 'energy' in df.columns:
        energy_clean = clean_numeric_column(df['energy'], 'energy', clip_min=0, clip_max=1)
        scores += energy_clean.fillna(0) * 100 * 0.15
    
    if 'Artist_followers' in df.columns:
        followers_clean = clean_numeric_column(df['Artist_followers'], 'Artist_followers', clip_min=0)
        followers_log = np.log1p(followers_clean.fillna(0))
        if followers_log.max() > 0:
            followers_score = (followers_log / followers_log.max()) * 100
            scores += followers_score * 0.20
    
    if 'Top10_dummy' in df.columns:
        top10_clean = clean_numeric_column(df['Top10_dummy'], 'Top10_dummy', clip_min=0, clip_max=1)
        scores += top10_clean.fillna(0) * 100 * 0.10
    
    return scores

def validate_kpi_output(kpi_df, min_year):
    """
    Validiert KPI-DataFrame vor Export
    
    KRITISCHE CHECKS:
    1. Keine Duplikate auf (market, year, genre_harmonized)
    2. Market-Share summiert zu ~100% pro (market, year)
    3. index_growth_2017_2021 hat mehr als 1 unique value
    
    Returns: (is_valid, error_messages)
    """
    errors = []
    
    # CHECK 1: Duplikate
    dup_check = kpi_df.groupby(['market', 'year', 'genre_harmonized']).size()
    duplicates = dup_check[dup_check > 1]
    if len(duplicates) > 0:
        errors.append(f"❌ DUPLIKATE: {len(duplicates)} doppelte (market, year, genre) Kombinationen gefunden!")
        print(f"\n   FEHLER: Duplikate in KPI:\n{duplicates.head()}")
    
    # CHECK 2: Market Share Summen
    share_sums = kpi_df.groupby(['market', 'year'])['market_share_percent'].sum().reset_index()
    bad_sums = share_sums[(share_sums['market_share_percent'] < 99.8) | (share_sums['market_share_percent'] > 100.2)]
    if len(bad_sums) > 0:
        errors.append(f"❌ MARKET SHARE: {len(bad_sums)} (market, year) haben falsche Summen (≠100%)!")
        print(f"\n   FEHLER: Market Share Summen:\n{bad_sums}")
    
    # CHECK 3: Index Growth nicht konstant 100
    unique_values = kpi_df['index_growth_2017_2021'].nunique()
    if unique_values <= 1:
        errors.append(f"❌ INDEX GROWTH: Nur {unique_values} unique Werte - wahrscheinlich Bug!")
        print(f"\n   FEHLER: index_growth_2017_2021 hat nur Wert: {kpi_df['index_growth_2017_2021'].unique()}")
    
    # Baseline-Check: Min year sollte immer 100 sein
    baseline_data = kpi_df[kpi_df['year'] == min_year]
    if len(baseline_data) > 0:
        non_100 = baseline_data[baseline_data['index_growth_2017_2021'] != 100.0]
        if len(non_100) > 0:
            errors.append(f"⚠️ WARNING: {len(non_100)} Baseline-Zeilen (year={min_year}) haben index ≠ 100!")
    
    # CHECK 4: Market Potential Score Range
    mps_stats = kpi_df['market_potential_score'].describe()
    if mps_stats['max'] > 150:
        errors.append(f"⚠️ WARNING: market_potential_score max={mps_stats['max']:.1f} - sehr hoch, prüfen!")
        print(f"\n   WARNING: Market Potential Score Stats:\n{mps_stats}")
    
    return len(errors) == 0, errors

# HAUPTLOGIK

def main():
    step_counter = 1
    min_year = MIN_YEAR
    
    print(f"\n{'='*80}")
    print(f"  🎵 DATENVERARBEITUNG SPOTIFY CHARTS (VERBESSERT)")
    print(f"{'='*80}")
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Märkte: {', '.join(MARKETS)}")
    print(f"Jahre: {min_year}-{MAX_YEAR}")
    print(f"Output: {OUTPUT_DIR.resolve()}")
    
    # 1: CHARTS LADEN
    print_section("1: CHARTS LADEN")
    
    try:
        charts = pd.read_csv(PATHS["raw_charts"], low_memory=False)
        log_step(step_counter, 'load', Path(PATHS["raw_charts"]).name, 'charts',
                 'Initiales Laden der Spotify Charts-Daten mit allen verfügbaren Zeilen und Spalten.',
                 rows_after=len(charts))
        step_counter += 1
        print(f"   ✅ charts.csv: {len(charts):,} Zeilen")
    except FileNotFoundError:
        raise FileNotFoundError("charts.csv nicht gefunden!")
    
    # Charts bereinigen - Date/Year/Region
    charts['date'] = pd.to_datetime(charts['date'], errors='coerce')
    charts['year'] = charts['date'].dt.year
    
    rows_before = len(charts)
    charts['region'] = charts['region'].str.strip()
    charts = charts[charts['region'].isin(MARKETS)].copy()
    log_step(step_counter, 'filter', 'charts', 'charts',
             f'Filterung auf definierte Märkte: {", ".join(MARKETS)}. Nur Datensätze aus diesen Regionen werden beibehalten.',
             rows_before=rows_before, rows_after=len(charts),
             extra_info=f'Filter: region in {MARKETS}')
    step_counter += 1
    
    charts['market'] = charts['region'].map(MARKET_CODES)
    
    rows_before = len(charts)
    charts = charts[charts['year'].between(min_year, MAX_YEAR)]
    log_step(step_counter, 'filter', 'charts', 'charts',
             f'Zeitliche Filterung auf Analysezeitraum {min_year}-{MAX_YEAR}. Frühere und spätere Daten werden ausgeschlossen.',
             rows_before=rows_before, rows_after=len(charts),
             extra_info=f'Filter: year between {min_year} and {MAX_YEAR}')
    step_counter += 1
    
    # Numerische Bereinigung
    charts['streams'] = clean_numeric_column(charts['streams'], 'streams', clip_min=0)
    if 'rank' in charts.columns:
        charts['rank'] = clean_numeric_column(charts['rank'], 'rank', clip_min=1, clip_max=200)
    
    # Track-ID extrahieren
    charts['track_id'] = charts['url'].str.extract(r'track/([A-Za-z0-9]+)', expand=False)
    log_step(step_counter, 'feature_engineering', 'charts', 'charts',
             'Track-ID aus der Spotify-URL gezogen (Regex), für sauberes mergen.',
             rows_before=len(charts), rows_after=len(charts),
             extra_info='Pattern: track/([A-Za-z0-9]+)')
    step_counter += 1
    
    # Duplikate entfernen
    rows_before = len(charts)
    charts = charts.drop_duplicates(subset=['track_id', 'date', 'market'], keep='first')
    log_step(step_counter, 'drop_duplicates', 'charts', 'charts',
             'Entfernung exakter Duplikate basierend auf Track-ID, Datum und Markt. Sichert eindeutige Chart-Einträge pro Tag/Markt.',
             rows_before=rows_before, rows_after=len(charts),
             extra_info='Keys: track_id, date, market')
    step_counter += 1
    
    # Streams imputation
    for (year, market), group in charts.groupby(['year', 'market']):
        median_streams = group['streams'].median()
        if pd.notna(median_streams) and median_streams > 0:
            mask = (charts['year'] == year) & (charts['market'] == market) & (charts['streams'].isna())
            charts.loc[mask, 'streams'] = median_streams
    
    log_step(step_counter, 'imputation', 'charts', 'charts',
             'Fehlende Streams: Median je Jahr×Markt eingesetzt (einfacher Fallback).',
             rows_before=len(charts), rows_after=len(charts),
             extra_info='Method: Median imputation grouped by year × market')
    step_counter += 1
    
    # Finale Bereinigung
    rows_before = len(charts)
    charts = charts.dropna(subset=['track_id', 'date', 'market'])
    charts = charts[charts['streams'] > 0]
    log_step(step_counter, 'clean_nulls', 'charts', 'charts',
             'Finale Bereinigung: Entfernung von Datensätzen mit fehlenden essentiellen Feldern und Streams <= 0.',
             rows_before=rows_before, rows_after=len(charts),
             extra_info='Dropped: track_id/date/market is NULL OR streams <= 0')
    step_counter += 1
    
    print(f"\n   Nach Bereinigung: {len(charts):,} Zeilen")
    
    # 2: FINAL DATABASE & DATASET LADEN
    print_section("2: AUDIO FEATURES & DATABASE LADEN")
    
    try:
        final_db = pd.read_csv(PATHS["raw_database"], low_memory=False)
        log_step(step_counter, 'load', Path(PATHS["raw_database"]).name, 'final_db',
                 'Laden der finalen Datenbank mit ergänzenden Track-Informationen und Metadaten.',
                 rows_after=len(final_db))
        step_counter += 1
        print(f"   ✅ Final database.csv: {len(final_db):,} Zeilen")
    except FileNotFoundError:
        print("   ⚠️ WARNUNG: Final database.csv nicht gefunden")
        final_db = pd.DataFrame()
    
    try:
        dataset = pd.read_csv(PATHS["raw_spotify"], low_memory=False)
        log_step(step_counter, 'load', Path(PATHS["raw_spotify"]).name, 'dataset',
                 'Laden des Spotify-Datasets mit Audio-Features (Danceability, Energy, etc.).',
                 rows_after=len(dataset))
        step_counter += 1
        print(f"   ✅ dataset.csv: {len(dataset):,} Zeilen")
    except FileNotFoundError:
        print("   ⚠️ WARNUNG: dataset.csv nicht gefunden")
        dataset = pd.DataFrame()
    
    # 3: AUDIO-FEATURES VORBEREITEN
    print_section("3: AUDIO-FEATURES VORBEREITEN")
    
    # Track-ID in final_db extrahieren
    for col in ['Uri', 'uri', 'url', 'URL']:
        if col in final_db.columns:
            final_db['track_id'] = final_db[col].str.extract(r'track/([A-Za-z0-9]+)', expand=False)
            break
    
    if 'track_id' not in final_db.columns:
        print("   ⚠️ WARNUNG: Keine Track-ID in Final database")
        final_db['track_id'] = None
    
    if not dataset.empty and 'track_id' in dataset.columns:
        dataset['track_id'] = dataset['track_id'].astype(str)
    
    # Spalten umbenennen
    final_db = final_db.rename(columns={
        'acoustics': 'acousticness', 'Acoustics': 'acousticness',
        'liveliness': 'liveness', 'Liveliness': 'liveness'
    })
    
    # Audio Features extrahieren
    audio_features = ['danceability', 'energy', 'acousticness', 'valence',
                     'tempo', 'speechiness', 'instrumentalness', 'liveness']
    
    audio_cols = ['track_id']
    for col in audio_features + ['Popularity', 'Artist_followers', 'Release_date', 'Top10_dummy', 'Top50_dummy']:
        if col in final_db.columns:
            audio_cols.append(col)
    
    rows_before = len(final_db) if not final_db.empty else 0
    audio_df = final_db[audio_cols].dropna(subset=['track_id']).drop_duplicates('track_id') if not final_db.empty else pd.DataFrame()
    
    if not audio_df.empty:
        log_step(step_counter, 'clean_nulls', 'final_db', 'audio_df',
                 'Extraktion relevanter Audio-Features und Metadaten. Entfernung von Tracks ohne Track-ID und Deduplizierung.',
                 rows_before=rows_before, rows_after=len(audio_df),
                 extra_info='Columns: track_id, audio_features, metadata')
        step_counter += 1
        
        # Audio Features bereinigen
        for col in ['danceability', 'energy', 'acousticness', 'valence', 'speechiness', 'instrumentalness', 'liveness']:
            if col in audio_df.columns:
                audio_df[col] = clean_numeric_column(audio_df[col], col, clip_min=0, clip_max=1)
        
        if 'tempo' in audio_df.columns:
            audio_df['tempo'] = clean_numeric_column(audio_df['tempo'], 'tempo', clip_min=30, clip_max=250)
        
        if 'Popularity' in audio_df.columns:
            audio_df['Popularity'] = clean_numeric_column(audio_df['Popularity'], 'Popularity', clip_min=0, clip_max=100)
        
        log_step(step_counter, 'clean_numeric', 'audio_df', 'audio_df',
                 'Audio-Features in sinnvolle Bereiche gekappt (0–1, Tempo 30–250).',
                 rows_before=len(audio_df), rows_after=len(audio_df),
                 extra_info='Tempo: 30-250 BPM, Audio features: 0-1, Popularity: 0-100')
        step_counter += 1
        
        print(f"\n   Audio Features: {len(audio_df):,} Zeilen")
    else:
        print("   ⚠️ Keine Audio Features verfügbar")
    
    # 4: GENRE-MAPPING
    print_section("4: GENRE-MAPPING")
    
    genre_cols = []
    for col in ['track_id', 'Genre', 'genre']:
        if col in final_db.columns:
            genre_cols.append(col)
    
    if 'track_id' in genre_cols:
        genre_df = final_db[genre_cols].dropna(subset=['track_id']).drop_duplicates('track_id')
        genre_col = 'Genre' if 'Genre' in genre_df.columns else 'genre'
        rows_before = len(genre_df)
        genre_mapping_source = 'genre_mapping.json' if genre_mapping_path.exists() else 'hardcoded mapping'
        genre_df['genre_harmonized'] = genre_df[genre_col].apply(harmonize_genre)
        
        # Coverage-Statistik für Journal
        other_count = (genre_df['genre_harmonized'] == 'Other').sum()
        other_rate = other_count / len(genre_df) * 100 if len(genre_df) > 0 else 0
        
        log_step(step_counter, 'harmonize', genre_mapping_source, 'genre_df',
                 f'Genre-Harmonisierung über Mapping. Konsolidiert {len(GENRE_MAPPING)} Detail-Genres in Hauptkategorien für konsistente Analyse.',
                 rows_before=rows_before, rows_after=len(genre_df),
                 extra_info=f'Mapping categories: {len(set(GENRE_MAPPING.values()))} unique genres | Other-Rate: {other_rate:.1f}%')
        step_counter += 1
        print(f"\n   Genre-DataFrame: {len(genre_df):,} Zeilen")
        print(f"   Other-Rate: {other_rate:.1f}%")
    else:
        print("   ⚠️ WARNUNG: Keine Track-ID für Genre-Mapping")
        genre_df = pd.DataFrame()
    
    # 5: DATEN ZUSAMMENFÜHREN
    print_section("5: DATEN ZUSAMMENFÜHREN")
    
    rows_before = len(charts)
    merged = charts.merge(audio_df, on='track_id', how='left')
    audio_coverage = merged['track_id'].notna().sum() / len(merged) * 100 if len(merged) > 0 else 0
    
    log_step(step_counter, 'merge', 'charts + audio_df', 'merged',
             'Zusammenführung von Charts und Audio-Features via Track-ID. Ergänzt Audio-Charakteristiken und Artist Followers.',
             rows_before=rows_before, rows_after=len(merged),
             extra_info=f'Join: charts.track_id = audio_df.track_id (left join) | Coverage: {audio_coverage:.1f}%')
    step_counter += 1
    
    if not genre_df.empty:
        rows_before = len(merged)
        merged = merged.merge(genre_df[['track_id', 'genre_harmonized']], on='track_id', how='left')
        
        # Genre Coverage berechnen
        genre_coverage = (merged['genre_harmonized'].notna() & (merged['genre_harmonized'] != 'Other')).sum() / len(merged) * 100
        other_rate_merged = (merged['genre_harmonized'] == 'Other').sum() / len(merged) * 100 if len(merged) > 0 else 0
        
        log_step(step_counter, 'merge', 'merged + genre_df', 'merged',
                 'Anreicherung mit harmonisierten Genre-Informationen. Ermöglicht Genre-basierte Analysen.',
                 rows_before=rows_before, rows_after=len(merged),
                 extra_info=f'Join: merged.track_id = genre_df.track_id (left join) | Genre-Coverage: {genre_coverage:.1f}% | Other-Rate: {other_rate_merged:.1f}%')
        step_counter += 1
        merged['genre_harmonized'] = merged['genre_harmonized'].fillna('Other')
        
        # 2021 Diagnose für Journal
        if 2021 in merged['year'].unique():
            merged_2021 = merged[merged['year'] == 2021]
            other_2021 = (merged_2021['genre_harmonized'] == 'Other').sum() / len(merged_2021) * 100
            print(f"   2021 Other-Rate: {other_2021:.1f}%")
    else:
        merged['genre_harmonized'] = 'Other'
    
    print(f"\n   Merged Dataset: {len(merged):,} Zeilen")
    
    # 6: SUCCESS-SCORE
    print_section("6: SCORE BERECHNEN")
    
    merged['success_score'] = calculate_success_score(merged)
    log_step(step_counter, 'feature_engineering', 'merged', 'merged',
             'Berechnung des Success-Scores (0-100) aus Chart-Rank (25%), Streams (15%), Audio-Features (30%), Followers (20%) und Top-Placements (10%).',
             rows_before=len(merged), rows_after=len(merged),
             extra_info='Formula: weighted composite score, threshold: ≥65')
    step_counter += 1
    
    print(f"\n   Success-Score: Min={merged['success_score'].min():.2f}, Mean={merged['success_score'].mean():.2f}, Max={merged['success_score'].max():.2f}")
    
    # 7: KPI-METRIKEN
    print_section("7: KPI-METRIKEN")
    
    kpi_list = []
    
    for (year, market), group in merged.groupby(['year', 'market']):
        total_streams = group['streams'].sum()
        if total_streams == 0:
            continue
        
        genre_stats = group.groupby('genre_harmonized').agg({'streams': 'sum', 'track_id': 'count'}).reset_index()
        genre_stats['market_share_percent'] = (genre_stats['streams'] / total_streams * 100).round(2)
        shannon = calculate_shannon_diversity(group['genre_harmonized'])
        
        for _, genre_row in genre_stats.iterrows():
            genre = genre_row['genre_harmonized']
            genre_group = group[group['genre_harmonized'] == genre]
            success_rate = (genre_group['success_score'] >= 65).sum() / len(genre_group) * 100
            
            baseline_group = merged[(merged['year'] == min_year) & (merged['market'] == market) & (merged['genre_harmonized'] == genre)]
            if len(baseline_group) > 0 and year > min_year:
                baseline_streams = baseline_group['streams'].sum()
                current_streams = genre_group['streams'].sum()
                growth_momentum = (current_streams / baseline_streams * 100) if baseline_streams > 0 else 100.0
            else:
                growth_momentum = 100.0
            
            # ✅ FIX: Market Potential Score mit normalisiertem Growth (0-100 Skala)
            # Growth auf 200 cappen (= Verdoppelung) und auf 0-100 normieren
            growth_capped = min(growth_momentum, 200.0)
            growth_norm_0_100 = (growth_capped / 200.0) * 100
            
            # Alle 3 Komponenten auf gleicher Skala (0-100), Gewichte 40/30/30
            market_potential = (
                genre_row['market_share_percent'] * 0.4 +
                success_rate * 0.3 +
                growth_norm_0_100 * 0.3
            )
            
            kpi_list.append({
                'market': market, 'year': int(year), 'genre': genre, 'genre_harmonized': genre,
                'streams_total': float(genre_row['streams']), 'market_share_percent': float(genre_row['market_share_percent']),
                'index_growth_2017_2021': float(growth_momentum), 'shannon_diversity': float(round(shannon, 3)),
                'success_rate_percent': float(round(success_rate, 2)), 'market_potential_score': float(round(market_potential, 2)),
                'growth_momentum_index': float(round(growth_momentum, 2))
            })
    
    kpi_df = pd.DataFrame(kpi_list)
    log_step(step_counter, 'aggregate', 'merged', 'kpi_df',
             'Aggregation zu KPI-Metriken pro Genre, Jahr und Markt. Berechnet Marktanteile, Shannon-Diversität, Success-Rates und Growth-Momentum.',
             rows_after=len(kpi_df), extra_info=f'Grouping: year × market × genre_harmonized | Market Potential: normalized growth (capped at 200)')
    step_counter += 1
    print(f"\n   KPI-Dataset: {len(kpi_df):,} Zeilen")
    
    # 8: MARKET TRENDS
    print_section("8: MARKET TRENDS")
    
    market_trends = merged.groupby(['year', 'market'])['streams'].sum().reset_index().rename(columns={'streams': 'total_streams'})
    market_trends['market_share_percent'] = (market_trends.groupby('year')['total_streams'].transform(lambda x: x / x.sum() * 100)).round(2)
    log_step(step_counter, 'aggregate', 'merged', 'market_trends',
             'Berechnung von Markt-Trends über Zeit. Zeigt relative Marktanteile (%) der drei Regionen pro Jahr.',
             rows_after=len(market_trends), extra_info='Grouping: year × market')
    step_counter += 1
    print(f"\n   Market Trends: {len(market_trends):,} Zeilen")
    
    # 9: HIGH-POTENTIAL TRACKS
    print_section("9: HIGH-POTENTIAL TRACKS")
    
    recent_years = sorted(merged['year'].unique())[-2:]
    rows_before = len(merged)
    recent_data = merged[merged['year'].isin(recent_years)].copy()
    log_step(step_counter, 'filter', 'merged', 'recent_data',
             f'Filterung auf die letzten zwei Jahre ({recent_years[0]}, {recent_years[1]}) zur Identifikation aktueller High-Potential Tracks.',
             rows_before=rows_before, rows_after=len(recent_data), extra_info=f'Filter: year in {recent_years}')
    step_counter += 1
    
    high_potential = recent_data.groupby(['track_id', 'market']).agg({
        'streams': 'sum', 'rank': 'mean', 'title': 'first', 'artist': 'first', 'genre_harmonized': 'first',
        'year': 'max', 'success_score': 'mean', 'danceability': 'first', 'energy': 'first', 'valence': 'first'
    }).reset_index().rename(columns={'title': 'track_name', 'streams': 'total_streams'})
    
    rows_before = len(high_potential)
    high_potential = high_potential[high_potential['total_streams'] >= 1000]
    log_step(step_counter, 'filter', 'recent_data', 'high_potential',
             'Aggregation und Filterung auf High-Potential Tracks. Mindestens 1000 Streams erforderlich für Relevanz.',
             rows_before=rows_before, rows_after=len(high_potential), extra_info='Filter: total_streams >= 1000')
    step_counter += 1
    
    high_potential = high_potential.sort_values('success_score', ascending=False)
    print(f"\n   High-Potential Tracks: {len(high_potential):,}")
    
    # ✅ VALIDIERUNG VOR EXPORT
    print_section("10: VALIDIERUNG")
    
    is_valid, validation_errors = validate_kpi_output(kpi_df, min_year)
    
    if not is_valid:
        print("\n❌ VALIDIERUNG FEHLGESCHLAGEN:")
        for error in validation_errors:
            print(f"   {error}")
        print("\n⚠️ Export wird NICHT durchgeführt - bitte Fehler beheben!")
        return
    else:
        print("\n✅ Alle Validierungen bestanden!")
    
    # 11: EXPORT
    print_section("11: DATEN EXPORTIEREN")
    
    outputs = {
        'cleaned_charts_kpi.csv': kpi_df,
        'spotify_charts_enhanced.csv': merged,
        'high_potential_tracks.csv': high_potential,
        'cleaned_market_trends.csv': market_trends
    }
    
    print(f"\n💾 Speichere nach: {OUTPUT_DIR.resolve()}\n")
    
    for filename, df in outputs.items():
        filepath = OUTPUT_DIR / filename
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        log_step(step_counter, 'export', 'DataFrame', filename,
                 f'Export der bereinigten und aggregierten Daten. Datei enthält {len(df)} Zeilen und {len(df.columns)} Spalten für Dashboard-Nutzung.',
                 rows_after=len(df), extra_info=f'Format: CSV (UTF-8 with BOM), Columns: {len(df.columns)}')
        step_counter += 1
        
        size_kb = filepath.stat().st_size / 1024
        size_mb = size_kb / 1024
        size_str = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{size_kb:.1f} KB"
        print(f"   ✅ {filename:40s} │ {len(df):8,} Zeilen │ {size_str:>10}")
    
    save_journal()
    
    print_section("✅ AUFBEREITUNG ABGESCHLOSSEN")
    print(f"Ende: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ FEHLER: {e}")
        import traceback
        traceback.print_exc()
