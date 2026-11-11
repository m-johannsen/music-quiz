# Musikratespiel

Web-App zum Abspielen von Hitster-Playlists als Ratespiel. Lieder werden über den eingebetteten YouTube-Player (IFrame API, unsichtbar – nur Audio) direkt von YouTube abgespielt. Es wird nichts heruntergeladen.

## Statische Seite (GitHub Pages)

`index.html` im Repo-Root ist die komplette App (Pico CSS per CDN), sie braucht keinen Server. Die Playlists liegen in `playlists/*.csv`, welche davon angeboten werden, steht in `playlists/published.csv`.

Deployment: GitHub → Settings → Pages → *Deploy from a branch* → `main` / `(root)`.

Lokal testen: `python3 -m http.server` und `http://localhost:8000` öffnen.

### Eigene Playlists

Über **+ Playlist** lässt sich ein Link zu einer CSV im Hitster-Format hinzufügen (`Card#,Artist,Title,URL,Hashed Info,Youtube-Title,Year`; nur `Artist`, `Title`, `URL`, `Year` werden gebraucht):

- **GitHub**: Link zur Datei (`github.com/.../blob/...` oder `raw.githubusercontent.com/...`)
- **Google Sheet**: „Teilen → Jeder mit dem Link“ oder *Datei → Im Web veröffentlichen → CSV*; der normale Bearbeiten-Link genügt

Die Links werden im `localStorage` gespeichert. Safari auf dem iPhone löscht das nach 7 Tagen ohne Besuch, außer die Seite liegt auf dem Home-Bildschirm. Der Button „Link mit Playlists kopieren“ erzeugt eine URL (`?pl=...`), die alle eigenen Playlists wiederherstellt.

## Playlists pflegen (lokal)

Eine Exportify-CSV (Spotify) wird mit `tools/convert.py` in eine Hitster-CSV umgewandelt:

```bash
uv run tools/convert.py export.csv -o playlists/mein-mix.csv --publish "Mein Mix"
```

Das Skript sucht per `yt-dlp` zu jedem Song einen YouTube-Link (zwischengespeichert in `tools/.yt-cache.json`), schreibt die CSV und gibt danach die Jahresverteilung pro Jahrzehnt sowie Songs zur manuellen Prüfung aus (Jahr stammt evtl. von einer Neuauflage, Video ungewöhnlich lang, kein Link gefunden). `--publish` trägt die Playlist in `playlists/published.csv` ein. Eine bestehende Hitster-CSV kann ebenfalls Eingabe sein, vorhandene Links bleiben dann erhalten. Weitere Optionen: `--help`.

## Bedienung

### Spiel

1. **Playlist wählen** – Dropdown zeigt alle verfügbaren Playlists
2. **Song abspielen** – startet den ersten Song; der Hauptknopf führt durch die Runde
3. **Auflösen** – deckt Künstler, Titel und Jahr auf
4. **Nächster Song** – spielt sofort einen neuen zufälligen Song (Jahrzehnte ausgeglichen gewichtet)

Dazu gibt es kleine Links für Pause und „Song überspringen“.

Künstler, Titel und Jahr auf
4. **Nächster Song** – spielt einen neuen zufälligen Song (Jahrzehnte ausgeglichen gewichtet)

Künstler, Titel und Jahr auf
4. **Nächster Song** – lädt einen neuen zufälligen Song
5. **Autoplay** – startet nach Songende automatisch den nächsten Song

Künstler, Titel und Jahr sind zensiert angezeigt, bis „Auflösen" geklickt wird.

Nicht abspielbare Songs (Einbetten gesperrt) werden im Browser gemerkt und übersprungen.

## Hinweise

- YouTube-Werbung kann vor Songs abgespielt werden (YouTube Premium auf dem Gerät verhindert das)
- Auf Mobilgeräten stoppt die Wiedergabe oft bei gesperrtem Bildschirm
