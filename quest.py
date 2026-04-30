"""
Side Quest Oracle — sends a randomly-timed quest to Telegram.

Runs on GitHub Actions cron. Each invocation:
  1. Rolls dice — sometimes does nothing (variable schedule, not predictable)
  2. If rolling through, picks a random energy + domain
  3. Asks Claude for a fresh quest
  4. Sends it to Telegram with accept/skip inline buttons
  5. Logs the quest to keep the repo non-dormant
"""

import os
import json
import random
import datetime
import urllib.request
import urllib.error
from pathlib import Path

# --- Config ---
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# Probability the bot actually fires this run. Lower = rarer = more lottery-like.
# Cron runs every 90 min during waking hours (set in workflow).
# 0.5 means roughly half of those runs send a quest = ~3-4 quests per day.
FIRE_PROBABILITY = 0.5

DOMAINS = ["tarot", "music", "reading", "language", "curiosity", "movement"]
ENERGY_LEVELS = ["low", "medium", "high"]
ENERGY_WEIGHTS = [0.5, 0.35, 0.15]  # mostly low/medium — high requires real activation

ENERGY_DESCRIPTIONS = {
    "low":    "5–15 minutes, very low effort, can be done from bed or near it",
    "medium": "20–35 minutes, requires some focus",
    "high":   "40+ minutes, requires real engagement and likely leaving the bed",
}

REWARD_FORMS = [
    ("✦", "a small omen"),
    ("☾", "a permission slip"),
    ("✧", "an unlocked door"),
    ("❋", "a tiny blessing"),
    ("◈", "a found object"),
    ("⌬", "a strange compliment"),
]

LOG_PATH = Path(".quest_log.jsonl")


def call_claude(prompt: str, max_tokens: int = 1000) -> str:
    """Call Anthropic API and return the text response."""
    body = json.dumps({
        "model": "claude-sonnet-4-5",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return next(c["text"] for c in data["content"] if c["type"] == "text").strip()


def recent_titles(n: int = 8) -> list[str]:
    """Read last N quest titles from log to avoid repetition."""
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text().strip().splitlines()[-n:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line)["title"])
        except Exception:
            pass
    return out


def generate_quest(energy: str, domain: str) -> dict:
    """Ask Claude for a fresh quest."""
    avoid = "; ".join(recent_titles()) or "none yet"
    prompt = f"""You are a quest-giver for a neurospicy creative person who has trouble starting things from bed. Generate ONE side quest.

CONSTRAINTS:
- Domain: {domain} (tarot=visual creative work / illustration / collage / symbolism, music=making music / sound, reading=engaging with text in interesting ways, language=language learning, curiosity=observation or noticing the world, movement=body / leaving bed / going outside)
- Energy/duration: {ENERGY_DESCRIPTIONS[energy]}
- Must be SPECIFIC and slightly weird/oddly specific — not generic advice. Not "read for 20 minutes" — instead "find a sentence in any book that sounds like a spell, copy it onto a sticky note, place it somewhere you'll forget about it"
- Avoid clichés: no "drink water", no "take 3 deep breaths", no "make your bed", no "write 3 things you're grateful for", no "go for a walk and notice 5 things"
- Tone: curious, playful, a little uncanny. Like a witchy friend texting you a dare.
- The quest should feel doable AND interesting enough that the brain wants to engage
- Recent quests to NOT repeat or echo: {avoid}

Return ONLY valid JSON, no markdown fences, no preamble:
{{
  "title": "5-9 word title with a bit of poetry to it",
  "body": "2-3 sentences explaining the quest specifically. Concrete actions. End with what 'done' looks like."
}}"""

    raw = call_claude(prompt, max_tokens=600)
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(cleaned)
    parsed["domain"] = domain
    parsed["energy"] = energy
    return parsed


def generate_reward(quest: dict) -> tuple[str, str, str]:
    """Generate a surprise reward sentence."""
    glyph, label = random.choice(REWARD_FORMS)
    prompt = f"""Someone just completed this quest: "{quest['title']}" — {quest['body']}

Give them a reward in the form of "{label}". This should be a single short sentence (12-25 words), poetic but not saccharine, slightly uncanny, never preachy or therapy-speak. Examples of the vibe:
- "The next stranger you make eye with knows something you'll need later this week."
- "You are hereby permitted to leave one email unanswered for 72 hours."
- "A small object near you is now lucky. You'll know which one."

Return ONLY the sentence, no quotes, no preamble."""
    try:
        text = call_claude(prompt, max_tokens=200)
    except Exception:
        text = "Small magic accumulates. You did the thing."
    return glyph, label, text


def send_telegram(quest: dict) -> None:
    """Send the quest to Telegram with inline accept/skip buttons."""
    glyph, label, reward_text = generate_reward(quest)

    # Pre-generate the reward and embed it in callback data
    # (so the user gets it instantly when they tap Accept)
    callback_accept = json.dumps({
        "a": "done",
        "g": glyph,
        "l": label,
        "r": reward_text[:180],  # callback_data has 64-byte limit per arg, we keep total under 1KB
        "t": quest["title"][:60],
    })
    # Telegram callback_data max 64 bytes — too tight. Use a short token instead.
    # For simplicity here: store reward in a file keyed by message timestamp.
    token = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    pending = Path(".pending_rewards.json")
    rewards = {}
    if pending.exists():
        try:
            rewards = json.loads(pending.read_text())
        except Exception:
            rewards = {}
    # prune old entries (keep last 50)
    if len(rewards) > 50:
        rewards = dict(list(rewards.items())[-50:])
    rewards[token] = {"glyph": glyph, "label": label, "text": reward_text, "title": quest["title"]}
    pending.write_text(json.dumps(rewards))

    text = (
        f"⌁  *{escape_md(quest['title'])}*\n"
        f"_{quest['domain']} · {quest['energy']} energy_\n\n"
        f"{escape_md(quest['body'])}"
    )

    keyboard = {
        "inline_keyboard": [[
            {"text": "✓ Accept", "callback_data": f"a:{token}"},
            {"text": "↻ Reroll", "callback_data": f"r:{token}"},
            {"text": "✗ Skip",   "callback_data": f"s:{token}"},
        ]]
    }

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
        "reply_markup": keyboard,
        "disable_notification": False,
    }
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def escape_md(s: str) -> str:
    """Escape Telegram MarkdownV2 special characters."""
    chars = r"_*[]()~`>#+-=|{}.!\\"
    return "".join(("\\" + c) if c in chars else c for c in s)


def log_quest(quest: dict) -> None:
    """Append to quest log (also keeps repo from going dormant)."""
    entry = {
        "ts": datetime.datetime.utcnow().isoformat(),
        "title": quest["title"],
        "domain": quest["domain"],
        "energy": quest["energy"],
    }
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    # Variable reward schedule: not every cron tick fires
    if random.random() > FIRE_PROBABILITY:
        print(f"Skipped this tick (probability {FIRE_PROBABILITY})")
        return

    energy = random.choices(ENERGY_LEVELS, weights=ENERGY_WEIGHTS)[0]
    domain = random.choice(DOMAINS)
    print(f"Generating: {energy} / {domain}")

    quest = generate_quest(energy, domain)
    print(f"Quest: {quest['title']}")

    send_telegram(quest)
    log_quest(quest)
    print("Sent.")


if __name__ == "__main__":
    main()
