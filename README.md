# Your Daily News Roundup 📰

An independent, newspaper-style daily HTML email, powered by Python, publisher RSS feeds, Gemini, and GitHub Actions. It brings together up to twelve relevant news articles about factual politics, Los Angeles news, technology, gaming, confirmed notable deaths, movies, television, and entertainment, plus a separate weekly theatrical release guide.

**Delivery:** The primary attempt is at 9:00 AM Pacific daily (best effort). Backup attempts at 9:17 and 9:37 AM Pacific run only if the day's scheduled edition has not already been delivered. GitHub Actions may delay or drop any individual scheduled run.

## What the newsletter includes

- Custom blackletter-inspired masthead, featured headlines, serif typography, newspaper dividers, and mobile-friendly HTML.
- Up to 12 original news summaries with publisher links, balancing politics, Los Angeles-area news, major entertainment announcements, technology, gaming, and confirmed notable deaths.
- Publisher-provided article images, downloaded and optimized as inline email attachments when available, with source attribution and links to original reporting. Unavailable images are automatically omitted without broken-image placeholders.
- News without filler, duplication of same-event reporting, or unsupported claims of independent verification.
- **New at the Movies This Week:** a separate list of up to five U.S. theatrical movie openings (not counted toward the 12 news articles), with dates and film posters when available.

## Weekly movie releases and Regal

The movie guide **resets every Monday** to preview the *coming Thursday-through-Wednesday* theatrical release window, including films with Friday theatrical dates. Thursday through Sunday it continues showing the films that have just opened; beginning Monday it looks ahead to the next Thursday so Wednesday's newsletter includes tomorrow's releases. U.S. theatrical release dates come from the **TMDB (The Movie Database)** API, prioritizing wide theatrical openings and occasionally including limited theatrical runs.

The section also links to [Regal's official movie listings](https://www.regmovies.com/movies), where you can select a theater and verify showtimes or book tickets.

**Important:** A U.S. theatrical release date does not confirm that any particular Regal theater has the film. Exact Regal availability depends on the location. The digest is a Regal-oriented release guide, **not** a real-time Regal showtime feed.

Movie listings require an additional optional secret named **TMDB_API_KEY**. Without that key the rest of the email still works; the movie section can provide a Regal listings link rather than inventing releases.

TMDB's API is available for eligible noncommercial uses subject to its terms and attribution requirements. You can obtain a key in [TMDB API settings](https://www.themoviedb.org/settings/api).

## Secure configuration

This is a **public repository**. Never commit email addresses, secrets, keys, app passwords or local environment files.

Add these GitHub Actions Secrets under **Settings → Secrets and variables → Actions**:

| Secret name | Purpose |
| --- | --- |
| GEMINI_API_KEY | Summarizes publisher RSS excerpts |
| GMAIL_APP_PASSWORD | Gmail App Password for the newsletter sender (not the Gmail login password) |
| NEWSLETTER_SENDER_EMAIL | Newsletter sending address |
| NEWSLETTER_RECIPIENT_EMAIL | Receiving inbox |
| TMDB_API_KEY | **Optional:** enables verified U.S. theatrical movie release dates |

Gmail App Passwords require an account with 2-Step Verification, using https://myaccount.google.com/apppasswords .

Email addresses and credentials are read from environment variables at runtime, not from the repository. Older public Git commits may still contain previously removed metadata; editing this README does not erase Git history.

## Preview and send

1. Open **Actions → Daily News Roundup → Run workflow**.
2. Leave **preview_only** checked to generate an HTML preview artifact without emailing it.
3. Open the downloaded HTML preview in a browser.
4. For a delivery test, start a new workflow run with **preview_only** unchecked.

Once configured, the schedule targets 9:00 AM Pacific daily, with recovery attempts at 9:17 and 9:37 AM Pacific. The delivery-state guard records the date only after a successful scheduled email, avoiding additional sends on later attempts. Manual live tests still operate independently. GitHub Actions execution remains best effort.

Local preview:

    python -m pip install -r requirements.txt
    python newsletter.py --preview

Set GEMINI_API_KEY locally; optionally set TMDB_API_KEY to populate the theatrical release section. Do not commit local credentials.

## Files

- newsletter.py — publisher feeds, Gemini news curation, formatting, email delivery.
- movie_releases.py — optional TMDB movie listings that reset each Monday to the upcoming Thursday-to-Wednesday opening window.
- config.json — public RSS sources, topic quotas, and non-secret settings.
- history.json — sent article IDs and public headlines.
- delivery_state.json — most recently delivered scheduled edition date, preventing duplicate daily sends during retry windows.
- .github/workflows/daily.yml — scheduled delivery and manual previews.
- .github/workflows/check.yml — offline automated tests.
- tests/ — unit tests without real network, Gemini, or Gmail activity.

## Limitations and credits

- Summaries are derived from RSS excerpts, not complete copyrighted articles. Automated summarization may omit context; visit original sources for verification.
- Political claims are compared across independently published reports only when those sources are available; this is not a professional fact-checking service.
- Publisher RSS image URLs may expire, reject automated downloads, or return invalid formats. Each issue downloads and verifies candidate images with bounded time and size limits, then attaches successfully retrieved JPEGs directly to the email; failures are omitted cleanly. HTML previews include the successful pictures as data URLs. No image hosting service is required.
- The newsletter uses original blackletter-inspired artwork stored in `assets/masthead.png`. It is independently branded, not affiliated with another newspaper. The static PNG is embedded in previews and emails, without downloading a font at runtime.
- TMDB provides the optional theatrical-release data, movie details and posters. The movie section displays TMDB attribution and the notice: **"This product uses the TMDB API but is not endorsed or certified by TMDB."** See [TMDB attribution](https://www.themoviedb.org/about/logos-attribution) and [API terms](https://www.themoviedb.org/api-terms-of-use).
- U.S. theatrical listings do not guarantee Regal showtimes. Confirm on [Regal's website](https://www.regmovies.com/movies).
- GitHub scheduled Actions may be delayed or dropped, especially at the top of an hour. Backup attempts improve reliability but do not guarantee an exact delivery time.
