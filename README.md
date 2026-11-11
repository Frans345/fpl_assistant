# FPL Assistant

A friendly second opinion for Fantasy Premier League managers. Enter any FPL team ID and it gives advice for that squad before each deadline.

**Live app:** https://fpl-assistant-goat.streamlit.app

## What it does

- **This week** - the best starting eleven drawn on a pitch, captain and vice-captain, plus injury and suspension warnings
- **My squad** - every player's next five fixtures, colour-coded by difficulty
- **Transfers** - who to sell and who to buy, within the money in the bank and the free transfers available. It avoids selling highly owned players, buying out-of-form players, and doubling up on one club's defence
- **Chip planner** - when to play the Triple Captain, Bench Boost, Free Hit and Wildcard, and a suggested squad for the Free Hit and Wildcard

## How it works

1. **Ingest** - player, team, fixture and manager data is pulled from the public FPL API (`fetch_data.py`, `app.py`)
2. **Analyse** - fixtures, availability and yellow-card risk are worked out per player (`analyse.py`)
3. **Advise** - players are scored on form and fixture difficulty, then rule-based logic plans transfers, line-ups and chips (`advice.py`)
4. **Present** - a Streamlit web app shows the advice in plain English (`app.py`)

Planned next: an LLM step that reads football news and adds context the numbers cannot see, and a scheduled GitHub Actions run.

## Built with

Python, Streamlit, the FPL API, HTML and CSS

## Running it on your own computer

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

## Notes

- The FPL API is free and needs no key, but it is unofficial and undocumented, so it can change without notice.
- Advice is based on simple scoring rules. It is an estimate, not a prediction.
- This is a student project and is not affiliated with the Premier League.
