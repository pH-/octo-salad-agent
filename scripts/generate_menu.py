"""
Weekly salad menu agent (GitHub Pages edition).

Runs every Friday:
1. Loads preferences and history.
2. Asks Claude (with web search) for next week's Mon-Sun menu, including full
   ingredient lists per recipe.
3. Saves data/current_menu.json, appends to data/history.json, rebuilds docs/.
The workflow commits everything; GitHub Pages serves docs/.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_site import build
from claude_api import call_claude_json

ROOT = Path(__file__).resolve().parent.parent
PREFS_PATH = ROOT / "data" / "preferences.json"
HISTORY_PATH = ROOT / "data" / "history.json"
CURRENT_PATH = ROOT / "data" / "current_menu.json"


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def recipes_on_cooldown(history, prefs, today):
    default_cd = prefs["cooldowns"]["default_days"]
    fav_cd = prefs["cooldowns"]["favorite_days"]
    favorites = {f.lower() for f in prefs["favorites"]}
    blocked = set()
    for week in history["weeks"]:
        week_date = datetime.strptime(week["week_of"], "%Y-%m-%d").date()
        age = (today - week_date).days
        for r in week["recipes"]:
            cd = fav_cd if r["name"].lower() in favorites else default_cd
            if age < cd:
                blocked.add(r["name"])
    return sorted(blocked)


MENU_ITEM_SCHEMA = """{"day": "Monday", "name": "...", "url": "...", "protein": "...",
 "substitutions": "... or empty string",
 "ingredients": ["1 cup cooked chickpeas (from 1/2 cup dried)", "..."],
 "night_of_steps_list": ["step 1", "step 2"],
 "agent_notes": []}"""


def build_prompt(prefs, blocked, next_monday):
    greens = prefs["greens_preferences"]
    replace_rules = "\n".join(
        f"  - Replace {k} with {v}" for k, v in greens["replace_always"].items()
    )
    fmt = lambda lst: "\n".join(f"  - {r}" for r in lst) or "  (none)"
    rules = "\n".join(f"- {r}" for r in prefs["dietary_rules"])
    sources = "\n".join(f"- {s}" for s in prefs["seed_sources"])

    return f"""You are a meal-planning agent. Build a vegetarian salad dinner menu for the week starting Monday {next_monday}.

Search the web for recipes. Start with these sources, but also search more broadly:
{sources}

HARD RULES:
{rules}

GREENS RULES:
- Preferred greens: {", ".join(greens["preferred"])}
- Adapt recipes with these substitutions and note them:
{replace_rules}

NEVER use these recipes (permanently rejected):
{fmt(prefs["rejected_forever"])}

Do NOT use these this week (on cooldown):
{fmt(blocked)}

User favorites (seek out similar styles):
{fmt(prefs["favorites"])}

{prefs["notes_to_agent"]}

Include the FULL ingredient list for each recipe (with quantities, noting dried bean
amounts where relevant).

OUTPUT — respond with ONLY a JSON object, no markdown fences:
{{
  "week_of": "{next_monday}",
  "menu": [ {MENU_ITEM_SCHEMA} ... 7 days Monday-Sunday ... ],
  "weekend_prep": {{"saturday": ["..."], "sunday": ["..."]}},
  "bean_schedule": [
    {{"bean": "chickpeas", "dried_amount": "1.5 cups", "soak": "Saturday 9pm, 12h",
      "cook": "Sunday, simmer 60-90 min", "used_in": ["Tuesday", "Thursday"]}}
  ],
  "shopping_list": {{"produce": ["..."], "dried_beans_legumes": ["..."],
    "dairy_and_other": ["..."], "pantry_check": ["..."]}}
}}"""


def main():
    prefs = load_json(PREFS_PATH)
    history = load_json(HISTORY_PATH)

    today = date.today()
    next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)

    blocked = recipes_on_cooldown(history, prefs, today)
    prompt = build_prompt(prefs, blocked, next_monday.isoformat())
    plan = call_claude_json(prompt)

    rejected = {r.lower() for r in prefs["rejected_forever"]}
    bad = [m["name"] for m in plan["menu"] if m["name"].lower() in rejected]
    if bad:
        print(f"Model returned rejected recipes {bad}; retrying once...")
        plan = call_claude_json(
            prompt + f"\n\nIMPORTANT: You included rejected recipes: {bad}. Replace them."
        )

    plan["week_of"] = next_monday.isoformat()
    save_json(CURRENT_PATH, plan)

    history["weeks"].append(
        {
            "week_of": next_monday.isoformat(),
            "generated_on": today.isoformat(),
            "recipes": [
                {"day": m["day"], "name": m["name"], "url": m["url"]}
                for m in plan["menu"]
            ],
        }
    )
    save_json(HISTORY_PATH, history)

    build(os.environ.get("GITHUB_REPOSITORY", ""))
    print("Menu generated, site built.")


if __name__ == "__main__":
    sys.exit(main())
