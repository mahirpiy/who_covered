# Chalk Report — X/Twitter Bot

Posts one tweet per football game, as soon as that game goes final, saying
whether the chalk covered the closing spread.

Covers **NFL** and **college football** (all divisions).

Follow the bot: [@ChalkReport](https://x.com/ChalkReport)

## How it works

1. Every couple of minutes, poll ESPN's scoreboard for each league.
2. For any game newly marked final, fetch that game's closing spread.
3. Grade it, compose a tweet, post it, and record the game in SQLite.

The SQLite record is what makes the bot safe to restart — a game already in
the table is never posted twice.

## Data source

Both scores and spreads come from ESPN's public endpoints. **No API key, no
cost.**

| | Endpoint |
|---|---|
| Scores | `site.api.espn.com/apis/site/v2/sports/football/{league}/scoreboard` |
| Spreads | `sports.core.api.espn.com/v2/sports/football/leagues/{league}/events/{id}/competitions/{id}/odds` |

Lines are ESPN BET. The odds endpoint keeps the closing spread and price after
a game ends, so the bot fetches the line at grading time rather than having to
snapshot it before kickoff.

These endpoints are undocumented and carry no stability guarantee. The parsers
fail loud — a game with no usable line is skipped and retried next pass, never
tweeted with a guessed number.

## Running it

Print-only is the default. Nothing is posted without `--live`.

```bash
python3 -m venv env && env/bin/pip install -r requirements.txt
```

Grade one past slate:

```bash
PYTHONPATH=src env/bin/python src/bot.py --leagues cfb --date 20260905 --once
```

Poll continuously (still print-only):

```bash
PYTHONPATH=src env/bin/python src/bot.py --leagues nfl cfb --interval 120
```

### Options

| Flag | Meaning |
|---|---|
| `--leagues nfl cfb` | Leagues to poll. Default: both. |
| `--interval 120` | Seconds between polls. Default: 120. |
| `--once` | Single pass, then exit. Use for cron. |
| `--date YYYYMMDD` | Grade specific Eastern dates. For backfill. |
| `--live` | Actually post. Requires Twitter credentials. |
| `--seed` | Record games without tweeting. Backfill before going live. |
| `--seed-on-empty` | With `--live`, seed the first pass instead of refusing when the database is blank. |
| `--pace 20` | Seconds between posted tweets. Default: 20. |
| `--db PATH` | SQLite path. Default: `$CHALK_REPORT_DB`. |

With no `--date`, the bot polls today and yesterday in US Eastern, so late
kickoffs that finish after midnight are still picked up.

## Tests

```bash
env/bin/pip install -r requirements-dev.txt
env/bin/python -m pytest tests -q
```

51 tests over recorded ESPN payloads in `tests/fixtures/`, covering grading
(cover, push, unit math, away-favorite spread flip), season boundaries,
dedupe, seeding, the empty-database refusal, and failure isolation.

## Docker

SQLite is embedded — there is no database server. Compose runs the bot and
keeps the database file on a named volume so it survives rebuilds.

```bash
docker compose up --build
```

Inspect the database:

```bash
docker compose run --rm sqlite
```

## Deploying to Railway

Runs as a **long-running service with a volume**, not a Railway cron job.
Railway crons are UTC-only, cannot fire more often than every 5 minutes, and
volume support on them is undocumented -- a plain service gets 2-minute
polling and a volume that is definitely supported.

### How the start command works

[railway.json](railway.json) sets the start command to:

```
sh -c "python src/bot.py $BOT_ARGS"
```

Everything the bot does is driven by the **`BOT_ARGS` service variable**. This
matters because Railway's config file *overrides* dashboard settings -- a
`startCommand` hardcoded in `railway.json` could not be changed from the UI.
Variables are not overridden, so changing `BOT_ARGS` and redeploying is how
you move between phases.

`BOT_ARGS` defaults to print-only in the Dockerfile. Nothing posts until you
put `--live` in it.

### Setup

1. **Create the service** from this repo. Railway reads `railway.json` and
   builds the Dockerfile.

2. **Add a volume** (⌘K -> "New Volume", attach to the service) with mount
   path `/data`. The image points `CHALK_REPORT_DB` at
   `/data/chalk_report.db`. Without the volume the database resets on every
   deploy and the bot re-posts games.

3. **Set variables** on the service:

   | Variable | Value |
   |---|---|
   | `TWITTER_CONSUMER_KEY` | from the developer portal |
   | `TWITTER_CONSUMER_SECRET` | from the developer portal |
   | `TWITTER_ACCESS_TOKEN` | from `scripts/authorize.py` |
   | `TWITTER_ACCESS_TOKEN_SECRET` | from `scripts/authorize.py` |
   | `BOT_ARGS` | see phases below |

### Rollout phases

Change `BOT_ARGS`, redeploy, check the result, move on.

**Phase 1 -- one tweet, to prove the deploy works:**

```
--live --once --leagues cfb --limit 1 --date 20260829 20260903 20260904 20260905 20260906 20260907
```

Posts the single earliest game and exits. `restartPolicyType` is `ON_FAILURE`,
so a clean exit does not restart.

**Phase 2 -- backfill the rest:**

```
--live --once --leagues cfb --date 20260829 20260903 20260904 20260905 20260906 20260907
```

The volume already holds phase 1's game, so it is not repeated. Posts in
kickoff order at `--pace` seconds apart.

**Phase 3 -- steady state:**

```
--leagues nfl cfb --interval 120 --live --pace 20
```

Note there is no `--seed-on-empty` here. The volume is populated by now, so
the empty-database guard should never fire -- and if it ever does, that means
the volume was lost and you want the loud refusal rather than a silent
reseed.

### Constraints worth knowing

A service with a volume cannot run replicas, and Railway blocks two
deployments mounting the same volume at once -- which is exactly the guarantee
this bot needs, since two instances would double-post.

Inspect the database with the Railway CLI:

```bash
railway volume browse /
```

## Posting for real

ESPN needs no credentials. X does.

The developer app can live on your personal X account -- the app's consumer
key/secret identify the *app*, while the access token/secret identify the
*posting account*. To issue tokens for the bot account without moving the app
or its billing:

1. In the X developer portal, set the app's permissions to **Read and Write**.
   Authorizing under read-only produces a token that fails to post with a 403.
2. Run the authorization helper and approve while logged in as the bot
   account:

   ```bash
   env/bin/python scripts/authorize.py
   ```

   It prints an authorization URL, takes the PIN, verifies which account the
   tokens belong to, and writes all four credentials into `.env` (mode 600).
   Pass `--print` to display them instead.

3. Copy the same four values into the Railway service variables.

X also requires automated accounts to carry the **Automated label**, set in
the bot account's settings and linked to a human-managed account. Set it.

The bot refuses to post from an empty database, since the first pass would
tweet every game already final in the polling window. Either run `--seed` once
to backfill, or pass `--seed-on-empty` to absorb the first pass automatically
(what the Railway start command does).

X's API is pay-per-use as of 2026: **$0.015 per post, $0.20 if the post
contains a link.** The bot never includes a link. A full NFL + CFB season is
roughly 1,200 tweets, or about **$18**.

## Tweet format

```
🏈 CFB

✅ #LSU (-10) covered vs #Clemson

Final: LSU 51, CLEM 10
+0.89u

📊 CFB favorites 2026: +2.53u
```

Units assume a one-unit bet on the favorite at the closing price: a win pays
the price, a loss is -1.00, a push is 0.00.

The bottom line is that league's season-to-date total on favorites, including
the game just posted. **NFL and college are tracked separately** -- a CFB tweet
never shows NFL units and vice versa.

A season runs August through February, so January bowls and playoff games count
toward the previous year's season.
