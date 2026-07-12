"""
Handles interactive requests from the Pages site, triggered by issue creation.

Title formats:
  replace: Wednesday            -> regenerate that day's recipe
  substitute: Wednesday / tahini -> suggest alternatives for a missing ingredient

Prints the reply comment to a file (reply.md) that the workflow posts to the issue.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_site import build
from claude_api import call_claude, call_claude_json
from generate_menu import MENU_ITEM_SCHEMA

ROOT = Path(__file__).resolve().parent.parent
CURRENT_PATH = ROOT / "data" / "current_menu.json"
HISTORY_PATH = ROOT / "data" / "history.json"
PREFS_PATH = ROOT / "data" / "preferences.json"
REPLY_PATH = ROOT / "reply.md"

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def find_day(text):
    t = text.lower()
    for d in DAYS:
        if d in t:
            return d.capitalize()
    return None


def handle_replace(plan, prefs, day, reason):
    others = [m["name"] for m in plan["menu"] if m["day"] != day]
    current = next(m for m in plan["menu"] if m["day"] == day)
    history = json.loads(HISTORY_PATH.read_text())
    recent = {r["name"] for w in history["weeks"][-6:] for r in w["recipes"]}
    avoid = sorted(recent | set(others) | set(prefs["rejected_forever"]) | {current["name"]})

    greens = prefs["greens_preferences"]
    replace_rules = "\n".join(
        f"- Replace {k} with {v}" for k, v in greens["replace_always"].items()
    )
    prompt = f"""Find ONE replacement vegetarian salad recipe for {day} dinner. Search the web,
starting with {", ".join(prefs["seed_sources"])} but searching broadly.

The user asked to replace "{current["name"]}". Their reason: "{reason or "not given"}".
If the reason mentions unavailable ingredients, pick a recipe that avoids them.

HARD RULES:
{chr(10).join("- " + r for r in prefs["dietary_rules"])}

GREENS: prefer {", ".join(greens["preferred"])}.
{replace_rules}

Do NOT use any of these recipes:
{chr(10).join("- " + a for a in avoid)}

The shopping list was already planned around this week's other recipes, so prefer
overlapping ingredients where sensible.

OUTPUT — respond with ONLY a JSON object matching exactly this shape:
{MENU_ITEM_SCHEMA}
with "day" set to "{day}"."""

    new_item = call_claude_json(prompt)
    new_item["day"] = day
    for i, m in enumerate(plan["menu"]):
        if m["day"] == day:
            plan["menu"][i] = new_item

    # keep history in sync so cooldowns track what you'll actually eat
    history = json.loads(HISTORY_PATH.read_text())
    for w in history["weeks"]:
        if w["week_of"] == plan["week_of"]:
            for r in w["recipes"]:
                if r["day"] == day:
                    r["name"], r["url"] = new_item["name"], new_item["url"]
    HISTORY_PATH.write_text(json.dumps(history, indent=2) + "\n")

    return (
        f"✅ Replaced **{current['name']}** with **[{new_item['name']}]({new_item['url']})** "
        f"for {day}.\n\nThe site is rebuilding now — refresh the week page in a minute.\n"
        f"Note: the shopping list on the index page is not recalculated; check the new "
        f"recipe's ingredient list on its day page."
    )


def handle_substitute(plan, prefs, day, ingredient):
    item = next(m for m in plan["menu"] if m["day"] == day)
    prompt = f"""The user is making "{item["name"]}" ({item["url"]}) but is missing this
ingredient: "{ingredient}".

Recipe ingredients: {json.dumps(item["ingredients"])}

Suggest the 2-3 best substitutions using common home ingredients, with quantity
guidance and how each changes the flavor. Vegetarian only. Keep it under 120 words,
plain text, as a short bulleted list."""
    answer = call_claude(prompt, max_tokens=1000, web_search=False).strip()

    item.setdefault("agent_notes", []).append(f"Missing {ingredient}? {answer}")
    return f"🧂 Substitutes for **{ingredient}** in {day}'s {item['name']}:\n\n{answer}\n\n(Also added to the {day} recipe page.)"


def main():
    title = os.environ["ISSUE_TITLE"].strip()
    body = os.environ.get("ISSUE_BODY", "")
    lower = title.lower()

    plan = json.loads(CURRENT_PATH.read_text())
    prefs = json.loads(PREFS_PATH.read_text())

    day = find_day(title)
    if not day:
        REPLY_PATH.write_text(
            "⚠️ I couldn't find a weekday in the issue title. "
            "Use e.g. `replace: Wednesday` or `substitute: Wednesday / tahini`."
        )
        return

    if lower.startswith("replace:"):
        reply = handle_replace(plan, prefs, day, body.strip())
    elif lower.startswith("substitute:"):
        ingredient = title.split("/", 1)[1].strip() if "/" in title else ""
        if not ingredient or ingredient.upper() == "REPLACE_WITH_MISSING_INGREDIENT":
            REPLY_PATH.write_text(
                "⚠️ Please edit the issue title to name the missing ingredient after "
                "the slash, e.g. `substitute: Wednesday / tahini`, then open a new issue."
            )
            return
        reply = handle_substitute(plan, prefs, day, ingredient)
    else:
        REPLY_PATH.write_text("⚠️ Unrecognized request.")
        return

    CURRENT_PATH.write_text(json.dumps(plan, indent=2) + "\n")
    build(os.environ.get("GITHUB_REPOSITORY", ""))
    REPLY_PATH.write_text(reply)


if __name__ == "__main__":
    main()
