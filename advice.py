"""The thinking behind the FPL Assistant.

Everything here is plain Python with no web page code, so each piece can be
tested on its own. app.py calls these functions and shows the results.
"""

from collections import Counter

from analyse import fixture_score

MAX_PER_CLUB = 3
MAX_FREE_TRANSFERS = 5
SQUAD_SHAPE = {1: 2, 2: 5, 3: 5, 4: 3}      # goalkeepers, defenders, midfielders, forwards
STARTING_SHAPE = {1: 1, 2: 3, 3: 4, 4: 3}   # a 3-4-3 starting eleven
CHIP_LABELS = {"wildcard": "Wildcard", "freehit": "Free Hit", "bboost": "Bench Boost", "3xc": "Triple Captain"}
NO_SPEND_CHIPS = {"wildcard", "freehit"}    # transfers made with these chips are free
TEMPLATE_OWNERSHIP = 25      # never suggest selling a fit player owned by this % of managers or more
RISKY_OWNERSHIP = 10         # warn when selling a fit player owned by this % or more
WILDCARD_MIN_WEEKS_LEFT = 10 # never suggest a Wildcard with fewer gameweeks than this left
CAPTAIN_WEIGHT = {1: 0.5, 2: 0.7, 3: 1.0, 4: 1.0}   # goalkeeper, defender, midfielder, forward
DEFENSIVE = (1, 2)           # goalkeepers and defenders
DIFFERENTIAL_OWNERSHIP = 5   # a player owned by fewer than this % is a "differential"


# ---------- rating players ----------

def strength(player):
    """How good a player is right now: mostly recent form, partly the whole season."""
    form = float(player.get("form") or 0)
    per_game = float(player.get("points_per_game") or 0)
    return 0.75 * form + 0.25 * per_game


def in_form(player):
    """True if the player's recent form is close to, or better than, his season average.
    A big name who has gone cold fails this test, so he is not recommended."""
    form = float(player.get("form") or 0)
    per_game = float(player.get("points_per_game") or 0)
    return form >= 0.8 * per_game


def play_chance(player):
    """Chance the player is available, from 0 to 1."""
    chance = player.get("chance_of_playing_next_round")
    if chance is not None:
        return chance / 100
    return 1.0 if player["status"] == "a" else 0.0


def gw_score(player, team_table, gw):
    """Expected usefulness in one gameweek. Two matches count double, no match counts zero."""
    matches = team_table.get(player["team"], {}).get(gw, [])
    ease = sum(6 - difficulty for _, _, difficulty in matches) / 3
    return strength(player) * ease * play_chance(player)


def outlook(player, team_table, first_gw, last_gw):
    """Expected usefulness over a run of gameweeks."""
    return sum(gw_score(player, team_table, gw) for gw in range(first_gw, last_gw + 1))


# ---------- free transfers ----------

def free_transfers(history, already_made=0):
    """Estimate how many free transfers the manager has left for the next gameweek.

    Rule: you gain 1 each gameweek and can save up to 5. In a week where a
    Wildcard or Free Hit is played the count is frozen: transfers that week use
    none up, and no extra one is gained. `already_made` is the number of
    transfers the manager has already confirmed for the next gameweek.
    FPL only shows the exact number to the logged-in manager, so this is an estimate.
    """
    weeks = history.get("current", [])
    if not weeks:
        return max(1 - already_made, 0)
    chip_weeks = {c["event"] for c in history.get("chips", []) if c["name"] in NO_SPEND_CHIPS}
    available = 1
    for week in weeks[1:]:  # the first week is the starting squad, which is unlimited
        if week["event"] in chip_weeks:
            continue  # frozen: nothing used, nothing gained
        available = max(available - week.get("event_transfers", 0), 0)
        available = min(available + 1, MAX_FREE_TRANSFERS)
    return max(available - already_made, 0)


def apply_pending_transfers(squad_ids, bank, transfers, next_gw):
    """Update the squad and bank with transfers already confirmed for the next gameweek.

    Returns (squad ids, bank, number of transfers already made).
    """
    squad_ids = list(squad_ids)
    made = 0
    for move in sorted(transfers, key=lambda t: t.get("time", "")):
        if move.get("event") != next_gw:
            continue
        made += 1
        if move["element_out"] in squad_ids:
            squad_ids[squad_ids.index(move["element_out"])] = move["element_in"]
            bank += move.get("element_out_cost", 0) - move.get("element_in_cost", 0)
    return squad_ids, bank, made


# ---------- transfers ----------

def ownership(player):
    """Percentage of all FPL managers who own this player."""
    return float(player.get("selected_by_percent") or 0)


