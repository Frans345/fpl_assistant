"""Step 2 of the FPL pipeline: analyse one manager's squad.

Run it with:  python analyse.py 1234567      (use any FPL team ID)
Run fetch_data.py first so the files in data/raw/ are up to date.

It prints four things:
  1. the squad with each player's next fixtures
  2. injury and availability warnings
  3. players close to a yellow card suspension
  4. transfer targets the manager does not own yet
"""

import json
import sys
from pathlib import Path

import requests

API = "https://fantasy.premierleague.com/api/"
HEADERS = {"User-Agent": "fpl-assistant/1.0 (student project)"}
RAW_DIR = Path("data/raw")

LOOK_AHEAD = 5  # how many gameweeks of fixtures to look at
POSITIONS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

# Premier League rule: 5 yellows by gameweek 19 = 1 match ban,
# 10 yellows by gameweek 32 = 2 match ban.
YELLOW_RULES = [(5, 19), (10, 32)]


# ---------- loading data ----------

def load(filename):
    """Read a file that fetch_data.py saved."""
    path = RAW_DIR / filename
    if not path.exists():
        sys.exit(f"Cannot find {path}. Run this first:  python fetch_data.py")
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(path):
    """Download one endpoint and return it as Python data."""
    response = requests.get(API + path, headers=HEADERS, timeout=30)
    if response.status_code == 404:
        sys.exit("FPL could not find that team. Check the team ID and try again.")
    response.raise_for_status()
    return response.json()


def gameweeks(bootstrap):
    """Return (last gameweek that has started, next gameweek to be played)."""
    events = bootstrap["events"]
    current = next((gw["id"] for gw in events if gw.get("is_current")), None)
    upcoming = next((gw["id"] for gw in events if gw.get("is_next")), None)
    return current, upcoming


# ---------- fixtures ----------

def fixtures_by_team(fixtures, first_gw, last_gw):
    """Build {team id: {gameweek: [(opponent id, "H" or "A", difficulty)]}}."""
    table = {}
    for match in fixtures:
        gw = match.get("event")
        if gw is None or gw < first_gw or gw > last_gw:
            continue
        home, away = match["team_h"], match["team_a"]
        table.setdefault(home, {}).setdefault(gw, []).append((away, "H", match["team_h_difficulty"]))
        table.setdefault(away, {}).setdefault(gw, []).append((home, "A", match["team_a_difficulty"]))
    return table


def fixture_text(team_fixtures, team_names, first_gw, last_gw):
    """Turn a team's fixtures into text like 'ARS(H)2  -  MCI(A)5+BOU(H)2'."""
    parts = []
    for gw in range(first_gw, last_gw + 1):
        matches = team_fixtures.get(gw, [])
        if not matches:
            parts.append("-")  # blank gameweek: no match
        else:
            parts.append("+".join(f"{team_names[opp]}({venue}){diff}" for opp, venue, diff in matches))
    return "  ".join(parts)


def fixture_score(team_fixtures):
    """Higher = easier run. An easy match (difficulty 2) is worth 4, a hard one (5) is worth 1.
    A double gameweek counts both matches and a blank counts nothing."""
    return sum(6 - diff for matches in team_fixtures.values() for _, _, diff in matches)


# ---------- checks on a player ----------

def availability_warning(player):
    """Return a warning if the player might not play, otherwise None."""
    chance = player.get("chance_of_playing_next_round")
    if player["status"] == "a" and chance in (None, 100):
        return None
    chance_text = "unknown" if chance is None else f"{chance}%"
    news = player.get("news") or "No details given"
    return f"{player['web_name']}: {news} (chance of playing: {chance_text})"


def yellow_warning(player, next_gw):
    """Return a warning if one more yellow card means a ban, otherwise None."""
    yellows = player.get("yellow_cards", 0)
    for limit, deadline_gw in YELLOW_RULES:
        if yellows == limit - 1 and next_gw <= deadline_gw:
            return (f"{player['web_name']}: {yellows} yellow cards. One more before the end of "
                    f"gameweek {deadline_gw} means a ban.")
    return None


def is_fit(player):
    return player["status"] == "a" and player.get("chance_of_playing_next_round") in (None, 100)


# ---------- transfer targets ----------

