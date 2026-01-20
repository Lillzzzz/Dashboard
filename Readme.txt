Business Intelligence and Analytics - Dashboard Spotify Performance Insights

Projektübersicht:
Dieses Dashboard habe ich im Rahmen des Kurses "Business Intelligence and Analytics" entwickelt. Es soll A&R-Manager bei der Bewertung von Musikmärkten unterstützen, indem es Genre-Trends und Audio-Features in drei internationalen Märkten analysiert.

Live-Dashboard: https://dashboard-d0z8.onrender.com


Zielsetzung:
Das Dashboard verfolgt drei konkrete Ziele:
- Reduktion des manuellen Analyseaufwands durch automatisierte Datenaufbereitung und Visualisierung.
- Identifikation marktspezifischer Genre-Schwerpunkte und Erfolgsmuster zur Unterstützung von A&R- und Marketingentscheidungen.
- Optionale Kontextualisierung kurzfristiger Streaming-Impulse über Spotify- und Last.fm-APIs (nicht Bestandteil der historischen KPI-Berechnung).

Analysierte Märkte: Deutschland, UK, Brasilien (2017-2021)


Installation:
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
   
   SPOTIFY_CLIENT_ID=spotify_client_id
   SPOTIFY_CLIENT_SECRET=spotify_client_secret
   LASTFM_API_KEY=lastfm_api_key
   
   ENtsprechende Keys können hier erstellt werden:
   - Spotify: https://developer.spotify.com/dashboard
   - Last.fm: https://www.last.fm/api/account/create


Projektstruktur
---------------
Dashboard/
	dashboard.py              # Dashboard
	datenverarbeitung.py      # ETL-Pipeline  
	config.json               # Konfiguration
	requirements.txt          # Dependencies
	.env                      # API-Keys (nicht im Repo)

	Verzeichnis: data/
		cleaned_charts_kpi.csv
		cleaned_market_trends.csv
		high_potential_tracks.csv
		genre_mapping.json
		data_journal.csv
	
	Verzeichnis: assets/
  		styles.css


Ausführung:

Datenverarbeitung starten:
- python datenverarbeitung.py

Das Skript erstellt vier Ausgabe-Dateien:
- cleaned_charts_kpi.csv
- spotify_charts_enhanced.csv
- high_potential_tracks.csv 
- cleaned_market_trends.csv

Zusätzlich wird data_journal.csv mit allen 23 Verarbeitungsschritten generiert.

Dashboard starten:
- python dashboard.py

Das Dashboard läuft dann auf http://localhost:8050


Datenquellen:
Für das Projekt habe ich verschiedene Datenquellen kombiniert:

- Spotify Charts Dataset: Tägliche Chart-Positionen 2017-2021 
  (26,2 Millionen Zeilen)
- Spotify Audio Features Dataset: Technische Song-Eigenschaften wie 
  Danceability, Energy, Tempo für 114.000 Tracks
- Final Database: Artist-Informationen und Follower-Zahlen 
  (170.000 Einträge)
- Spotify API: Live-Daten für aktuelle Top-Tracks
- Last.fm API: Nutzer-basierte Genre-Trends zur Validierung


Datenbereinigung:
Der ETL-Prozess in datenverarbeitung.py läuft komplett automatisch:

1. Laden der drei Kaggle-Datasets
2. Filterung auf Deutschland, UK und Brasilien  
3. Zeitliche Eingrenzung auf 2017-2021
4. Entfernung von Duplikaten
5. Imputation fehlender Stream-Werte mit Median pro Markt
6. Genre-Harmonisierung (Auf 9 Hauptkategorien reduziert)
7. Berechnung eines Success Scores aus mehreren Faktoren
8. Aggregation zu KPI-Metriken

Die Genre-Standardisierung ist in genre_mapping.json definiert. Beispielsweise werden "hip hop", "rap", "trap" und "deutschrap" alle als "Hip-Hop" klassifiziert.

Alle Verarbeitungsschritte sind in data_journal.csv dokumentiert.
Die ETL-Pipeline ist deterministisch implementiert, sodass bei identischen Eingabedaten identische Ausgabe-Dateien erzeugt werden.