def best_swap(squad, all_players, team_table, bank, first_gw, last_gw):
    """Find the single best affordable swap. Returns a dictionary, or None if nothing helps.

    Selling a fit player that lots of managers own is risky: if he scores and you
    do not have him, you fall behind everyone who does. So a fit player owned by
    TEMPLATE_OWNERSHIP percent or more is never sold, and the more owned a player
    is, the bigger the improvement has to be before selling him is suggested.
    """
    owned = {p["id"] for p in squad}
    clubs = Counter(p["team"] for p in squad)
    main_keeper = max((p for p in squad if p["element_type"] == 1), key=strength, default=None)
    best = None
    for out in squad:
        if out["element_type"] == 1 and out is not main_keeper:
            continue  # the backup goalkeeper never plays, so swapping him is a wasted transfer
        fit = play_chance(out) == 1
        if fit and ownership(out) >= TEMPLATE_OWNERSHIP:
            continue
        caution = 1 + ownership(out) / 10 if fit else 1
        out_value = outlook(out, team_table, first_gw, last_gw)
        budget = out["now_cost"] + bank
        for candidate in all_players:
            if candidate["id"] in owned or candidate["element_type"] != out["element_type"]:
                continue
            if candidate["now_cost"] > budget or play_chance(candidate) < 1 or not in_form(candidate):
                continue
            same_club = clubs[candidate["team"]] - (1 if out["team"] == candidate["team"] else 0)
            if same_club >= MAX_PER_CLUB:
                continue
            if candidate["element_type"] in DEFENSIVE and any(
                    p["team"] == candidate["team"] and p["element_type"] in DEFENSIVE and p is not out
                    for p in squad):
                continue  # two defenders from one club both lose their points if that club concedes
            gain = (outlook(candidate, team_table, first_gw, last_gw) - out_value) / caution
            if best is None or gain > best["gain"]:
                best = {"out": out, "in": candidate, "gain": gain,
                        "bank_after": budget - candidate["now_cost"]}
    return best


def swap_notes(move):
    """Plain-English reasons and risks for one suggested transfer."""
    out, new = move["out"], move["in"]
    notes = []
    if play_chance(out) < 1:
        notes.append(("reason", f"{out['web_name']} is flagged: {out.get('news') or 'he may not play'}."))
    else:
        notes.append(("reason", f"{new['web_name']} is in better form ({new['form']} against {out['form']}) "
                                "and has the kinder run of fixtures."))
    if play_chance(out) == 1 and ownership(out) >= RISKY_OWNERSHIP:
        notes.append(("risk", f"{out['web_name']} is owned by {ownership(out):.0f}% of managers. If he scores "
                              "big after you sell him, you lose ground on all of them. Only do this if you "
                              "are happy to take that gamble."))
    if ownership(new) < DIFFERENTIAL_OWNERSHIP:
        notes.append(("risk", f"{new['web_name']} is a differential: only {ownership(new):.1f}% own him. "
                              "Great if it comes off, but he is less proven."))
    return notes


def plan_transfers(squad, all_players, team_table, bank, count, first_gw, last_gw, min_gain=3.0):
    """Plan up to `count` swaps, one after the other, never spending more than the bank allows.

    Regular starters only are considered as targets. Returns (list of swaps, squad afterwards, bank afterwards).
    """
    most_minutes = max((p["minutes"] for p in all_players), default=0)
    regulars = [p for p in all_players if p["minutes"] >= most_minutes * 0.5]
    squad = list(squad)
    moves = []
    for _ in range(count):
        swap = best_swap(squad, regulars, team_table, bank, first_gw, last_gw)
        if swap is None or swap["gain"] < min_gain:
            break
        moves.append(swap)
        squad = [swap["in"] if p["id"] == swap["out"]["id"] else p for p in squad]
        bank = swap["bank_after"]
    return moves, squad, bank


def save_up_targets(squad, all_players, team_table, bank, first_gw, last_gw, how_many=3):
    """Top players the manager cannot afford yet, with how much more money is needed."""
    owned = {p["id"] for p in squad}
    most_minutes = max((p["minutes"] for p in all_players), default=0)
    targets = []
    for candidate in all_players:
        if candidate["id"] in owned or play_chance(candidate) < 1 or candidate["minutes"] < most_minutes * 0.5:
            continue
        if not in_form(candidate):
            continue
        same_position = [p for p in squad if p["element_type"] == candidate["element_type"]]
        dearest = max(p["now_cost"] for p in same_position)
        short_by = candidate["now_cost"] - (dearest + bank)
        if short_by > 0:
            targets.append((outlook(candidate, team_table, first_gw, last_gw), candidate, short_by))
    targets.sort(key=lambda item: item[0], reverse=True)
    best_per_position = []
    for position in SQUAD_SHAPE:  # one goalkeeper, one defender, one midfielder, one forward
        match = next(((p, short) for _, p, short in targets if p["element_type"] == position), None)
        if match:
            best_per_position.append(match)
    return best_per_position


