"""Offline coverage of Thursday release windows and movie-guide integration."""
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import movie_releases
import newsletter


def fake_movie(movie_id, title, poster="/example.jpg", popularity=12):
    return {
        "id": movie_id,
        "title": title,
        "poster_path": poster,
        "adult": False,
        "popularity": popularity,
        "release_date": "2026-10-16",  # Global dates are NOT trusted.
    }


def country_dates(*dates):
    return {"results": [
        {"iso_3166_1": "GB", "release_dates": [
            {"type": 3, "release_date": "2026-10-15T00:00:00Z"}
        ]},
        {"iso_3166_1": "US", "release_dates": [
            {"type": kind, "release_date": day + "T00:00:00Z"}
            for day, kind in dates
        ]},
    ]}


class MovieReleaseTests(unittest.TestCase):
    def test_thursday_to_wednesday_window_including_friday(self):
        start, end = movie_releases.opening_week(date(2026, 10, 17))  # Saturday
        self.assertEqual(start, date(2026, 10, 15))
        self.assertEqual(end, date(2026, 10, 21))
        self.assertEqual(movie_releases.opening_week(date(2026, 10, 15)), (start, end))
        self.assertEqual(movie_releases.opening_week(date(2026, 10, 21)), (start, end))
        self.assertEqual(movie_releases.opening_week(date(2026, 10, 22))[0], date(2026, 10, 22))

    def test_US_theatrical_dates_only_not_digital_or_world_premiere(self):
        first, last = movie_releases.opening_week(date(2026, 10, 17))
        dates = country_dates(
            ("2026-10-16", 4),  # streaming not a theatrical opening
            ("2026-10-16", 3),  # US wide theatrical opening
            ("2026-10-18", 2),
        )
        self.assertEqual(movie_releases._region_theatrical_date(dates, first, last),
                         (date(2026, 10, 16), 3))
        self.assertIsNone(movie_releases._region_theatrical_date(
            country_dates(("2026-10-16", 4), ("2026-10-23", 3)), first, last))

    def test_no_key_returns_unconfigured_not_invented_releases(self):
        with patch.dict(os.environ, {"TMDB_API_KEY": ""}):
            titles, status, window = movie_releases.get_weekly_movies(
                {"max_weekly_movies": 5}, date(2026, 10, 17))
        self.assertEqual(titles, [])
        self.assertEqual(status, "unconfigured")
        self.assertEqual(window, (date(2026, 10, 15), date(2026, 10, 21)))

    def test_discovery_verifies_each_movie_us_date_and_sorts_wide_first(self):
        requests_made = []
        discovery = {"results": [
            fake_movie(101, "A limited release", popularity=200),
            fake_movie(102, "A wide Friday release", popularity=80),
            fake_movie(103, "Digital only"),
            fake_movie(104, "Next week movie"),
        ]}
        mapping = {
            "/movie/101/release_dates": country_dates(("2026-10-15", 2)),
            "/movie/102/release_dates": country_dates(("2026-10-16", 3)),
            "/movie/103/release_dates": country_dates(("2026-10-16", 4)),
            "/movie/104/release_dates": country_dates(("2026-10-23", 3)),
        }
        def fake_get(path, key, *, params=None):
            requests_made.append((path, dict(params or {})))
            if path == "/discover/movie":
                return discovery if params["page"] == 1 else {"results": []}
            return mapping[path]

        with patch.dict(os.environ, {"TMDB_API_KEY": "synthetic-test-key"}):
            with patch.object(movie_releases, "_tmdb_get", side_effect=fake_get):
                titles, status, window = movie_releases.get_weekly_movies(
                    {"max_weekly_movies": 5}, date(2026, 10, 17))
        self.assertEqual(status, "ok")
        self.assertEqual([r["id"] for r in titles], [102, 101])
        self.assertEqual(titles[0]["date"], date(2026, 10, 16))
        discover_query = [params for path, params in requests_made if path == "/discover/movie"][0]
        self.assertEqual(discover_query["region"], "US")
        self.assertEqual(discover_query["with_release_type"], "3|2")
        self.assertEqual(discover_query["release_date.gte"], "2026-10-15")
        self.assertEqual(discover_query["release_date.lte"], "2026-10-21")
        self.assertEqual(window, (date(2026, 10, 15), date(2026, 10, 21)))

    def test_cinema_html_contains_proper_attribution_regal_and_title(self):
        movies = [{
            "id": 102, "title": "A wide Friday release", "date": date(2026, 10, 16),
            "type": "Wide theatrical", "wide": True,
            "poster": "https://image.tmdb.org/t/p/w185/example.jpg",
            "url": "https://www.themoviedb.org/movie/102", "popularity": 80
        }]
        section = newsletter.cinema_markup(
            movies, "ok", movie_releases.opening_week(date(2026, 10, 17)))
        self.assertIn("NEW AT THE MOVIES THIS WEEK", section)
        self.assertIn("A wide Friday release", section)
        self.assertIn("Fri, Oct 16", section)
        self.assertIn("https://image.tmdb.org", section)
        self.assertIn("https://www.regmovies.com/movies", section)
        self.assertIn("not confirmed showtimes", section)
        self.assertIn("This product uses the TMDB API", section)

    def test_no_key_renders_regal_fallback_without_inventing_movies(self):
        section = newsletter.cinema_markup(
            [], "unconfigured", movie_releases.opening_week(date(2026, 10, 17)))
        self.assertIn("not configured yet", section)
        self.assertIn("Regal", section)
        self.assertNotIn("A wide Friday release", section)

    def test_entertainment_category_enabled_but_not_overwritten(self):
        self.assertIn("entertainment", newsletter.CATEGORIES)
        self.assertIn("ENTERTAINMENT", newsletter.LABELS["entertainment"])
        config = json.loads((Path(__file__).parent.parent / "config.json").read_text())
        self.assertGreaterEqual(len(config["feeds"]["entertainment"]), 2)
        # Code is expected to keep the user's existing local coverage intact.
        self.assertGreater(len(config["feeds"]["local"]), 2)

    def test_readme_only_uses_broad_LA_location(self):
        readme = (Path(__file__).parent.parent / "README.md").read_text().lower()
        for exact_neighborhood in ("pasadena", "alhambra", "san gabriel"):
            self.assertNotIn(exact_neighborhood, readme)
        self.assertIn("los angeles", readme)
        self.assertNotIn("@gmail.com", readme)


if __name__ == "__main__":
    unittest.main()
