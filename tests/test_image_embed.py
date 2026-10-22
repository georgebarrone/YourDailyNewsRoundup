"""Offline regression tests for article photos and email-safe inline image references."""
import io
import unittest
from unittest.mock import patch

from PIL import Image

import image_embed


class FakeResponse:
    def __init__(self, payload, content_type="image/png"):
        self.payload = payload
        self.headers = {"Content-Type": content_type}
        self.url = "https://cdn.example.com/image.png"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=65536):
        yield self.payload


class ImageEmbedTests(unittest.TestCase):
    def test_download_valid_png_is_optimized_as_jpeg(self):
        output = io.BytesIO()
        Image.new("RGBA", (200, 100), (30, 40, 50, 120)).save(output, "PNG")
        with patch.object(image_embed.requests, "get", return_value=FakeResponse(output.getvalue())):
            jpeg = image_embed.download_jpeg("https://cdn.example.com/image.png")
        self.assertTrue(jpeg.startswith(b"\xff\xd8"))
        self.assertLessEqual(len(jpeg), image_embed.MAX_INLINE_BYTES)

    def test_blocked_or_too_large_images_are_omitted(self):
        with patch.object(image_embed.requests, "get", return_value=FakeResponse(b"<html>blocked</html>", "text/html")):
            self.assertIsNone(image_embed.download_jpeg("https://cdn.example.com/image.png"))
        with patch.object(image_embed.requests, "get", return_value=FakeResponse(b"x" * (image_embed.MAX_DOWNLOAD_BYTES + 1))):
            self.assertIsNone(image_embed.download_jpeg("https://cdn.example.com/image.png"))
        self.assertIsNone(image_embed.download_jpeg("http://insecure.example.com/image.jpg"))

    def test_email_uses_cid_and_drops_failed_image_without_changing_input(self):
        stories = [
            {"id": "one", "category": "local", "published": "2026-10-21", "image": "https://cdn.example.com/good.jpg"},
            {"id": "two", "category": "politics", "published": "2026-10-21", "image": "https://cdn.example.com/broken.jpg"},
        ]
        movies = [{"title": "Film", "poster": "https://cdn.example.com/poster.jpg"}]
        with patch.object(image_embed, "download_jpeg", side_effect=lambda url: b"validjpeg" if "broken" not in url else None):
            output, posters, attachments = image_embed.prepare_images(stories, movies)
        self.assertEqual(output[0]["image"], "cid:roundup-article-1")
        self.assertEqual(output[1]["image"], "")
        self.assertEqual(posters[0]["poster"], "cid:roundup-poster-1")
        self.assertEqual(set(attachments), {"roundup-article-1", "roundup-poster-1"})
        self.assertEqual(stories[0]["image"], "https://cdn.example.com/good.jpg")

    def test_preview_inlines_image_without_remote_links(self):
        stories = [{"id": "one", "category": "local", "published": "2026-10-21", "image": "https://cdn.example.com/good.jpg"}]
        with patch.object(image_embed, "download_jpeg", return_value=b"validjpeg"):
            output, _, attachments = image_embed.prepare_images(stories, preview=True)
        self.assertTrue(output[0]["image"].startswith("data:image/jpeg;base64,"))
        self.assertFalse(attachments)

    def test_email_src_rejects_script_and_unsafe_cids(self):
        self.assertEqual(image_embed.email_image_src("cid:roundup-article-1"), "cid:roundup-article-1")
        self.assertEqual(image_embed.email_image_src("javascript:alert(1)"), "")
        self.assertEqual(image_embed.email_image_src("cid:attacker"), "")


if __name__ == "__main__":
    unittest.main()