def captain_pick(squad, team_table, gw):
    """Best and second-best captain for a gameweek."""
    ranked = sorted(squad, key=lambda p: captain_score(p, team_table, gw), reverse=True)
    return ranked[0], ranked[1]


def captain_score(player, team_table, gw):
    """Like gw_score, but leaning towards attackers: a captain needs goals and assists,
    and a defender's points disappear with one goal conceded."""
    return gw_score(player, team_table, gw) * CAPTAIN_WEIGHT[player["element_type"]]


# ---------- picking a starting eleven ----------

def pick_lineup(squad, team_table, gw):
    """Choose the best legal starting eleven for a gameweek.

    FPL rules: 1 goalkeeper, at least 3 defenders, at least 2 midfielders, at least 1 forward.
    Returns (starters, bench). The bench is in the order the substitutes should come on.
    """
    def score(player):
        return gw_score(player, team_table, gw)

    by_position = {pos: sorted((p for p in squad if p["element_type"] == pos), key=score, reverse=True)
                   for pos in SQUAD_SHAPE}
    starters = by_position[1][:1] + by_position[2][:3] + by_position[3][:2] + by_position[4][:1]
    spare = sorted(by_position[2][3:] + by_position[3][2:] + by_position[4][1:], key=score, reverse=True)
    starters += spare[:11 - len(starters)]
    starters.sort(key=lambda p: (p["element_type"], -score(p)))
    bench = by_position[1][1:] + spare[4:]
    return starters, bench


def keeper_rotation(keepers, team_table, first_gw, last_gw):
    """For two goalkeepers, say which one to start in each gameweek: [(gameweek, keeper), ...]."""
    return [(gw, max(keepers, key=lambda k: gw_score(k, team_table, gw)))
            for gw in range(first_gw, last_gw + 1)]


# ---------- chips ----------

def chip_windows(bootstrap):
    """When each chip can be played: {chip name: [(first gameweek, last gameweek), ...]}.

    You get two of each chip, one for each half of the season. The exact gameweeks
    come from FPL when it provides them; otherwise the usual halves are assumed.
    """
    windows = {name: [] for name in CHIP_LABELS}
    for rule in bootstrap.get("chips") or []:
        if rule.get("name") in windows and rule.get("start_event") and rule.get("stop_event"):
            windows[rule["name"]].append((rule["start_event"], rule["stop_event"]))
    for name, found in windows.items():
        found.sort()
        if not found or (len(found) == 1 and found[0][1] - found[0][0] > 25):
            windows[name] = [(1, 19), (20, 38)]
    return windows


def chip_status(bootstrap, history, next_gw):
    """For each chip, describe each of its windows.

    Returns {chip name: [{"start", "stop", "played" (gameweek or None), "open" (can still be played)}]}.
    """
    used = history.get("chips", [])
    status = {}
    for name, windows in chip_windows(bootstrap).items():
        status[name] = []
        for start, stop in windows:
            played = next((u["event"] for u in used if u["name"] == name and start <= u["event"] <= stop), None)
            status[name].append({"start": start, "stop": stop, "played": played,
                                 "open": played is None and stop >= next_gw})
    return status


