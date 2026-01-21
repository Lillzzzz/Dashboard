Business Intelligence and Analytics - Dashboard Spotify Performance Insights

Projektübersicht:
Dieses Dashboard habe ich im Rahmen des Kurses "Business Intelligence and Analytics" entwickelt. Ziel war es, A&R-Manager bei Marktanalysen zu unterstützen – mit besonderem Fokus auf Genre-Trends und Audio-Features in drei Märkten: Deutschland, UK und Brasilien (2017-2021).

Die Entwicklung hat etwa 4 Wochen gedauert, inklusive mehrfacher Iteration der ETL-Pipeline und Trial-and-Error bei der Dashboard-UX. Einige Entscheidungen (z.B. Last.fm-Gewichtung 1.2) sind explorativ und würden für Produktivnutzung weitere Validierung benötigen.

Live-Dashboard: https://dashboard-d0z8.onrender.com


Zielsetzung:
Das Dashboard verfolgt drei konkrete Ziele:
- Automatisierte Aufbereitung und Visualisierung der relevanten Marktdaten.
- Analyse von Genre-Strukturen und Erfolgskennzahlen auf Marktebene.
- Ergänzung historischer KPIs um optionale Live-Signale aus Spotify und Last.fm.

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

3. API-Keys konfigurieren (optional, aber empfohlen):
   Eine .env Datei im Hauptverzeichnis erstellen mit:
   
   SPOTIFY_CLIENT_ID=dein_spotify_client_id
   SPOTIFY_CLIENT_SECRET=dein_spotify_client_secret
   LASTFM_API_KEY=dein_lastfm_api_key
   
   Entsprechende Keys können hier erstellt werden:
   - Spotify: https://developer.spotify.com/dashboard
   - Last.fm: https://www.last.fm/api/account/create
   
   HINWEIS: Dashboard funktioniert auch ohne API-Keys (nutzt Fallback-Daten). Die Live-API-Integration ist ein Bonus-Feature und nicht zwingend erforderlich.


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

Zusätzlich wird data_journal.csv mit detaillierter Dokumentation aller Verarbeitungsschritte generiert.

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

Die Genre-Standardisierung ist in genre_mapping.json definiert. Beispielsweise werden "hip hop", "rap", "trap" und "german hip hop" alle als "Hip-Hop" klassifiziert.

Alle Verarbeitungsschritte sind in data_journal.csv dokumentiert.
Die ETL-Pipeline erzeugt bei identischen Eingabedaten reproduzierbare Ergebnisse.


Success Score Berechnung:
Der Success Score kombiniert fünf Komponenten auf einer 0-100 Skala:
- Chart-Rank (Gewicht 25%): Position in den Charts (normiert, höherer Rang = besserer Score)
- Streams (Gewicht 15%): Logarithmisch normalisierte Stream-Zahlen
- Audio-Features (Gewicht 30%): Kombination aus Danceability (15%) und Energy (15%)
- Artist Followers (Gewicht 20%): Logarithmisch normalisierte Follower-Zahlen
- Top10 Placement (Gewicht 10%): Bonus für Top-10-Platzierungen

Die Formel gewichtet objektive Erfolgsindikatoren (Rank, Streams, Followers) mit 60% und Audio-Eigenschaften mit 40%. Tracks mit einem Score ≥65 gelten als High-Potential.


Market Potential Score Berechnung:
Der Market Potential Score kombiniert drei Komponenten auf einer 0-100 Skala:
- Market Share (Gewicht 40%): Aktueller Marktanteil des Genres
- Success Rate (Gewicht 30%): Anteil der Tracks mit hohem Success Score (≥65)
- Growth Momentum (Gewicht 30%): Wachstum seit 2017, normiert auf 0-100

Die Growth-Komponente wird auf 200% (Verdoppelung) begrenzt und anschließend auf 0-100 normiert, um Ausreißer-Dominanz zu verhindern und Vergleichbarkeit zwischen Genres zu gewährleisten. Vor dem Export erfolgt eine automatische Validierung der Datenqualität (keine Duplikate, Market Share Summen = 100%).


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
- Die Shannon-Diversität variiert zwischen den Märkten: Brasilien zeigt durchschnittlich 1,36, Deutschland 1,26 und UK 1,38, was auf unterschiedliche Konzentrationsgrade hinweist.
- Brasilien zeigt im Zeitverlauf einen Aufwärtstrend in den Marktverläufen, während der UK-Markt relativ an Anteil verliert.
- Audio-Features wie Danceability und Energy zeigen Zusammenhänge mit Erfolg, erklären diesen jedoch nur begrenzt und nicht kausal.

Limitation der Datenquelle:
Die Genre-Identifikation basiert auf Metadata-Abgleich mit der Final Database. Für das Jahr 2021 zeigt sich eine deutlich reduzierte Genre-Coverage (10,2% vs. 53,8% in 2020), was zu einem erhöhten "Other"-Anteil führt. Diese Einschränkung liegt in der verwendeten Kaggle-Datenquelle begründet, die für 2021-Tracks weniger vollständige Genre-Metadaten enthält. Die Analyse fokussiert daher primär auf den Zeitraum 2017-2020 mit vollständiger Genre-Klassifikation.


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
   Optionale Ergänzung der historischen Analyse durch aktuelle Streaming-Daten aus Spotify- und Last.fm-APIs.


4. Dashboard starten:
   python dashboard.py
   Öffne anschließend http://localhost:8050
   
   Beim ersten Start lädt das Dashboard automatisch die große CSV-Datei (spotify_charts_enhanced.csv, 309MB) von GitHub herunter falls nicht lokal vorhanden.
   Das kann 1-2 Minuten dauern – danach läuft alles lokal.

	WICHTIG für Reproduktion:
	- datenverarbeitung.py muss NUR ausgeführt werden, wenn die CSV-Dateien neu generiert werden sollen (z.B. bei geänderten Kaggle-Rohdaten).
	- Die fertigen CSV-Dateien sind bereits im Repo enthalten.
	- Das Dashboard läuft auch ohne API-Keys.


Dokumentation:
Zusätzlich zum Code gibt es folgende Dokumentation:

- Report: Dashboard Spotify Performance Insights Report.pdf
- Data Journal: data_journal.csv
- Genre-Mapping: genre_mapping.json
- Config: config.json
