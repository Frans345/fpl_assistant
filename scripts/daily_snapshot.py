"""Save a daily snapshot of FPL player prices, ownership and availability."""

import csv
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
COLUMNS = [
    "id", "name", "team", "position", "price", "selected_by_percent",
    "status", "chance_of_playing_next_round", "news", "total_points", "form",
]


def main():
    request = urllib.request.Request(
        URL, headers={"User-Agent": "Mozilla/5.0 (fpl-assistant daily snapshot)"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)

    teams = {team["id"]: team["short_name"] for team in data["teams"]}
    positions = {pos["id"]: pos["singular_name_short"] for pos in data["element_types"]}

    today = datetime.now(timezone.utc).date().isoformat()
    output = Path("snapshots") / f"{today}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        for player in sorted(data["elements"], key=lambda p: p["id"]):
            writer.writerow([
                player["id"],
                player["web_name"],
                teams.get(player["team"], ""),
                positions.get(player["element_type"], ""),
                player["now_cost"] / 10,
                player.get("selected_by_percent", ""),
                player.get("status", ""),
                player.get("chance_of_playing_next_round", ""),
                player.get("news", ""),
                player.get("total_points", ""),
                player.get("form", ""),
            ])

    print(f"Saved {len(data['elements'])} players to {output}")


if __name__ == "__main__":
    main()