def chip_advice(name, squad, team_table, first_gw, last_gw, wildcard_window=8):
    """Suggest when to play one chip. Returns a dictionary describing the best week."""
    weeks = list(range(first_gw, last_gw + 1))
    if not weeks:
        return None

    def squad_total(gw):
        return sum(gw_score(p, team_table, gw) for p in squad)

    def best_eleven(gw):
        return sum(sorted((gw_score(p, team_table, gw) for p in squad), reverse=True)[:11])

    def without_match(gw):
        return [p["web_name"] for p in squad if not team_table.get(p["team"], {}).get(gw)]

    def playing_twice(gw):
        return [p["web_name"] for p in squad if len(team_table.get(p["team"], {}).get(gw, [])) > 1]

    if name == "3xc":
        # Best week and player for each outfield position, then one favourite overall.
        options = {}
        for position in (2, 3, 4):
            group = [p for p in squad if p["element_type"] == position]
            if group:
                best_gw, best_player = max(((g, p) for g in weeks for p in group),
                                           key=lambda pair: gw_score(pair[1], team_table, pair[0]))
                options[position] = (best_gw, best_player)
        gw, player = max(((g, p) for g in weeks for p in squad),
                         key=lambda pair: captain_score(pair[1], team_table, pair[0]))
        return {"gw": gw, "player": player, "doubles": playing_twice(gw), "options": options}
    if name == "bboost":
        gw = max(weeks, key=squad_total)
        return {"gw": gw, "doubles": playing_twice(gw), "blanks": without_match(gw)}
    if name == "freehit":
        gw = min(weeks, key=best_eleven)
        return {"gw": gw, "blanks": without_match(gw)}
    if name == "wildcard":
        # A Wildcard squad stays with you, so the earlier it is played the more weeks it pays off.
        # Look for the worst long run for the current squad, and lean towards the earlier option.
        starts = [g for g in weeks if g <= 38 - WILDCARD_MIN_WEEKS_LEFT] or weeks[:1]
        normal = sum(squad_total(w) for w in range(weeks[0], 39)) / (39 - weeks[0])

        def benefit(g):
            run = range(g, min(g + wildcard_window, 39))
            weakness = sum(normal - squad_total(w) for w in run)
            return weakness + 0.05 * normal * (38 - g)  # bonus for every gameweek still to come

        gw = max(starts, key=benefit)
        return {"gw": gw, "until": min(gw + wildcard_window - 1, 38)}
    return None


# ---------- Free Hit builder ----------

def build_free_hit(all_players, team_table, gw, budget):
    """Build a squad for a single gameweek."""
    return build_squad(all_players, team_table, gw, gw, budget)


def build_squad(all_players, team_table, first_gw, last_gw, budget, bench_weight=0.0):
    """Build a 15-player squad for a run of gameweeks within the budget (in tenths, like the API).

    Method: start with the cheapest legal squad, then keep making the upgrade that adds the
    most for the money, until no upgrade fits.

    bench_weight says how much the substitutes matter:
      0.0 for a Free Hit   - one week only, so all the money goes on the starting eleven
      0.6 for a Wildcard   - the squad lasts for months, so the bench must be able to step in
    Returns (starters, bench, cost) or None if even the cheapest squad is too dear.
    """
    most_minutes = max((p["minutes"] for p in all_players), default=0)
    pool = [p for p in all_players if play_chance(p) == 1 and p["minutes"] >= most_minutes * 0.4]
    score = {p["id"]: outlook(p, team_table, first_gw, last_gw) for p in pool}

    squad, clubs = [], Counter()
    for position, needed in SQUAD_SHAPE.items():
        cheapest = sorted((p for p in pool if p["element_type"] == position),
                          key=lambda p: (p["now_cost"], -score[p["id"]]))
        added = 0
        for p in cheapest:
            if added == needed:
                break
            if clubs[p["team"]] < MAX_PER_CLUB:
                squad.append(p)
                clubs[p["team"]] += 1
                added += 1
        if added < needed:
            return None
    spent = sum(p["now_cost"] for p in squad)
    if spent > budget:
        return None

    # How much each of the 15 places matters. The first players of each position are the starters.
    weight = {}
    for position, count in STARTING_SHAPE.items():
        indexes = [i for i, p in enumerate(squad) if p["element_type"] == position]
        for order, index in enumerate(indexes):
            if order < count:
                weight[index] = 1.0
            elif position == 1:
                weight[index] = bench_weight * 0.5  # a second goalkeeper only helps by rotating
            else:
                weight[index] = bench_weight
    slots = [i for i in weight if weight[i] > 0]

    while True:
        owned = {p["id"] for p in squad}
        best = None
        for slot in slots:
            current = squad[slot]
            for candidate in pool:
                if candidate["id"] in owned or candidate["element_type"] != current["element_type"]:
                    continue
                gain = (score[candidate["id"]] - score[current["id"]]) * weight[slot]
                extra = candidate["now_cost"] - current["now_cost"]
                if gain <= 0 or spent + extra > budget:
                    continue
                same_club = clubs[candidate["team"]] - (1 if current["team"] == candidate["team"] else 0)
                if same_club >= MAX_PER_CLUB:
                    continue
                value = gain / (max(extra, 0) + 1)
                if best is None or value > best[0]:
                    best = (value, slot, candidate, extra)
        if best is None:
            break
        _, slot, candidate, extra = best
        clubs[squad[slot]["team"]] -= 1
        clubs[candidate["team"]] += 1
        squad[slot] = candidate
        spent += extra

    starters, bench = pick_lineup(squad, team_table, first_gw)
    return starters, bench, spent