def transfer_targets(players, owned_ids, team_table, per_position=3):
    """Rank players the manager does not own by form and how easy their fixtures are."""
    most_minutes = max((p["minutes"] for p in players), default=0)
    results = {name: [] for name in POSITIONS.values()}
    for p in players:
        if p["id"] in owned_ids or not is_fit(p):
            continue
        if p["minutes"] < most_minutes * 0.5:  # skip players who rarely play
            continue
        form = float(p["form"] or 0)
        score = form * fixture_score(team_table.get(p["team"], {})) / (LOOK_AHEAD * 3)
        results[POSITIONS[p["element_type"]]].append((score, p))
    for name in results:
        results[name] = sorted(results[name], key=lambda item: item[0], reverse=True)[:per_position]
    return results


# ---------- the report ----------

def build_report(team_id, bootstrap, fixtures, entry, picks):
    current_gw, next_gw = gameweeks(bootstrap)
    if next_gw is None:
        return ["The season has finished, so there are no fixtures to analyse."]
    last_gw = min(next_gw + LOOK_AHEAD - 1, 38)

    team_names = {team["id"]: team["short_name"] for team in bootstrap["teams"]}
    players = {p["id"]: p for p in bootstrap["elements"]}
    team_table = fixtures_by_team(fixtures, next_gw, last_gw)

    squad = [players[pick["element"]] for pick in picks["picks"]]
    owned_ids = {p["id"] for p in squad}

    manager = f"{entry.get('player_first_name', '')} {entry.get('player_last_name', '')}".strip()
    lines = [
        f"{entry.get('name', 'Team')} ({manager}), team ID {team_id}",
        f"Total points: {entry.get('summary_overall_points')}   Overall rank: {entry.get('summary_overall_rank')}",
        f"Squad as of gameweek {current_gw}. Fixtures shown: gameweeks {next_gw} to {last_gw}.",
        "",
        "SQUAD AND FIXTURES   (H = home, A = away, number = difficulty 1 easy to 5 hard, - = no match)",
    ]
    for p in sorted(squad, key=lambda p: p["element_type"]):
        run = fixture_text(team_table.get(p["team"], {}), team_names, next_gw, last_gw)
        lines.append(f"  {POSITIONS[p['element_type']]}  {p['web_name']:<18} form {p['form']:<5} {run}")

    lines += ["", "AVAILABILITY WARNINGS"]
    warnings = [w for w in (availability_warning(p) for p in squad) if w]
    lines += [f"  {w}" for w in warnings] or ["  None. Everyone in the squad is marked as available."]

    lines += ["", "SUSPENSION RISK"]
    risks = [w for w in (yellow_warning(p, next_gw) for p in squad) if w]
    lines += [f"  {w}" for w in risks] or ["  None. Nobody is one yellow card away from a ban."]

    lines += ["", "DOUBLE AND BLANK GAMEWEEKS FOR YOUR SQUAD"]
    special = []
    for gw in range(next_gw, last_gw + 1):
        doubles = [p["web_name"] for p in squad if len(team_table.get(p["team"], {}).get(gw, [])) > 1]
        blanks = [p["web_name"] for p in squad if not team_table.get(p["team"], {}).get(gw)]
        if doubles:
            special.append(f"  Gameweek {gw}: {len(doubles)} players play twice ({', '.join(doubles)})")
        if blanks:
            special.append(f"  Gameweek {gw}: {len(blanks)} players have no match ({', '.join(blanks)})")
    lines += special or ["  None in the next few gameweeks."]

    lines += ["", "TRANSFER TARGETS YOU DO NOT OWN   (ranked on form and upcoming fixtures)"]
    targets = transfer_targets(list(players.values()), owned_ids, team_table)
    for position, ranked in targets.items():
        for score, p in ranked:
            run = fixture_text(team_table.get(p["team"], {}), team_names, next_gw, last_gw)
            price = p["now_cost"] / 10
            lines.append(f"  {position}  {p['web_name']:<18} {price:>4.1f}m  form {p['form']:<5} {run}")
    return lines


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit("Type the team ID after the script name, like this:  python analyse.py 1234567")
    team_id = sys.argv[1]

    bootstrap = load("bootstrap.json")
    fixtures = load("fixtures.json")
    current_gw, _ = gameweeks(bootstrap)
    if current_gw is None:
        sys.exit("The season has not started yet, so there is no squad to analyse.")

    entry = fetch(f"entry/{team_id}/")
    picks = fetch(f"entry/{team_id}/event/{current_gw}/picks/")

    print("\n".join(build_report(team_id, bootstrap, fixtures, entry, picks)))


if __name__ == "__main__":
    main()
