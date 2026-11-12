"""Check the Year column of a Hitster CSV against MusicBrainz (earliest release of the recording).

    uv run tools/years.py playlists/mix.csv            # only report
    uv run tools/years.py playlists/mix.csv --apply    # write corrected years into the file

Spotify gives the year of the album, so reissues and best-of albums show up as too late.
Only earlier MusicBrainz years are applied; later ones are listed for manual review.
Needs about one second per song (MusicBrainz rate limit); answers are cached in tools/.mb-cache.json.
"""
import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path(__file__).with_name(".mb-cache.json")
API = "https://musicbrainz.org/ws/2/recording/"
AGENT = "musikratespiel-years/0.1 (private hobby project)"


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = re.sub(r"[^a-z0-9]+", "", s)
    return re.sub(r"^the", "", s)


def clean_title(title):
    """'Song - Remastered 2009' / 'Song (Live)' -> 'Song'"""
    title = re.split(r" - ", title)[0]
    return re.sub(r"\s*[(\[].*?[)\]]", "", title).strip()


def main_artist(artist):
    return re.split(r",| feat\.?| ft\.?| & | with | and his | and the ", artist, flags=re.I)[0].strip()


def lookup(artist, title, cache):
    """Earliest first-release year of matching recordings, or None."""
    key = f"{artist}|{title}"
    if key in cache:
        return cache[key]
    t, a = clean_title(title), main_artist(artist)
    q = 'recording:"{}" AND artist:"{}"'.format(t.replace('"', '\\"'), a.replace('"', '\\"'))
    url = API + "?" + urllib.parse.urlencode({"query": q, "fmt": "json", "limit": 100})
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            data = json.load(urllib.request.urlopen(req, timeout=30))
            break
        except Exception as e:
            time.sleep(3 * (attempt + 1))
    else:
        return "error"   # not cached, a rerun retries it
    years = []
    for rec in data.get("recordings", []):
        if rec.get("score", 0) < 85 or norm(rec.get("title", "")) != norm(t):
            continue
        credits = [norm(c["name"]) for c in rec.get("artist-credit", []) if isinstance(c, dict)]
        if not any(norm(a) in c or c in norm(a) for c in credits if c):
            continue
        d = rec.get("first-release-date", "")
        if d[:4].isdigit():
            years.append(int(d[:4]))
    cache[key] = min(years) if years else None
    return cache[key]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--apply", action="store_true", help="frühere MusicBrainz-Jahre in die Datei schreiben")
    args = ap.parse_args()

    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}

    earlier, later, missing = [], [], []
    for i, r in enumerate(rows, 1):
        if r.get("Card#", "").strip() == "-1" or not r["Year"].isdigit():
            continue
        fresh = f"{r['Artist']}|{r['Title']}" not in cache
        mb = lookup(r["Artist"], r["Title"], cache)
        if fresh:
            time.sleep(1.1)
            if i % 25 == 0:
                CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
                print(f"  {i}/{len(rows)}", file=sys.stderr)
        old = int(r["Year"])
        if mb == "error" or mb is None:
            missing.append(r)
        elif mb < old:
            earlier.append((r, old, mb))
        elif mb > old:
            later.append((r, old, mb))
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))

    print(f"\n{len(earlier)} Songs mit früherem MusicBrainz-Jahr:")
    for r, old, mb in sorted(earlier, key=lambda x: x[1] - x[2], reverse=True):
        print(f"  {old} -> {mb}  {r['Artist']} – {r['Title']}")
    print(f"\n{len(later)} Songs mit späterem MusicBrainz-Jahr (nicht geändert, bitte prüfen):")
    for r, old, mb in later:
        print(f"  {old} -> {mb}  {r['Artist']} – {r['Title']}")
    print(f"\n{len(missing)} Songs ohne Treffer (Jahr unverändert)")

    if args.apply:
        for r, _, mb in earlier:
            r["Year"] = str(mb)
        with open(args.csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fields)
            w.writeheader()
            w.writerows(rows)
        print(f"\n{len(earlier)} Jahre in {args.csv} korrigiert")


if __name__ == "__main__":
    main()
