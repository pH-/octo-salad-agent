"""
Weekly salad menu agent.

Runs every Friday via GitHub Actions:
1. Loads preferences (rejected/favorite recipes, greens rules) and history.
2. Asks Claude (with web search) to build next week's Mon-Sun salad menu.
3. Emails the menu + weekend prep plan.
4. Commits the new menu into data/history.json so cooldown rules work.
"""

import json
import os
import smtplib
import sys
import urllib.request
from datetime import date, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFS_PATH = ROOT / "data" / "preferences.json"
HISTORY_PATH = ROOT / "data" / "history.json"

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", GMAIL_ADDRESS)

MODEL = "claude-sonnet-4-5"


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def recipes_on_cooldown(history, prefs, today):
    """Return recipe names that may NOT be used this week."""
    default_cd = prefs["cooldowns"]["default_days"]
    fav_cd = prefs["cooldowns"]["favorite_days"]
    favorites = {f.lower() for f in prefs["favorites"]}
    blocked = set()
    for week in history["weeks"]:
        week_date = datetime.strptime(week["week_of"], "%Y-%m-%d").date()
        age_days = (today - week_date).days
        for r in week["recipes"]:
            name = r["name"]
            cd = fav_cd if name.lower() in favorites else default_cd
            if age_days < cd:
                blocked.add(name)
    return sorted(blocked)


def build_prompt(prefs, blocked, next_monday):
    greens = prefs["greens_preferences"]
    replace_rules = "\n".join(
        f"  - Replace {k} with {v}" for k, v in greens["replace_always"].items()
    )
    rejected = "\n".join(f"  - {r}" for r in prefs["rejected_forever"]) or "  (none)"
    cooldown = "\n".join(f"  - {r}" for r in blocked) or "  (none)"
    favorites = "\n".join(f"  - {r}" for r in prefs["favorites"]) or "  (none)"
    rules = "\n".join(f"- {r}" for r in prefs["dietary_rules"])
    sources = "\n".join(f"- {s}" for s in prefs["seed_sources"])

    return f"""You are a meal-planning agent. Build a vegetarian salad dinner menu for the week starting Monday {next_monday}.

Search the web for recipes. Start with these sources, but also search more broadly for variety:
{sources}

HARD RULES:
{rules}

GREENS RULES:
- Preferred greens: {", ".join(greens["preferred"])}
- If a recipe uses any of the following, adapt the recipe with the substitution and note it:
{replace_rules}

NEVER use these recipes (rejected by the user, permanently):
{rejected}

Do NOT use these recipes this week (recently used, on cooldown):
{cooldown}

The user LOVES these (fine to bring back once off cooldown, and seek out similar styles):
{favorites}

{prefs["notes_to_agent"]}

OUTPUT FORMAT — respond with ONLY a JSON object, no markdown fences, no commentary:
{{
  "menu": [
    {{"day": "Monday", "name": "...", "url": "...", "protein": "...", "substitutions": "... or empty string", "night_of_steps": "what to do in <10 min that night"}}
    ... 7 days ...
  ],
  "weekend_prep": {{
    "saturday": ["step 1", "step 2"],
    "sunday": ["step 1", "step 2"]
  }},
  "bean_schedule": [
    {{"bean": "chickpeas", "dried_amount": "1.5 cups", "soak": "Saturday 9pm, 12h", "cook": "Sunday, simmer 60-90 min", "used_in": ["Tuesday", "Thursday"]}}
  ],
  "shopping_list": {{
    "produce": ["..."],
    "dried_beans_legumes": ["..."],
    "dairy_and_other": ["..."],
    "pantry_check": ["items user likely has: olive oil, vinegar, ..."]
  }}
}}"""


def call_claude(prompt):
    body = {
        "model": MODEL,
        "max_tokens": 8000,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.load(resp)

    text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
    # Strip accidental markdown fences and find the JSON object
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in model response:\n{text[:2000]}")
    return json.loads(text[start : end + 1])


def render_email(plan, next_monday):
    rows = ""
    for item in plan["menu"]:
        subs = f"<br><em>Substitution: {item['substitutions']}</em>" if item.get("substitutions") else ""
        rows += (
            f"<tr><td><b>{item['day']}</b></td>"
            f"<td><a href='{item['url']}'>{item['name']}</a>"
            f"<br>Protein: {item['protein']}{subs}"
            f"<br>Night of: {item['night_of_steps']}</td></tr>"
        )

    def ul(items):
        return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"

    beans = ""
    for b in plan.get("bean_schedule", []):
        beans += (
            f"<li><b>{b['bean']}</b> — {b['dried_amount']} dried. "
            f"Soak: {b['soak']}. Cook: {b['cook']}. Used: {', '.join(b['used_in'])}</li>"
        )

    sl = plan["shopping_list"]
    html = f"""
    <h2>🥗 Salad menu — week of {next_monday}</h2>
    <table border="1" cellpadding="6" cellspacing="0">{rows}</table>

    <h3>🫘 Bean soak & cook schedule</h3><ul>{beans}</ul>

    <h3>📋 Weekend prep</h3>
    <b>Saturday</b>{ul(plan["weekend_prep"]["saturday"])}
    <b>Sunday</b>{ul(plan["weekend_prep"]["sunday"])}

    <h3>🛒 Shopping list</h3>
    <b>Produce</b>{ul(sl["produce"])}
    <b>Dried beans & legumes</b>{ul(sl["dried_beans_legumes"])}
    <b>Dairy & other</b>{ul(sl["dairy_and_other"])}
    <b>Pantry check</b>{ul(sl["pantry_check"])}

    <hr>
    <p><b>Feedback:</b> open an issue in the repo titled
    <code>reject: Recipe Name</code> (never see it again),
    <code>favorite: Recipe Name</code> (repeat every 2 weeks instead of monthly), or
    <code>unfavorite: Recipe Name</code>.</p>
    """
    return html


def send_email(html, next_monday):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🥗 Your salad menu + weekend prep — week of {next_monday}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [RECIPIENT_EMAIL], msg.as_string())


def main():
    prefs = load_json(PREFS_PATH)
    history = load_json(HISTORY_PATH)

    today = date.today()
    next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)

    blocked = recipes_on_cooldown(history, prefs, today)
    prompt = build_prompt(prefs, blocked, next_monday.isoformat())

    plan = call_claude(prompt)

    # Guard: refuse rejected recipes even if the model slips
    rejected = {r.lower() for r in prefs["rejected_forever"]}
    bad = [m["name"] for m in plan["menu"] if m["name"].lower() in rejected]
    if bad:
        print(f"Model returned rejected recipes {bad}; retrying once...")
        plan = call_claude(prompt + f"\n\nIMPORTANT: You included rejected recipes: {bad}. Replace them.")

    html = render_email(plan, next_monday.isoformat())
    send_email(html, next_monday.isoformat())

    history["weeks"].append(
        {
            "week_of": next_monday.isoformat(),
            "generated_on": today.isoformat(),
            "recipes": [
                {"day": m["day"], "name": m["name"], "url": m["url"]} for m in plan["menu"]
            ],
        }
    )
    save_json(HISTORY_PATH, history)
    print("Menu generated, emailed, and saved to history.")


if __name__ == "__main__":
    sys.exit(main())
