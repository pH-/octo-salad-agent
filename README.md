# 🥗 Salad Agent

An agent that emails you a vegetarian salad dinner menu every Friday, with a weekend
prep plan (including a dried-bean soak/cook schedule) and a shopping list.

## How it works

- **Every Friday** a GitHub Action calls the Claude API (with web search) to build a
  Mon–Sun menu, starting from theplantbasedschool.com and searching more broadly.
- **Rules baked in:** vegetarian, a plant protein every day, no pasta/rice salads,
  dried beans instead of canned, kale/chard/iceberg replaced with spinach or mixed greens.
- **Memory:** each week's menu is committed to `data/history.json`. Recipes repeat at
  most once a month (favorites: every 2 weeks). Rejected recipes never come back.
- **Feedback loop:** open a GitHub issue to teach it what you like:
  - `reject: Recipe Name` → banned forever
  - `favorite: Recipe Name` → eligible again after 2 weeks instead of 30 days
  - `unfavorite: Recipe Name` → back to the normal 30-day cooldown

  An Action updates `data/preferences.json` and closes the issue automatically.
  You can also just edit `data/preferences.json` directly in the GitHub UI.

## Setup (one time, ~15 min)

1. **Create the repo** — make it private, push these files.

2. **Get an Anthropic API key** at https://console.anthropic.com
   (a weekly run costs a few cents).

3. **Gmail app password** — in your Google account: Security → 2-Step Verification →
   App passwords → create one for "Mail".

4. **Add repository secrets** — repo Settings → Secrets and variables → Actions:

   | Secret | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | your API key |
   | `GMAIL_ADDRESS` | the Gmail account that sends the email |
   | `GMAIL_APP_PASSWORD` | the app password from step 3 |
   | `RECIPIENT_EMAIL` | where the menu goes (can be the same address) |

5. **Set your send time** — edit the cron in `.github/workflows/weekly-menu.yml`.
   Cron is UTC. Example: Friday 4pm Pacific = `0 23 * * 5` (winter) — pick what suits you.

6. **Test it** — Actions tab → "Weekly salad menu" → Run workflow. Check your inbox.

## Customizing

Everything lives in `data/preferences.json`:

- `greens_preferences.replace_always` — add/remove greens substitutions
- `cooldowns` — change how often recipes may repeat
- `seed_sources` — add more recipe websites to start from
- `dietary_rules` / `notes_to_agent` — plain-English rules the agent follows

## Files

```
.github/workflows/weekly-menu.yml   # Friday cron job
.github/workflows/feedback.yml      # processes reject:/favorite: issues
scripts/generate_menu.py            # the agent
scripts/process_feedback.py         # updates preferences from issues
data/preferences.json               # your rules, favorites, rejections
data/history.json                   # every past menu (the memory)
```
