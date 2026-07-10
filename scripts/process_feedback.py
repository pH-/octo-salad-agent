"""
Processes a feedback issue. Triggered by GitHub Actions when an issue opens.

Issue title conventions (case-insensitive):
  reject: Recipe Name      -> never suggest again
  favorite: Recipe Name    -> shorter cooldown (repeat every ~2 weeks)
  unfavorite: Recipe Name  -> back to normal 30-day cooldown
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFS_PATH = ROOT / "data" / "preferences.json"

title = os.environ["ISSUE_TITLE"].strip()

with open(PREFS_PATH) as f:
    prefs = json.load(f)

lower = title.lower()


def norm_list(lst):
    return [x for x in lst]


if lower.startswith("reject:"):
    name = title.split(":", 1)[1].strip()
    if name and name.lower() not in {r.lower() for r in prefs["rejected_forever"]}:
        prefs["rejected_forever"].append(name)
    prefs["favorites"] = [f for f in prefs["favorites"] if f.lower() != name.lower()]
    action = f"Rejected forever: {name}"
elif lower.startswith("favorite:"):
    name = title.split(":", 1)[1].strip()
    if name and name.lower() not in {f.lower() for f in prefs["favorites"]}:
        prefs["favorites"].append(name)
    prefs["rejected_forever"] = [
        r for r in prefs["rejected_forever"] if r.lower() != name.lower()
    ]
    action = f"Added favorite: {name}"
elif lower.startswith("unfavorite:"):
    name = title.split(":", 1)[1].strip()
    prefs["favorites"] = [f for f in prefs["favorites"] if f.lower() != name.lower()]
    action = f"Removed favorite: {name}"
else:
    print("Issue title doesn't match reject:/favorite:/unfavorite: — ignoring.")
    sys.exit(0)

with open(PREFS_PATH, "w") as f:
    json.dump(prefs, f, indent=2)
    f.write("\n")

print(action)
