"""Step 1 of the FPL pipeline: download the raw data and save it.

Run it with:  python fetch_data.py
It saves two files in data/raw/ and prints a short summary.
"""

import json
from pathlib import Path

import requests

API = "https://fantasy.premierleague.com/api/"
HEADERS = {"User-Agent": "fpl-assistant/1.0 (student project)"}
RAW_DIR = Path("data/raw")


def fetch(path):
    """Download one endpoint and return it as Python data."""
    response = requests.get(API + path, headers=HEADERS, timeout=30)
    response.raise_for_status()  # stop with a clear error if the request failed
    return response.json()


def save(data, filename):
    """Save data as a JSON file in data/raw/."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = RAW_DIR / filename
    target.write_text(json.dumps(data), encoding="utf-8")
    return target


def summarise(bootstrap, fixtures):
    """Build a few lines of text that prove the data looks right."""
    teams = {team["id"]: team["short_name"] for team in bootstrap["teams"]}
    players = bootstrap["elements"]

    next_gw = next((gw for gw in bootstrap["events"] if gw.get("is_next")), None)
    lines = [f"Players: {len(players)}  Teams: {len(teams)}  Fixtures: {len(fixtures)}"]
    if next_gw:
        lines.append(f"Next deadline: {next_gw['name']} at {next_gw['deadline_time']}")

    lines.append("Top 5 players by form:")
    in_form = sorted(players, key=lambda p: float(p["form"] or 0), reverse=True)[:5]
    for p in in_form:
        price = p["now_cost"] / 10  # the API stores 7.5m as 75
        lines.append(f"  {p['web_name']} ({teams[p['team']]})  form {p['form']}  £{price}m")
    return lines


def main():
    bootstrap = fetch("bootstrap-static/")  # players, teams and gameweeks
    fixtures = fetch("fixtures/")           # every match of the season

    print("Saved", save(bootstrap, "bootstrap.json"))
    print("Saved", save(fixtures, "fixtures.json"))
    print("\n".join(summarise(bootstrap, fixtures)))


if __name__ == "__main__":
    main()