Visualisierungen:
Das Dashboard enthält acht verschiedene Visualisierungen:

1. Zeitliche Entwicklung der Marktanteile (Liniendiagramm)
2. Genre-Diversität nach Shannon-Index  
3. Korrelation zwischen Audio-Features (Heatmap)
4. Zusammenhang zwischen Audio-Features und Erfolg (Scatter Plot)
5. Top 20 Tracks mit hohem Potenzial (Ranking)
6. Verteilung der Success Scores (Histogramm)
7. Live Top-Tracks via Spotify API
8. Last.fm Genre-Trends


Zentrale Erkenntnisse:

Aus der Analyse ergeben sich mehrere zentrale Muster:

- Die drei betrachteten Märkte (Deutschland, UK, Brasilien) unterscheiden sich deutlich in ihren Genre-Strukturen.
- Die Shannon-Diversität liegt in allen Märkten im Bereich von ca. 1,27–1,40 und weist auf insgesamt konzentrierte Märkte mit wenigen dominanten Genres hin.
- Brasilien zeigt im Zeitverlauf einen Aufwärtstrend in den Marktverläufen, während der UK-Markt relativ an Anteil verliert.
- Audio-Features wie Danceability und Energy zeigen Zusammenhänge mit Erfolg, erklären diesen jedoch nur begrenzt und nicht kausal.


Technischer Stack:
Backend: Python 3.x mit Pandas und NumPy
Dashboard: Dash 2.18 und Plotly 5.24
Styling: Custom CSS mit Dash Bootstrap Components  
Deployment: Render.com mit Gunicorn
APIs: Spotify Web API und Last.fm API


Deployment auf Render:
Das Dashboard läuft auf Render.com mit folgender Konfiguration:

Build Command: pip install -r requirements.txt
Start Command: gunicorn dashboard:server --bind 0.0.0.0:$PORT --workers 1 --timeout 120
Instance Type: Standard (2 GB RAM, 1 CPU)

Die Environment Variables müssen in den Render-Einstellungen gesetzt werden.

Hinweis zur großen Datei: Die spotify_charts_enhanced.csv (309 MB) konnte nicht direkt auf GitHub hochgeladen werden wegen der 25 MB Größenbeschränkung. Sie liegt deshalb als GitHub Release und wird beim Dashboard-Start automatisch heruntergeladen.


Reproduzierbarkeit:
Die folgenden Schritte beziehen sich auf den aktuellen Stand des GitHub-Repositories (Branch: main).
Das Projekt kann in vier Schritten vollständig reproduziert werden:

1. Repository klonen:
   git clone https://github.com/Lillzzzz/Dashboard.git
   cd Dashboard

2. Python-Umgebung einrichten:
   python -m venv venv
   source venv/bin/activate  (Windows: venv\Scripts\activate)
   pip install -r requirements.txt

3. API-Keys konfigurieren (nur für Live-Daten erforderlich):
   Erstelle eine .env Datei im Hauptverzeichnis mit:
   SPOTIFY_CLIENT_ID=your_spotify_id
   SPOTIFY_CLIENT_SECRET=your_spotify_secret
   LASTFM_API_KEY=your_lastfm_key

   Hinweis: Das Dashboard funktioniert auch ohne API-Keys (Fallback auf lokale Daten).
   Die Live-API-Komponenten dienen ausschließlich der optionalen Kontextualisierung und sind nicht Bestandteil der historischen Analyse oder der KPI-Berechnung.


4. Dashboard starten:
   python dashboard.py
   Öffne anschließend http://localhost:8050

Hinweis: datenverarbeitung.py muss nur ausgeführt werden, wenn die CSV-Dateien neu generiert werden sollen
(die vorbereiteten CSV-Dateien sind bereits enthalten).


Dokumentation:
Zusätzlich zum Code gibt es folgende Dokumentation:

- Report: Dashboard Spotify Performance Insights Report.pdf
- Data Journal: data_journal.csv
- Genre-Mapping: genre_mapping.json
- Config: config.json
