# Your Daily News Roundup 📰

Automated, newspaper-style daily newsletter with up to 12 useful articles, emailed to **barronejorge@gmail.com** from **yourdailynewsroundup@gmail.com**.

Focus: factual and politically neutral national politics, local Los Angeles / Pasadena / South Pasadena / Alhambra news, confirmed notable deaths, technology, and gaming.

**Schedule:** 9 AM Los Angeles time daily (GitHub Actions is best-effort, and runs can be delayed). Runs at both 16:00 and 17:00 UTC; the workflow checks local LA time to handle daylight saving time.

## Setup: do this before the first email

1. Create a Gemini API key at https://aistudio.google.com/apikey . The model in config.json defaults to `gemini-2.5-flash`; verify it is available in your free tier.
2. Sign in to the dedicated sender Gmail. Enable 2-Step Verification and generate a **Google App Password** at https://myaccount.google.com/apppasswords . This option may be unavailable for some accounts.
3. In the GitHub repository go to **Settings → Secrets and variables → Actions → New repository secret**. Add `GEMINI_API_KEY` and `GMAIL_APP_PASSWORD` (the sender's app password, **not** its normal password). Never commit or share the secrets.
4. Go to **Actions → Daily News Roundup → Run workflow**. Keep **preview_only** checked. Download the **newsletter-preview** workflow artifact and open `preview.html`.
5. Once the preview looks good, run manually with **preview_only unchecked** to send a test email. Scheduled runs will also send when both secrets have been configured.

**Important:** This version sends via Gmail SMTP using an app password rather than OAuth. It does not need Gmail API credentials. If Google does not offer app passwords for your account, a Gmail OAuth or email-service integration would be needed instead.

## How it works

- Fetches the RSS feeds in `config.json`, keeping approximately the last 30 hours of news.
- Sends headlines and short RSS excerpts to Gemini to select up to 12 relevant stories and generate original one-paragraph summaries.
- Builds a mobile-friendly newspaper-style HTML email with links to original sources.
- Stores identifiers of sent stories in `history.json` so the same exact links are not resent.
- Skips sending when no qualifying stories appear.

Because many RSS feeds contain only excerpts, **this initial version uses one-paragraph summaries** rather than inventing two-paragraph article summaries. It does not reproduce copyrighted articles. Feed endpoints are starting points and should be checked and replaced if publishers change them.

## Local preview

```bash
python -m pip install -r requirements.txt
# Set GEMINI_API_KEY as an environment variable
python newsletter.py --preview
```

Then open `preview.html` in a browser.

## Security and limitations

This is a **public repository**. Store credentials in GitHub Actions Secrets only. Scheduled Actions can be delayed; a run delayed past the 9 AM local hour may skip that day. Feeds may fail or omit stories, and Gemini summaries should be checked against original linked reporting for important facts. Deduplication is by article URL rather than by event across publishers.
