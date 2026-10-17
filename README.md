# Your Daily News Roundup 📰

A custom-branded newspaper-style **daily HTML newsletter** powered by Python, RSS and Google Gemini. Editorial interests are factual politics, Los Angeles / Pasadena / South Pasadena / Alhambra, confirmed notable deaths, technology and gaming. **Up to 12 stories; no filler.**

**Schedule:** 9 AM America/Los_Angeles every day (GitHub Actions operates on a best-effort schedule).

## What's new

- A unique **blackletter-inspired masthead**, generated from open-licensed UnifrakturCook, rather than using any newspaper's actual logo.
- Featured front-page headline, thick rules, classic serif article headlines and columns that reflow on mobile.
- Relevant article photos where the publisher explicitly supplies a picture in its RSS media fields, with attribution and a link to its original article. A blocked/absent image is simply omitted.
- Expanded local feeds from Pasadena Now, LAist, the South Pasadenan, Pasadena Star-News, San Gabriel Valley Tribune and LA Times. A publisher feed may change or reject connections; failure of a single feed doesn't abort the job.
- Soft category targets: 3 politics, 3 local, 2 technology, 1 gaming, 1 notable death; leftover slots for the strongest news of the day. The newsletter never manufactures filler to reach 12 stories.
- Event-level grouping across independent reporting, with links to other coverage for applicable stories. This helps cross-check political claims **when multiple independent sources are actually present**, but is not a fact-checking guarantee.
- Recent-headline matching to reduce repeating the same event across sources and days.
- One short paragraph per story, optionally two when RSS material supports it. This is original paraphrasing rather than reproducing copyrighted articles.

## Secure installation

This is a **public repo**: never commit API keys, app passwords, personal email addresses or local environment files. Set these **four repository secrets** under GitHub Settings → Secrets and variables → Actions:

| Secret name | Meaning |
| --- | --- |
| GEMINI_API_KEY | Gemini key from https://aistudio.google.com/apikey |
| GMAIL_APP_PASSWORD | Dedicated Gmail sender account's App Password, not its ordinary login password |
| NEWSLETTER_SENDER_EMAIL | Newsletter sender address |
| NEWSLETTER_RECIPIENT_EMAIL | Newsletter recipient address |

To create an App Password, enable Google two-step verification and use https://myaccount.google.com/apppasswords . Values are read at runtime; neither email address is kept in a committed config file.

## Preview or send manually

1. Go to **Actions → Daily News Roundup → Run workflow**.
2. Leave **preview_only** checked. When the run succeeds, download the **newsletter-preview** artifact and open the included HTML file.
3. For a one-time live delivery test, run the workflow again with **preview_only** unchecked. The scheduled workflow also sends automatically.

To generate a preview locally, install packages from requirements.txt, export GEMINI_API_KEY and run the script with the --preview argument:

    python -m pip install -r requirements.txt
    python newsletter.py --preview

Open preview.html locally. A local delivery additionally requires the three email-related environment variables.

## How it works

1. Collects publisher RSS items with timestamps from approximately the last 30 hours.
2. Builds a balanced sample of articles from all configured categories.
3. Uses Gemini to rank only useful stories, merge same-event coverage, cautiously summarize the supplied reporting and avoid already-covered headlines.
4. Applies soft category allocation targets and a conservative duplicate check.
5. Generates a unique masthead PNG using the open-licensed [UnifrakturCook](https://github.com/google/fonts/tree/main/ofl/unifrakturcook) font. The outgoing mail embeds this masthead as a CID image. No font file is committed or shared.
6. Builds HTML in old-fashioned newspaper styling, including publisher RSS images where available.
7. Sends via Gmail SMTP and saves URL hashes and public news headlines in history.json only after a successful send.

## Limitations and licensing

- Automated news summarization can be imperfect. Political reports are compared **where multiple feeds actually cover the same event**. If only one source is available, do not assume independent confirmation.
- Article photos are remote links provided by the respective publisher RSS feeds, not downloaded or hosted by this project. They may be blocked by mail clients and remain subject to publishers' reuse terms. Do not assume they are licensed for public redistribution.
- The blackletter typeface is released under the [SIL Open Font License 1.1](https://openfontlicense.org/). It is downloaded at runtime, never committed.
- RSS snippets do not always contain enough information to give an in-depth account, and the tool deliberately avoids copying full articles or bypassing paywalls.
- The scheduled workflow has 16:00 and 17:00 UTC triggers and checks whether it is 9 AM local time in Los Angeles. Late GitHub runs can miss this window.
- **Privacy note:** Previous public Git commits contained email addresses later removed from all current files. Changing current files does NOT remove them from old commit history. A carefully coordinated history rewrite would be required for full historical removal.
- history.json contains URL hashes and publicly available headlines; no email addresses or credentials are stored there.

## Source files

- newsletter.py — RSS reading, deduplication, Gemini curation, custom design and email delivery.
- config.json — non-sensitive feed list, section settings and model.
- history.json — sent article IDs and headlines.
- requirements.txt — Python dependencies.
- .github/workflows/daily.yml — delivery schedule and HTML preview.
- tests/test_newsletter.py — offline tests.
