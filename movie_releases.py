"""US theatrical opening dates for an independent moviegoing newsletter.

Uses TMDB's region-aware discover and per-movie US release records. These are
NOT Regal theater showtimes or proof that a local Regal is screening a title.
No TMDB content is submitted to a generative AI model.
"""
import logging
import os
import re
from datetime import date, datetime, timedelta
import requests

LOG = logging.getLogger("roundup")
TMDB_API = "https://api.themoviedb.org/3"
TMDB_LOGO = (
    "https://www.themoviedb.org/assets/2/v4/logos/v2/"
    "blue_short-8e7b30f73a4020692ccca9c88bafe5dcb6f8a62a4c6bc55cd9ba82bb2cd95f6c.svg"
)
REGAL_MOVIES_URL = "https://www.regmovies.com/movies"
PREFERRED_REGAL_THEATERS = (
    {
        "name": "Regal Alhambra Renaissance",
        "url": "https://www.regmovies.com/theatres/regal-edwards-alhambra-renaissance-1053",
    },
    {
        "name": "Regal Paseo",
        "url": "https://www.regmovies.com/theatres/regal-paseo-1485",
    },
)


def opening_week(day=None):
    """Show the next Thursday's films beginning Monday, through the following Wednesday.

    Thursday-Sunday keeps the releases that have just opened. On Monday the
    guide resets to the forthcoming Thursday-Wednesday theatrical window.
    """
    day = day or date.today()
    thursday = day - timedelta(days=(day.weekday() - 3) % 7)
    if day.weekday() <= 2:  # Monday, Tuesday, Wednesday: look ahead.
        thursday += timedelta(days=7)
    return thursday, thursday + timedelta(days=6)


def _region_theatrical_date(releases, first, last):
    """Only trust US theatrical dates (limited = 2, wide = 3) inside this week."""
    candidates = []
    for region in releases.get("results", []):
        if region.get("iso_3166_1") != "US":
            continue
        for row in region.get("release_dates", []):
            kind = row.get("type")
            if kind not in (2, 3):
                continue
            raw_date = str(row.get("release_date", ""))[:10]
            try:
                opening = date.fromisoformat(raw_date)
            except ValueError:
                continue
            if first <= opening <= last:
                candidates.append((opening, kind))
    # Prefer the earlier theatrical opening; prefer wide if both types same day.
    candidates.sort(key=lambda pair: (pair[0], -pair[1]))
    return candidates[0] if candidates else None


def _tmdb_get(endpoint, api_key, *, params=None):
    query = dict(params or {})
    query["api_key"] = api_key
    response = requests.get(TMDB_API + endpoint, params=query, timeout=14,
                            headers={"Accept": "application/json", "User-Agent": "YourDailyNewsRoundup/2.1"})
    if response.status_code >= 400:
        # Do not include request URLs in exceptions: they contain the API key.
        raise RuntimeError("TMDB returned HTTP " + str(response.status_code))
    return response.json()


def get_weekly_movies(config, today=None):
    """Return (titles, status, (Thursday, Wednesday)); failures are non-fatal."""
    local_day = today or date.today()
    first, last = opening_week(local_day)
    api_key = os.environ.get("TMDB_API_KEY", "").strip()
    if not api_key:
        LOG.info("TMDB_API_KEY not present: weekly movie list unavailable")
        return [], "unconfigured", (first, last)
    max_movies = max(1, min(int(config.get("max_weekly_movies", 5)), 8))
    results, visited = [], set()
    try:
        for page in (1, 2):
            if len(results) >= max_movies + 5:
                break
            discovery = _tmdb_get(
                "/discover/movie", api_key,
                params={
                    "region": "US",
                    "language": "en-US",
                    "include_adult": "false",
                    "sort_by": "popularity.desc",
                    "with_release_type": "3|2",
                    "release_date.gte": first.isoformat(),
                    "release_date.lte": last.isoformat(),
                    "page": page,
                },
            )
            for item in discovery.get("results", [])[:20]:
                movie_id = item.get("id")
                if not isinstance(movie_id, int) or movie_id <= 0 or movie_id in visited:
                    continue
                visited.add(movie_id)
                if item.get("adult") or not item.get("title"):
                    continue
                # TMDB's primary_release_date may differ from the US theatrical
                # release date, so verify the per-country release records.
                dates = _tmdb_get(f"/movie/{movie_id}/release_dates", api_key)
                actual = _region_theatrical_date(dates, first, last)
                if not actual:
                    continue
                released, kind = actual
                poster = item.get("poster_path") or ""
                poster_url = ""
                if re.fullmatch(r"/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)", poster):
                    poster_url = "https://image.tmdb.org/t/p/w185" + poster
                results.append({
                    "id": movie_id,
                    "title": str(item["title"])[:150],
                    "date": released,
                    "type": "Wide theatrical" if kind == 3 else "Limited theatrical",
                    "wide": kind == 3,
                    "poster": poster_url,
                    "url": f"https://www.themoviedb.org/movie/{movie_id}",
                    "popularity": float(item.get("popularity") or 0),
                })
                if len(results) >= max_movies + 4:
                    break
            if len(results) >= max_movies:
                break
        results.sort(key=lambda m: (-int(m["wide"]), -m["popularity"], m["date"], m["title"]))
        selected = results[:max_movies]
        LOG.info("Found %d US theatrical movies for %s to %s", len(selected), first, last)
        return selected, ("ok" if selected else "no_releases"), (first, last)
    except (requests.RequestException, RuntimeError, ValueError, TypeError, KeyError) as exc:
        LOG.warning("TMDB theatrical movie lookup unavailable (%s)", type(exc).__name__)
        return [], "unavailable", (first, last)
