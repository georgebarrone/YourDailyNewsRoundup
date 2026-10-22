"""Retrieve and embed publisher photos so email clients never need remote image URLs."""
import base64
import io
import logging
import re
from urllib.parse import urlsplit

import requests
from PIL import Image, ImageOps, UnidentifiedImageError

LOG = logging.getLogger("roundup")
MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_INLINE_BYTES = 600_000
MAX_ARTICLE_IMAGES = 5
MAX_ARTICLE_ATTEMPTS = 8


def email_image_src(value):
    """Allow only approved image references in HTML, including locally prepared CIDs."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if re.fullmatch(r"cid:roundup-(?:article|poster)-[1-9][0-9]*", value):
        return value
    if value.startswith("data:image/jpeg;base64,") and re.fullmatch(
            r"data:image/jpeg;base64,[A-Za-z0-9+/]+={0,2}", value):
        return value
    try:
        parsed = urlsplit(value)
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return ""


def download_jpeg(url):
    """Read a bounded publisher response and convert supported images to compact JPEGs."""
    if not email_image_src(url).startswith("https://"):
        return None
    try:
        with requests.get(
                url, stream=True, timeout=(5, 8),
                headers={"User-Agent": "YourDailyNewsRoundup/2.0 (+personal RSS reader)",
                         "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif,*/*;q=0.5"},
        ) as response:
            response.raise_for_status()
            if not email_image_src(response.url).startswith("https://"):
                raise ValueError("Image redirected to an unsafe URL")
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > MAX_DOWNLOAD_BYTES:
                raise ValueError("Image exceeds download limit")
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type.startswith("text/") or "html" in content_type:
                raise ValueError("Publisher returned a webpage instead of an image")
            data = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                data.extend(chunk)
                if len(data) > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Image exceeds download limit")
        with Image.open(io.BytesIO(data)) as original:
            if original.width * original.height > MAX_IMAGE_PIXELS:
                raise ValueError("Image dimensions exceed safety limit")
            picture = ImageOps.exif_transpose(original)
            picture.thumbnail((1100, 720), Image.Resampling.LANCZOS)
            if picture.mode in ("RGBA", "LA") or "transparency" in picture.info:
                rgba = picture.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                picture = background
            else:
                picture = picture.convert("RGB")
            for quality in (78, 65):
                output = io.BytesIO()
                picture.save(output, format="JPEG", quality=quality, optimize=True)
                if output.tell() <= MAX_INLINE_BYTES:
                    return output.getvalue()
            raise ValueError("Optimized image exceeds attachment limit")
    except (requests.RequestException, OSError, ValueError, TypeError,
            UnidentifiedImageError, Image.DecompressionBombError) as exc:
        LOG.warning("Skipping unavailable publisher image %s: %s", url, exc)
        return None


def prepare_images(stories, movies=None, preview=False):
    """Replace remote photos with inline CIDs (email) or data URLs (HTML preview).

    Never leave an external image src behind in a delivered email. If retrieval
    fails, omit the image and preserve the article/poster text and links.
    """
    prepared_stories = [{**story, "image": ""} for story in stories]
    prepared_movies = [{**movie, "poster": ""} for movie in (movies or [])]
    attachments = {}

    def inline_src(source, cid):
        jpeg = download_jpeg(source)
        if not jpeg:
            return ""
        if preview:
            return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        attachments[cid] = jpeg
        return "cid:" + cid

    # Match the newsletter's visual article order, not the model's grouping order.
    ordered = prepared_stories[:1]
    for category in ("politics", "local", "entertainment", "technology", "gaming", "obituaries"):
        ordered.extend(sorted(
            (story for story in prepared_stories[1:] if story["category"] == category),
            key=lambda story: story["published"], reverse=True))
    image_count = 0
    attempts = 0
    originals = {story["id"]: story.get("image") for story in stories}
    for story in ordered:
        source = originals.get(story["id"])
        if not source or image_count >= MAX_ARTICLE_IMAGES or attempts >= MAX_ARTICLE_ATTEMPTS:
            continue
        attempts += 1
        cid = "roundup-article-" + str(image_count + 1)
        story["image"] = inline_src(source, cid)
        if story["image"]:
            image_count += 1

    for index, movie in enumerate(prepared_movies[:5], start=1):
        source = (movies or [])[index - 1].get("poster")
        if source:
            movie["poster"] = inline_src(source, "roundup-poster-" + str(index))

    LOG.info("Prepared %d inline images for %s",
             len(attachments) if not preview else
             sum(bool(story["image"]) for story in prepared_stories) +
             sum(bool(movie["poster"]) for movie in prepared_movies),
             "email" if not preview else "preview")
    return prepared_stories, prepared_movies, attachments
