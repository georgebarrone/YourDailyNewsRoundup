"""Offline unit tests: no network calls, real Gemini requests, or Gmail access."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import newsletter


def make_story(key, category, title, domain="news.example", image=""):
    return {
        "id": key,
        "category": category,
        "title": title,
        "url": "https://" + domain + "/articles/" + key,
        "source": domain,
        "domain": domain,
        "published": "2026-10-17T09:00:00+00:00",
        "excerpt": title + ". Additional reporting with useful facts about this event.",
        "image": image,
    }


class NewsRoundupTests(unittest.TestCase):
    def test_safe_links_and_images(self):
        self.assertEqual(newsletter.safe_url("javascript:alert(1)"), "")
        self.assertEqual(newsletter.safe_url("http://example.com/pic.jpg"), "")
        self.assertEqual(newsletter.safe_url("https://example.com/pic.jpg"),
                         "https://example.com/pic.jpg")
        entry = {
            "media_thumbnail": [{"url": "https://images.example/pasadena.jpg"}],
            "media_content": [],
        }
        self.assertEqual(newsletter.image_from_entry(entry),
                         "https://images.example/pasadena.jpg")

    def test_same_event_and_distinct_topics(self):
        a = make_story("a", "politics", "City council approves new zoning plan after vote")
        b = make_story("b", "politics", "City council approves new zoning plan after vote")
        c = make_story("c", "technology", "New gaming console announced with updated graphics")
        self.assertTrue(newsletter.same_event(a, b))
        self.assertFalse(newsletter.same_event(a, c))

    def test_past_headlines_and_legacy_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            path.write_text('["old-hash"]', encoding="utf-8")
            history = newsletter.load_history(path)
            self.assertEqual(history[0]["id"], "old-hash")
            self.assertTrue(newsletter.recently_sent(
                make_story("old-hash", "local", "Local city update"), history))

    def test_markup_contains_photo_source_and_related_link(self):
        feature = make_story("abc", "local", "Pasadena considers a new park",
                             image="https://images.example/park.jpg")
        feature["summary"] = "The city announced a proposed park project."
        feature["related"] = [make_story("def", "local", "Pasadena park proposal considered",
                                          domain="other.example")]
        second = make_story("ghi", "technology", "New computing technology launches")
        second["summary"] = "A company announced a new computer product."
        second["related"] = []
        page = newsletter.render(
            [feature, second], {"newsletter_title": "Your Daily News Roundup"},
            "Saturday, October 17, 2026", "cid:roundup-masthead")
        self.assertIn("cid:roundup-masthead", page)
        self.assertIn("https://images.example/park.jpg", page)
        self.assertIn("other.example", page)
        self.assertIn("TOP STORY", page)
        self.assertIn("TECHNOLOGY", page)
        self.assertNotIn("javascript:", page)

    def test_gemini_retries_transient_503_and_succeeds(self):
        class FakeAPIError(Exception):
            def __init__(self, code):
                self.code = code

        class FakeClient:
            class Models:
                def __init__(self):
                    self.calls = 0

                def generate_content(self, **kwargs):
                    self.calls += 1
                    if self.calls < 3:
                        raise FakeAPIError(503)
                    return type("Response", (), {"text": '{"stories":[]}'})()

            def __init__(self):
                self.models = self.Models()

        fake = FakeClient()
        with patch.object(newsletter.gemini_errors, "APIError", FakeAPIError):
            with patch.object(newsletter.time, "sleep") as sleep:
                response = newsletter.generate_news_with_retry(fake, "test-model", "test")
        self.assertEqual(response.text, '{"stories":[]}')
        self.assertEqual(fake.models.calls, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [15, 40])

    def test_gemini_does_not_retry_permanent_errors(self):
        class FakeAPIError(Exception):
            def __init__(self, code):
                self.code = code

        class FakeClient:
            class Models:
                def __init__(self):
                    self.calls = 0

                def generate_content(self, **kwargs):
                    self.calls += 1
                    raise FakeAPIError(401)

            def __init__(self):
                self.models = self.Models()

        fake = FakeClient()
        with patch.object(newsletter.gemini_errors, "APIError", FakeAPIError):
            with patch.object(newsletter.time, "sleep") as sleep:
                with self.assertRaises(FakeAPIError):
                    newsletter.generate_news_with_retry(fake, "test-model", "test")
        self.assertEqual(fake.models.calls, 1)
        sleep.assert_not_called()

    def test_gemini_retries_stop_after_bounded_attempts(self):
        class FakeAPIError(Exception):
            def __init__(self, code):
                self.code = code

        class FakeClient:
            class Models:
                def __init__(self):
                    self.calls = 0

                def generate_content(self, **kwargs):
                    self.calls += 1
                    raise FakeAPIError(503)

            def __init__(self):
                self.models = self.Models()

        fake = FakeClient()
        with patch.object(newsletter.gemini_errors, "APIError", FakeAPIError):
            with patch.object(newsletter.time, "sleep") as sleep:
                with self.assertRaises(FakeAPIError):
                    newsletter.generate_news_with_retry(fake, "test-model", "test")
        self.assertEqual(fake.models.calls, 4)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [15, 40, 90])


    def test_gemini_uses_backup_after_persistent_503(self):
        class FakeAPIError(Exception):
            def __init__(self, code):
                self.code = code

        class FakeModels:
            def __init__(self):
                self.calls = []

            def generate_content(self, **kwargs):
                model = kwargs["model"]
                self.calls.append(model)
                if model == "overloaded":
                    raise FakeAPIError(503)
                return type("Response", (), {"text": '{"stories":[]}'})()

        fake = type("Client", (), {"models": FakeModels()})()
        with patch.object(newsletter.gemini_errors, "APIError", FakeAPIError):
            with patch.object(newsletter.time, "sleep") as sleep:
                result = newsletter.generate_news_with_fallback(
                    fake, ["overloaded", "backup", "unused"], "test")
        self.assertEqual(json.loads(result.text), {"stories": []})
        self.assertEqual(fake.models.calls, ["overloaded", "overloaded", "backup"])
        sleep.assert_called_once_with(10)

    def test_gemini_fallback_does_not_hide_credential_errors(self):
        class FakeAPIError(Exception):
            def __init__(self, code):
                self.code = code

        class FakeModels:
            def __init__(self):
                self.calls = []

            def generate_content(self, **kwargs):
                self.calls.append(kwargs["model"])
                raise FakeAPIError(403)

        fake = type("Client", (), {"models": FakeModels()})()
        with patch.object(newsletter.gemini_errors, "APIError", FakeAPIError):
            with patch.object(newsletter.time, "sleep") as sleep:
                with self.assertRaises(FakeAPIError):
                    newsletter.generate_news_with_fallback(fake, ["primary", "backup"], "test")
        self.assertEqual(fake.models.calls, ["primary"])
        sleep.assert_not_called()

    def test_gemini_fallback_skips_missing_model_and_invalid_json(self):
        class FakeAPIError(Exception):
            def __init__(self, code):
                self.code = code

        class FakeModels:
            def __init__(self):
                self.calls = []

            def generate_content(self, **kwargs):
                model = kwargs["model"]
                self.calls.append(model)
                if model == "missing":
                    raise FakeAPIError(404)
                if model == "invalid":
                    return type("Response", (), {"text": "not json"})()
                return type("Response", (), {"text": '{"stories":[]}'})()

        fake = type("Client", (), {"models": FakeModels()})()
        with patch.object(newsletter.gemini_errors, "APIError", FakeAPIError):
            with patch.object(newsletter.time, "sleep") as sleep:
                result = newsletter.generate_news_with_fallback(
                    fake, ["missing", "invalid", "ok"], "test")
        self.assertEqual(json.loads(result.text), {"stories": []})
        self.assertEqual(fake.models.calls, ["missing", "invalid", "ok"])
        sleep.assert_not_called()

    def test_gemini_groups_same_event_and_balances_categories(self):
        local = make_story("l", "local", "Pasadena neighborhood meeting draws residents")
        political = make_story("p", "politics", "Congress takes vote on new budget bill")
        alternate = make_story(
            "q", "politics", "Congress takes vote on new budget bill",
            domain="independent.example")
        tech = make_story("t", "technology", "New computer processor launched")
        response = {
            "stories": [
                {"primary_id": "p", "related_ids": ["q"], "summary":
                 "The legislature voted on a bill according to coverage from two outlets."},
                {"primary_id": "l", "related_ids": [], "summary":
                 "Residents met to discuss plans for a neighborhood improvement project."},
                {"primary_id": "t", "related_ids": [], "summary":
                 "A company has announced its latest processor and new performance features."},
                {"primary_id": "q", "related_ids": [], "summary":
                 "A second article about the same congressional budget vote was also published."}
            ]
        }
        class FakeResponse:
            text = json.dumps(response)
        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass
            class models:
                @staticmethod
                def generate_content(**kwargs):
                    return FakeResponse()
        with patch.dict("os.environ", {"GEMINI_API_KEY": "example-not-a-real-key"}):
            with patch.object(newsletter.genai, "Client", FakeClient):
                articles = newsletter.curate(
                    [local, political, alternate, tech], [],
                    {"max_articles": 12, "gemini_model": "mock-model"})
        self.assertEqual(len(articles), 3)
        self.assertEqual(articles[0]["category"], "local")
        self.assertEqual(articles[1]["category"], "politics")
        self.assertEqual(len(articles[1]["related"]), 1)

    def test_static_masthead_matches_committed_png_and_needs_no_network(self):
        with patch.object(newsletter.requests, "get", side_effect=AssertionError("masthead should not fetch")):
            data = newsletter.masthead_png()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(data, newsletter.MASTHEAD_PATH.read_bytes())
        self.assertGreater(len(data), 1000)

    def test_email_mime_embeds_masthead_and_keeps_credentials_runtime_only(self):
        story = make_story("m", "local", "Local public meeting planned")
        story["summary"] = "Officials published plans for a local public meeting."
        story["related"] = []
        page = newsletter.render([story], {"newsletter_title": "Your Daily News Roundup"},
                                 "October 17, 2026", "cid:roundup-masthead")
        secrets = {
            "NEWSLETTER_SENDER_EMAIL": "sender@example.com",
            "NEWSLETTER_RECIPIENT_EMAIL": "recipient@example.com",
            "GMAIL_APP_PASSWORD": "synthetic-test-password",
        }
        with patch.dict("os.environ", secrets):
            with patch.object(newsletter.smtplib, "SMTP_SSL") as smtp:
                newsletter.send(page, b"\x89PNG\r\n\x1a\n", {
                    "newsletter_title": "Your Daily News Roundup"}, "October 17, 2026")
                sent = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
                self.assertEqual(sent["From"], "sender@example.com")
                self.assertEqual(sent["To"], "recipient@example.com")
                self.assertIn("roundup-masthead", sent.as_string())
                smtp.return_value.__enter__.return_value.login.assert_called_once_with(
                    "sender@example.com", "synthetic-test-password")

    def test_corrects_misclassified_articles_from_actual_preview(self):
        cases = [
            ("obituaries", "Judge dismisses charges against actor Timothy Busfield",
             "entertainment"),
            ("entertainment", "Malibu Bryson Fire containment improves",
             "local"),
            ("gaming", "Beloved Fantasy Novel Series Redwall Sets Return",
             "entertainment"),
            ("entertainment", "Popular film star dies at 82",
             "obituaries"),
            ("gaming", "Nintendo announces a new Zelda video game",
             "gaming"),
        ]
        for original, title, expected in cases:
            with self.subTest(title=title):
                record = make_story("one", original, title)
                self.assertEqual(newsletter.categorize_story(record), expected)

    def test_section_ordering_and_automatic_headline_sorting(self):
        def story(key, category, title, published):
            item = make_story(key, category, title)
            item["published"] = published
            item["summary"] = "A factual report was published."
            item["related"] = []
            return item

        stories = [
            story("lead", "local", "Local lead story", "2026-10-17T08:00:00+00:00"),
            story("political", "politics", "National political update", "2026-10-17T07:00:00+00:00"),
            story("technology", "technology", "Technology update", "2026-10-17T09:00:00+00:00"),
            story("entertainment", "entertainment", "Movie casting update", "2026-10-17T09:30:00+00:00"),
            story("new", "local", "Newest neighborhood headline", "2026-10-17T10:00:00+00:00"),
            story("old", "local", "Older neighborhood headline", "2026-10-17T06:00:00+00:00"),
            story("gaming", "gaming", "New video game announced", "2026-10-17T10:00:00+00:00"),
            story("obituary", "obituaries", "Notable person died", "2026-10-17T10:00:00+00:00"),
        ]
        page = newsletter.render(
            stories, {"newsletter_title": "Your Daily News Roundup"},
            "Saturday, October 17, 2026", "cid:roundup-masthead")
        self.assertIn("TOP STORY · LOS ANGELES", page)
        sections = [
            "POLITICS & WORLD",
            "LOS ANGELES & THE SAN GABRIEL VALLEY",
            "MOVIES, TELEVISION & ENTERTAINMENT",
            "TECHNOLOGY",
            "GAMING",
            "IN MEMORIAM",
        ]
        labels = ["politics", "local", "entertainment", "technology", "gaming", "obituaries"]
        for before, after in zip(labels, labels[1:]):
            self.assertLess(page.index(newsletter.section_header(before)),
                            page.index(newsletter.section_header(after)))
        self.assertLess(page.index("Newest neighborhood headline"),
                        page.index("Older neighborhood headline"))

    def test_scheduled_retry_does_not_send_twice_same_day(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "config.json").write_text(
                json.dumps({"timezone": "America/Los_Angeles", "newsletter_title": "Test"}),
                encoding="utf-8"
            )
            (path / "history.json").write_text("[]", encoding="utf-8")
            today = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
            (path / "delivery_state.json").write_text(
                json.dumps({"last_scheduled_delivery": today}), encoding="utf-8"
            )
            with patch.object(newsletter, "ROOT", path), \
                 patch("sys.argv", ["newsletter.py", "--scheduled"]), \
                 patch.object(newsletter, "get_weekly_movies") as movie_lookup, \
                 patch.object(newsletter, "collect") as collect, \
                 patch.object(newsletter, "send") as send:
                newsletter.main()
                movie_lookup.assert_not_called()
                collect.assert_not_called()
                send.assert_not_called()

    def test_scheduled_delivery_records_date_only_after_success(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "config.json").write_text(
                json.dumps({"timezone": "America/Los_Angeles", "newsletter_title": "Test"}),
                encoding="utf-8"
            )
            (path / "history.json").write_text("[]", encoding="utf-8")
            (path / "delivery_state.json").write_text(
                json.dumps({"last_scheduled_delivery": None}), encoding="utf-8"
            )
            movie = {"title": "Demo opening"}
            with patch.object(newsletter, "ROOT", path), \
                 patch("sys.argv", ["newsletter.py", "--scheduled"]), \
                 patch.object(newsletter, "get_weekly_movies", return_value=(
                     [movie], "ok", (None, None))), \
                 patch.object(newsletter, "collect", return_value=[]), \
                 patch.object(newsletter, "masthead_png", return_value=b"test"), \
                 patch.object(newsletter, "render", return_value="<html></html>"), \
                 patch.object(newsletter, "send") as send:
                newsletter.main()
                send.assert_called_once()
                state = json.loads((path / "delivery_state.json").read_text())
                today = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
                self.assertEqual(state["last_scheduled_delivery"], today)

    def test_no_private_email_in_public_configuration(self):
        content = (Path(newsletter.__file__).parent / "config.json").read_text(
            encoding="utf-8")
        config = json.loads(content)
        self.assertNotIn("sender", config)
        self.assertNotIn("recipient", config)
        self.assertNotIn("@gmail.com", content)


if __name__ == "__main__":
    unittest.main()
