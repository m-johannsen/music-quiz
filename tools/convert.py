"""Convert an Exportify (Spotify) CSV into a Hitster-format CSV with YouTube links.

    uv run tools/convert.py export.csv -o playlists/mein-mix.csv --publish "Mein Mix"

Also accepts a Hitster CSV: existing YouTube links are kept, missing ones are searched.
Search results are cached in tools/.yt-cache.json, so re-running is cheap.
Afterwards the script prints the year distribution per decade and the songs worth a manual check.
"""
import argparse
import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).with_name(".yt-cache.json")
FIELDS = ["Card#", "Artist", "Title", "URL", "Hashed Info", "Youtube-Title", "Year"]

# Album titles suggesting Spotify's release date is not the song's original year
REISSUE = re.compile(
    r"remaster|greatest hits|best of|collection|anniversary|deluxe|essential|anthology"
    r"|compilation|beste|sammlung|jubil|klassiker|\bhits\b|\bgold\b|\bplatinum\b|\bclassics\b|very best|ultimate", re.I)


def video_id(url):
    u = urlparse(url)
    if u.hostname == "youtu.be":
        return u.path.lstrip("/")
    if u.hostname and u.hostname.endswith("youtube.com"):
        return parse_qs(u.query).get("v", [None])[0]


def read_songs(path):
    """Rows from Exportify or Hitster format as dicts: artist, title, year, url, yt_title, check."""
    songs = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if "Track Name" in row:   # Exportify
                title, album = row["Track Name"].strip(), row.get("Album Name", "")
                songs.append({
                    "artist": row.get("Artist Name(s)", "").split(";")[0].strip(),
                    "title": title,
                    "year": (row.get("Release Date") or row.get("Album Release Date") or "")[:4],
                    "url": "", "yt_title": "",
                    "check": album if REISSUE.search(album) or REISSUE.search(title) else "",
                })
            elif row.get("Card#", "").strip() != "-1":   # Hitster
                songs.append({"artist": row["Artist"], "title": row["Title"], "year": row["Year"],
                              "url": row.get("URL", ""), "yt_title": row.get("Youtube-Title", ""),
                              "check": ""})
    return [s for s in songs if s["title"]]


def search(query, cache):
    """First YouTube hit for query as {id, title, duration}, or None."""
    if query not in cache:
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as ydl:
                entry = (ydl.extract_info(f"ytsearch1:{query}", download=False).get("entries") or [None])[0]
            cache[query] = entry and {"id": entry["id"], "title": entry.get("title", ""),
                                      "duration": entry.get("duration")}
        except Exception as e:
            print(f"  Suche fehlgeschlagen für {query!r}: {e}", file=sys.stderr)
            return None   # not cached, so a rerun retries it
    return cache[query]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="Exportify- oder Hitster-CSV")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Ziel-CSV, z. B. playlists/mix.csv")
    ap.add_argument("--publish", metavar="NAME", help="Eintrag in playlists/published.csv anlegen")
    ap.add_argument("--no-search", action="store_true", help="keine YouTube-Suche")
    ap.add_argument("-j", "--jobs", type=int, default=4, help="parallele Suchen (Standard 4)")
    args = ap.parse_args()

    songs = read_songs(args.input)
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}

    todo = [s for s in songs if not video_id(s["url"])]
    if todo and not args.no_search:
        print(f"Suche {len(todo)} YouTube-Links …", file=sys.stderr)
        with ThreadPoolExecutor(args.jobs) as pool:
            hits = pool.map(lambda s: search(f"{s['artist']} {s['title']}", cache), todo)
            for s, hit in zip(todo, hits):
                if hit:
                    s["url"] = f"https://www.youtube.com/watch?v={hit['id']}"
                    s["yt_title"] = hit["title"]
                    if hit["duration"] and hit["duration"] > 600:
                        s["check"] = f"Video ist {hit['duration'] // 60} min lang"
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for i, s in enumerate(songs, 1):
            w.writerow([i, s["artist"], s["title"], s["url"], "", s["yt_title"], s["year"]])
    print(f"{len(songs)} Songs -> {args.output}")

    if args.publish:
        index = ROOT / "playlists" / "published.csv"
        line = f"{args.output.name},{args.publish}\n"
        text = index.read_text(encoding="utf-8")
        if args.output.name + "," not in text:
            index.write_text(text + ("" if text.endswith("\n") else "\n") + line, encoding="utf-8")
            print(f"Eintrag in {index.relative_to(ROOT)} angelegt")

    report(songs)


def report(songs):
    decades = {}
    for s in songs:
        if s["year"].isdigit():
            d = int(s["year"]) // 10 * 10
            decades[d] = decades.get(d, 0) + 1
    print("\nJahrzehnte:")
    for d in sorted(decades):
        print(f"  {d}er {decades[d]:4}  {'█' * round(40 * decades[d] / max(decades.values()))}")
    if len(songs) - sum(decades.values()):
        print(f"  ohne Jahr: {len(songs) - sum(decades.values())}")

    flagged = [s for s in songs if s["check"]]
    if flagged:
        print(f"\nPrüfen ({len(flagged)}): Jahr evtl. von Neuauflage oder falsches Video")
        for s in flagged:
            print(f"  {s['year']}  {s['artist']} – {s['title']}  [{s['check']}]")
    missing = [s for s in songs if not video_id(s["url"])]
    if missing:
        print(f"\nOhne YouTube-Link ({len(missing)}): werden im Spiel übersprungen")
        for s in missing:
            print(f"  {s['artist']} – {s['title']}")


if __name__ == "__main__":
    main()
