SPOTIFY A&R MARKET INTELLIGENCE DASHBOARD
==========================================

Projektübersicht
----------------
Dieses Dashboard habe ich im Rahmen des Moduls "Business Intelligence & Analytics" 
entwickelt. Es soll A&R-Manager bei der Bewertung von Musikmärkten unterstützen, 
indem es Genre-Trends und Audio-Features in drei internationalen Märkten analysiert.

Live-Dashboard: https://dashboard-d0z8.onrender.com

Zielsetzung
-----------
Das Dashboard verfolgt drei konkrete Ziele:
- Reduktion der Analysezeit für Genre-Performance von mehreren Tagen auf wenige Minuten
- Identifikation unterschätzter Genres mit hohem ROI-Potenzial  
- Reaktionszeit unter 24 Stunden auf virale Trends durch Echtzeit-Datenintegration

Analysierte Märkte: Deutschland, Vereinigtes Königreich, Brasilien (2017-2021)

Installation
------------
Das Projekt kann lokal ausgeführt werden:

1. Repository klonen:
   git clone https://github.com/Lillzzzz/Dashboard.git
   cd Dashboard

2. Python-Umgebung einrichten:
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

3. API-Keys konfigurieren:
   Eine .env Datei im Hauptverzeichnis erstellen mit:
   
   SPOTIFY_CLIENT_ID=deine_spotify_client_id
   SPOTIFY_CLIENT_SECRET=dein_spotify_client_secret
   LASTFM_API_KEY=dein_lastfm_api_key
   
   Keys können hier erstellt werden:
   - Spotify: https://developer.spotify.com/dashboard
   - Last.fm: https://www.last.fm/api/account/create

Projektstruktur
---------------
Dashboard/
├── dashboard.py              # Hauptdashboard
├── datenverarbeitung.py      # ETL-Pipeline  
├── config.json               # Konfiguration
├── requirements.txt          # Dependencies
├── .env                      # API-Keys (nicht im Repo)
├── data/
│   ├── cleaned_charts_kpi.csv
│   ├── cleaned_market_trends.csv
│   ├── high_potential_tracks.csv
│   ├── genre_mapping.json
│   └── data_journal.csv
└── assets/
    └── styles.css

Ausführung
----------
Datenverarbeitung starten:
   python datenverarbeitung.py

Das Skript erstellt vier Ausgabe-Dateien:
- cleaned_charts_kpi.csv (128 Zeilen)
- spotify_charts_enhanced.csv (1,25 Millionen Zeilen)
- high_potential_tracks.csv (14.490 Zeilen)  
- cleaned_market_trends.csv (15 Zeilen)

Zusätzlich wird data_journal.csv mit allen 23 Verarbeitungsschritten generiert.

Dashboard starten:
   python dashboard.py

Das Dashboard läuft dann auf http://localhost:8050

Datenquellen
------------
Für das Projekt habe ich verschiedene Datenquellen kombiniert:

- Spotify Charts Dataset: Tägliche Chart-Positionen 2017-2021 
  (ursprünglich 26,2 Millionen Zeilen, gefiltert auf 1,25 Millionen)
  
- Spotify Audio Features Dataset: Technische Song-Eigenschaften wie 
  Danceability, Energy, Tempo für 114.000 Tracks
  
- Final Database: Artist-Informationen und Follower-Zahlen 
  (170.000 Einträge)
  
- Spotify API: Live-Daten für aktuelle Top-Tracks

- Last.fm API: Nutzer-basierte Genre-Trends zur Validierung

Datenbereinigung
----------------
Der ETL-Prozess in datenverarbeitung.py läuft komplett automatisch:

1. Laden der drei Kaggle-Datasets
2. Filterung auf Deutschland, UK und Brasilien  
3. Zeitliche Eingrenzung auf 2017-2021
4. Entfernung von 100.000 Duplikaten
5. Imputation fehlender Stream-Werte mit Median pro Markt
6. Genre-Harmonisierung (60 Schreibweisen auf 9 Hauptkategorien reduziert)
7. Berechnung eines Success Scores aus mehreren Faktoren
8. Aggregation zu KPI-Metriken

Die Genre-Standardisierung ist in genre_mapping.json definiert. Beispielsweise 
werden "hip hop", "rap", "trap" und "deutschrap" alle als "Hip-Hop" klassifiziert.

Alle Verarbeitungsschritte sind in data_journal.csv dokumentiert.

Visualisierungen
----------------
Das Dashboard enthält acht verschiedene Visualisierungen:

1. Marktanteile und Wachstumsdynamik (Liniendiagramm)
2. Genre-Diversität nach Shannon-Index  
3. Korrelation zwischen Audio-Features (Heatmap)
4. Zusammenhang zwischen Audio-Features und Erfolg (Scatter Plot)
5. Top 20 Tracks mit hohem Potenzial (Ranking)
6. Verteilung der Success Scores (Histogramm)
7. Live Top-Tracks via Spotify API
8. Last.fm Genre-Trends

Zentrale Erkenntnisse
---------------------
Aus der Analyse ergeben sich mehrere interessante Muster:

- Tracks mit mittleren Werten bei Danceability und Energy (0,6-0,8) 
  sind kommerziell am erfolgreichsten
  
- Der UK-Markt zeigt die höchste Genre-Diversität

- In Brasilien wächst Electronic besonders stark

- Energy und Danceability korrelieren stark positiv (r = 0,74)

- Die Top 5% der Tracks generieren über 80% aller Streams

Technischer Stack
-----------------
Backend: Python 3.13 mit Pandas und NumPy
Dashboard: Dash 2.18 und Plotly 5.24
Styling: Custom CSS mit Dash Bootstrap Components  
Deployment: Render.com mit Gunicorn
APIs: Spotify Web API und Last.fm API

Deployment auf Render
----------------------
Das Dashboard läuft auf Render.com mit folgender Konfiguration:

Build Command: pip install -r requirements.txt
Start Command: gunicorn dashboard:server --bind 0.0.0.0:$PORT --workers 1 --timeout 120
Instance Type: Standard (2 GB RAM, 1 CPU)

Die Environment Variables müssen in den Render-Einstellungen gesetzt werden.

Hinweis zur großen Datei: Die spotify_charts_enhanced.csv (309 MB) konnte nicht 
direkt auf GitHub hochgeladen werden wegen der 25 MB Größenbeschränkung. Sie liegt 
deshalb als GitHub Release und wird beim Dashboard-Start automatisch heruntergeladen.

Reproduzierbarkeit
------------------
Das Projekt kann in drei Schritten vollständig reproduziert werden:

1. Repository klonen und Dependencies installieren
2. .env Datei mit API-Keys erstellen  
3. datenverarbeitung.py und dashboard.py ausführen

Das Dashboard sollte dann auf localhost:8050 laufen und alle CSV-Dateien 
sollten im data/ Ordner erstellt werden.

Dokumentation
-------------
Zusätzlich zum Code gibt es folgende Dokumentation:

- Report: BI_Dashboard_Report.docx (5 Seiten)
- Data Journal: data/data_journal.csv (23 Schritte)
- Genre-Mapping: data/genre_mapping.json
- Config: config.json

Kontakt
-------
Lilly C.
Master Marketing
Hochschule Macromedia
Januar 2026
