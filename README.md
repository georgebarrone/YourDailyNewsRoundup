# Your Daily News Roundup 📰

A daily, newspaper-style HTML email digest powered by Python, RSS, and Google Gemini. The newsletter curates **up to 12** stories on factual, politically neutral current affairs, Los Angeles / Pasadena / South Pasadena / Alhambra, notable deaths, technology, and gaming.

**Schedule:** 9:00 AM America/Los_Angeles, daily (best effort; GitHub Actions can be delayed). The workflow checks local LA time on both 16:00 and 17:00 UTC runs to handle daylight saving time.

## Configure GitHub Actions Secrets

This repository is public. **Do not commit API keys, passwords, email addresses, or local .env files.**

In **Settings → Secrets and variables → Actions → New repository secret**, set these four secrets:

| Secret | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | API key from https://aistudio.google.com/apikey |
| `GMAIL_APP_PASSWORD` | Gmail App Password for the dedicated sender account (not the Gmail login password) |
| `NEWSLETTER_SENDER_EMAIL` | Dedicated sender's email address |
| `NEWSLETTER_RECIPIENT_EMAIL` | Inbox that receives the daily digest |

Enable 2-Step Verification on the sender's Google account and create the App Password at https://myaccount.google.com/apppasswords . Email addresses and credentials are **read from environment variables during a GitHub Actions run**, never stored in `config.json`.

**Existing installations:** After upgrading, add both new email-address secrets or mail sending will fail securely. The existing `GEMINI_API_KEY` and `GMAIL_APP_PASSWORD` secrets remain valid; no need to recreate them.

## Run manually

1. Open **Actions → Daily News Roundup → Run workflow**.
2. Leave `preview_only` checked to build a preview **without sending** an email.
3. After the run, download the `newsletter-preview` artifact and open `preview.html`.
4. To test sending, run the workflow again with `preview_only` unchecked.

Scheduled runs send the newsletter automatically (provided all secrets are configured). GitHub scheduling is best-effort; a delay beyond the allowed local-time hour can skip that day's run.

## How it works

- Fetches configured RSS feeds from approximately the last 30 hours.
- Uses Gemini (`gemini-3.8-flash` by default) to select important distinct stories and write short, original summaries based **only on RSS titles and excerpts**.
- Creates a mobile-friendly HTML newsletter and links back to original publishers.
- Saves hashes of emailed article URLs in `history.json` to avoid repeating exact links.
- Skips sending when no qualifying stories are found.

Some publisher feeds can become unavailable, and an RSS excerpt may not contain enough information to fully summarize a long article. Summaries are not the full copyrighted article; consult original reporting for details. Political stories should be evaluated against trustworthy sources; automated summaries may make errors.

## Local preview

```bash
python -m pip install -r requirements.txt
# Set GEMINI_API_KEY in your local environment, without committing it.
python newsletter.py --preview
```

Open `preview.html` in your browser. To send from your computer, set the other three environment variables securely as well.

## Security

- Never post secrets in issues, screenshots, chat, or commits.
- `.env` and `preview.html` are ignored by Git.
- The public Git history may still contain older file versions, even after current files are sanitized. A separate, carefully planned history rewrite would be necessary to remove older committed email addresses from commit history.
- News history tracks URL hashes; this is not a database of subscriber information.
