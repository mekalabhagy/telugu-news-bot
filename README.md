# Telugu News Channel Bot (Instagram)

Fetches trending Telugu headlines, rewrites them in Telugu with Claude, renders a branded
1080x1350 card, and posts it through the official Instagram Graph API on a schedule.

```
Google News (Telugu) + Google Trends  ->  group by story  ->  need >= 2 outlets
   -> Claude writes Telugu headline/summary/caption + flags sensitive stories
   -> Pillow renders card (generated art, no outlet photos)
   -> upload to public bucket -> Instagram container -> publish
   -> SQLite remembers it, so it is never posted twice
```

## 1. Try it now (no keys needed)

```bash
pip install -r requirements.txt
python main.py demo          # writes out/demo_1.jpg ... demo_3.jpg
```

On Linux, Pillow needs the Raqm library for correct Telugu conjuncts:
`sudo apt install libraqm0 libfribidi0 libharfbuzz0b` (Windows/macOS wheels include it).
Fonts (Noto Sans Telugu + Noto Sans, SIL OFL) are bundled in `fonts/`.

## 2. One-time accounts

1. **Instagram**: switch the account to Business or Creator and link it to a Facebook Page.
2. **Meta developer app**: create an app, add the Instagram API / Content Publishing permissions,
   and generate an access token. Note your **Instagram user ID**. Prefer a long-lived or
   System User token so it does not expire every 60 days. Publishing from your own account in
   development mode works without full app review.
3. **Claude API key** from the Anthropic Console.
4. **Public image bucket** (Instagram downloads the image from a URL). Cloudflare R2 or any
   S3-compatible bucket with public read works.

Copy `.env.example` to `.env` and fill it in.

## 3. Run

```bash
python main.py run --dry-run   # fetch + write + render, nothing posted (cards in out/)
python main.py run             # uses POST_MODE
python main.py list            # cards waiting for approval
python main.py approve --all   # publish them
```

## 4. Schedule it (free, in the cloud)

Push this folder to a **private** GitHub repo, then add:

- Secrets: `ANTHROPIC_API_KEY`, `IG_USER_ID`, `IG_ACCESS_TOKEN`, `S3_ENDPOINT`, `S3_BUCKET`,
  `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_PUBLIC_BASE_URL`
- Variables: `POST_MODE`, `CHANNEL_NAME`, `CHANNEL_HANDLE`

`post.yml` runs at 07:30, 12:30, 18:30 and 21:00 IST (edit the cron lines, they are in UTC).
GitHub may start scheduled jobs a few minutes late. The dedupe database is committed back to the
repo after each run.

## 5. Review mode first, then autonomous

- `POST_MODE=review` (default): each run queues cards; you publish with the **approve-queue**
  workflow (or `python main.py approve --all`). Run like this for 1-2 weeks and read what it writes.
- `POST_MODE=auto`: set the repository variable and it posts with no human step.

## Safeguards built in

| Safeguard | Setting |
|---|---|
| Story must appear in at least 2 outlets | `MIN_SOURCES` |
| Claude flags deaths/violence, crimes against women/children, communal or religious tension, active election/party attacks, unverified allegations, health scares; these are skipped | `SKIP_SENSITIVE` |
| Claude may only use facts in the headlines and must not add numbers, names or quotes | prompt in `summarize.py` |
| Output must be mostly Telugu or it is rejected | `summarize.py` |
| No outlet photos or text are copied; art is generated and wording is rewritten | `render.py` |
| Source credit and "AI-assisted" label on every card and caption | `render.py`, `publish.py` |
| Near-duplicate detection over the last 72 hours | `DEDUPE_HOURS` |

## Known limits

- Claude sees **headlines only**, not article bodies, so summaries stay short and conservative.
  If you want richer posts, add article fetching, but check each outlet's terms first.
- The "trending" signal is Google News ranking + number of outlets + Google Trends India.
  Edit `FEEDS` in `sources.py` to add direct RSS feeds from Telugu outlets.
- Keyword and LLM filters reduce risk but cannot eliminate it. Check the account weekly,
  especially after switching to `auto`.
- Meta limits how many posts an account can publish per day and takes action on spammy,
  unoriginal accounts. Keep the volume modest.
- The `sources.py` fetch was not testable in the build sandbox (network allowlist), so do a first
  `python main.py run --dry-run` on your side and check the output.
