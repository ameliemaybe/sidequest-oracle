# Side Quest Oracle 🜲

Random Telegram pings throughout the day with oddly-specific creative side quests, generated fresh by Claude each time. Built for the neurospicy mind that needs external structure but hates predictable productivity apps.

## What it does

- Runs on GitHub Actions every ~90 minutes during waking hours
- Each tick has a 50% chance to actually fire (variable reward schedule = not predictable = brain stays engaged)
- Picks a random energy level (low/medium/high, weighted toward low) and domain (tarot, music, reading, language, curiosity, movement)
- Asks Claude to generate a fresh, specific, slightly-weird quest
- Sends to Telegram with Accept/Reroll/Skip buttons
- Logs completed quests to avoid repetition

## Setup (~15 min)

### 1. Create a Telegram bot
1. Open Telegram, search `@BotFather`
2. Send `/newbot`, follow prompts
3. Save the **bot token** it gives you
4. Send your new bot any message ("hi") so it can reply to you later
5. Search `@userinfobot`, send any message, save your **chat ID** (it's a number)

### 2. Get an Anthropic API key
1. Go to https://console.anthropic.com
2. Create an API key
3. Add a small amount of credit ($5 will last months at this volume)

### 3. Create a public GitHub repo
1. New repo, **must be public** for free Actions minutes
2. Upload these files:
   - `quest.py`
   - `.github/workflows/oracle.yml`

### 4. Add secrets
In your repo: Settings → Secrets and variables → Actions → New repository secret

Add three:
- `TELEGRAM_TOKEN` — from BotFather
- `TELEGRAM_CHAT_ID` — your chat ID number
- `ANTHROPIC_API_KEY` — from console.anthropic.com

### 5. Test it
- Actions tab → "side-quest-oracle" → "Run workflow" (manual trigger)
- Within ~30 seconds you should get a Telegram ping
- If not: check the Actions log for errors

## Tuning

In `quest.py`:
- `FIRE_PROBABILITY` — lower = rarer pings. 0.5 ≈ 3-4/day. 0.3 ≈ 2/day.
- `ENERGY_WEIGHTS` — bias toward low/medium/high quests
- `DOMAINS` — remove any you don't want

In `.github/workflows/oracle.yml`:
- `cron` schedule — adjust hours. Note: GitHub uses UTC by default. As of March 2026 you can add `timezone: "America/Los_Angeles"` to use local time directly.

## Known quirks

- **Cron is approximate.** GitHub may delay scheduled runs by 10-30 minutes during high load. This is actually fine for our purposes — the unpredictability is a feature.
- **Don't make the repo private** unless you want to pay for Actions minutes.
- **Inline buttons don't do anything yet.** The Accept/Reroll/Skip buttons send callbacks to Telegram but nothing receives them — adding that requires a webhook server (separate project). For now the buttons are just UI; you complete quests in your head. If you want real button handling, ask and we'll build a webhook receiver.

## Why this design

- **Variable reward schedule** beats fixed schedules for engagement (this is also why Instagram works)
- **Generated, not curated** keeps quests from getting predictable
- **No streaks, no points** — those collapse the moment you miss a day
- **External structure** because self-direction from bed is the broken part
