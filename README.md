# 🥗 Salad Agent

An agent that publishes a vegetarian salad dinner menu to a **GitHub Pages site** every
Friday: a week overview (prep plan, dried-bean soak/cook schedule, shopping list) and
one page per day with full ingredients and interactive buttons.

## How it works

- **Every Friday** a GitHub Action asks Claude (with web search) to build a Mon–Sun
  menu and rebuilds the site in `docs/`.
- **Rules:** vegetarian, plant protein daily, no pasta/rice salads, dried beans (with
  soak/cook schedule), kale/chard/iceberg auto-replaced with spinach or mixed greens.
- **Memory:** menus are stored in `data/history.json`. Recipes repeat at most once a
  month (favorites: every 2 weeks). Rejected recipes never return.

## Buttons on the site (all open a pre-filled GitHub issue)

| Button | Issue title | What happens |
|---|---|---|
| 🔄 Replace this recipe | `replace: Wednesday` | A new recipe is generated for that day (mention unavailable ingredients in the issue body to avoid them) |
| 🧂 Missing an ingredient? | `substitute: Wednesday / tahini` | Substitution advice is posted on the issue and added to the day page |
| ⭐ Favorite | `favorite: Recipe Name` | Recipe can repeat every 2 weeks |
| 🚫 Reject | `reject: Recipe Name` | Recipe never appears again |

The corresponding Action runs, updates the site (~1 min), and closes the issue.

## Setup

1. Repo Settings → **Pages** → Source: *Deploy from a branch* → `main` / `/docs` → Save.
   Your site: `https://<username>.github.io/octo-salad-agent/`
   ⚠️ Pages on a **private** repo requires GitHub Pro/Team; otherwise make the repo public.
2. Add one secret (Settings → Secrets and variables → Actions):
   `ANTHROPIC_API_KEY` — from https://console.anthropic.com (weekly run costs cents).
3. Adjust the Friday cron in `.github/workflows/weekly-menu.yml` (cron is UTC).
4. Test: Actions tab → *Weekly salad menu* → Run workflow → open your Pages URL.

## Files

```
.github/workflows/weekly-menu.yml      # Friday cron: generate menu + build site
.github/workflows/handle-requests.yml  # replace:/substitute: issues
.github/workflows/feedback.yml         # reject:/favorite:/unfavorite: issues
scripts/generate_menu.py               # weekly agent
scripts/handle_request.py              # replace & substitute handler
scripts/build_site.py                  # renders docs/ from current_menu.json
scripts/claude_api.py                  # shared API helper
data/preferences.json                  # rules, favorites, rejections
data/history.json                      # every past menu (memory)
data/current_menu.json                 # this week's full plan (created on first run)
docs/                                  # the published site
```

## Customizing

Edit `data/preferences.json`: greens substitutions, cooldown lengths, seed recipe
sites, and plain-English `dietary_rules` / `notes_to_agent`.
