"""FPL Assistant: the web page.

Run it with:  python -m streamlit run app.py
It opens in your browser. Type any FPL team ID to get advice for that team.
"""

from datetime import datetime
from html import escape
from pathlib import Path

import requests
import streamlit as st

import advice
from analyse import (
    POSITIONS,
    availability_warning,
    fixtures_by_team,
    gameweeks,
    yellow_warning,
)

API = "https://fantasy.premierleague.com/api/"
HEADERS = {"User-Agent": "fpl-assistant/1.0 (student project)"}
ASSETS = Path(__file__).parent / "assets"
LOOK_AHEAD = 5
PAGES = ["This week", "My squad", "Transfers", "Chip planner"]

DIFFICULTY_COLOURS = {
    1: "background-color: #1f7a3d; color: white",
    2: "background-color: #37b25f; color: black",
    3: "background-color: #d9d9d9; color: black",
    4: "background-color: #f2617a; color: black",
    5: "background-color: #8a1538; color: white",
    0: "background-color: #555555; color: white",  # no match
}

STYLE = """
<style>
/* Page width and breathing room */
.block-container { max-width: 980px; padding-top: 2.5rem; padding-bottom: 4rem; }
h3 { margin-top: 1.6rem; margin-bottom: 0.4rem; }

/* Banner */
.hero { background: linear-gradient(120deg, #00ff87 0%, #04f5ff 45%, #963cff 100%);
        border-radius: 18px; padding: 1.4rem 1.6rem; color: #1d0421; }
.hero h1 { margin: 0; padding: 0; font-size: 2rem; color: #1d0421; }
.hero p { margin: 0.25rem 0 0 0; font-size: 1.05rem; color: #1d0421; }

/* Number cards */
.cards { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1rem 0 1.4rem 0; }
.card { flex: 1 1 150px; background: #2b0630; border-radius: 14px; padding: 0.85rem 1rem; }
.card .label { font-size: 0.8rem; opacity: 0.7; }
.card .value { font-size: 1.3rem; font-weight: 700; margin-top: 0.15rem; }

/* Message boxes: advice (green), warning (yellow), problem (red) */
.note { background: #2b0630; border-left: 4px solid #00ff87; border-radius: 12px;
        padding: 0.9rem 1.1rem; margin: 0 0 0.9rem 0; line-height: 1.55; }
.note b { color: #00ff87; }
.note.warn { border-left-color: #ffd60a; }
.note.warn b { color: #ffd60a; }
.note.danger { border-left-color: #ff4d6d; }
.note.danger b { color: #ff6b8a; }

/* Transfer cards */
.swap { background: #2b0630; border-radius: 14px; padding: 1.1rem 1.2rem; margin-bottom: 1rem; line-height: 1.75; }
.swap .title { font-size: 0.8rem; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.06em; }
.swap .out { color: #ff6b8a; font-weight: 700; display: inline-block; width: 2.6rem; }
.swap .in { color: #00ff87; font-weight: 700; display: inline-block; width: 2.6rem; }
.swap .why { margin-top: 0.6rem; padding-top: 0.6rem; border-top: 1px solid rgba(255,255,255,0.12);
             line-height: 1.5; opacity: 0.9; }
.swap .risk { color: #ffd60a; margin-top: 0.3rem; }

/* The menu: a row of big buttons, like a website's navigation bar */
div[role="radiogroup"] { background: #2b0630; border-radius: 14px; padding: 0.4rem; gap: 0.3rem; }
div[role="radiogroup"] label { margin: 0; padding: 0.75rem 1.4rem; border-radius: 10px; cursor: pointer;
                               justify-content: center;
                               transition: background-color 150ms ease, color 150ms ease; }
div[role="radiogroup"] label > div:first-child { display: none; }
div[role="radiogroup"] label p { font-size: 1.1rem; font-weight: 700; }
div[role="radiogroup"] label:has(input:checked) { background: #00ff87; }
div[role="radiogroup"] label:has(input:checked) p { color: #1d0421; }

/* Fold-out bars (the chips, and the extra sections on the Transfers page) */
div[data-testid="stExpander"] details { background: #2b0630; border: none; border-radius: 14px; }
div[data-testid="stExpander"] summary { padding: 1rem 1.2rem; border-radius: 14px;
                                        transition: background-color 150ms ease; }
div[data-testid="stExpander"] summary p { font-size: 1.1rem; font-weight: 700; }
div[data-testid="stExpander"] { margin-bottom: 0.7rem; }

@media (hover: hover) and (pointer: fine) {
  div[role="radiogroup"] label:not(:has(input:checked)):hover { background: rgba(255,255,255,0.1); }
  div[data-testid="stExpander"] summary:hover { background: rgba(255,255,255,0.06); }
}
@media (prefers-reduced-motion: reduce) {
  div[role="radiogroup"] label, div[data-testid="stExpander"] summary { transition: none; }
}

/* The welcome form: no "Press Enter" hint, since phones have no Enter key to speak of */
div[data-testid="InputInstructions"] { display: none; }

/* The pitch on the This week page */
.pitch { background: repeating-linear-gradient(180deg, #0a8f4c 0 70px, #0b9a52 70px 140px);
         border-radius: 16px; padding: 0.8rem 0.4rem 1rem 0.4rem; }
.line { display: flex; justify-content: center; gap: 0.5rem; margin: 0.9rem 0; }
.pl { flex: 0 1 98px; min-width: 0; text-align: center; }
.pl .shirt { width: 46px; height: 46px; margin: 0 auto; border-radius: 50%; background: #37003c; color: white;
             border: 2px solid white; display: flex; align-items: center; justify-content: center;
             font-size: 0.7rem; font-weight: 700; position: relative; }
.pl.doubt .shirt { border-color: #ffd60a; }
.pl .badge { position: absolute; top: -7px; right: -9px; width: 21px; height: 21px; border-radius: 50%;
             background: #00ff87; color: #1d0421; font-size: 0.72rem; line-height: 21px; }
.pl .nm { background: #1d0421; color: white; font-size: 0.8rem; font-weight: 700; border-radius: 6px 6px 0 0;
          padding: 2px 4px; margin-top: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pl .fx { background: white; color: #1d0421; font-size: 0.72rem; border-radius: 0 0 6px 6px; padding: 1px 4px;
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bench { background: #2b0630; border-radius: 16px; padding: 0.2rem 0.4rem 0.4rem 0.4rem; margin: 0.7rem 0 1.2rem 0; }
.bench .label { font-size: 0.8rem; opacity: 0.7; text-align: center; margin-top: 0.6rem; }

/* Phones */
@media (max-width: 640px) {
  .block-container { padding: 1.2rem 0.9rem 3rem 0.9rem; }
  .hero { padding: 1.1rem 1.2rem; }
  .hero h1 { font-size: 1.5rem; }
  .card { flex: 1 1 42%; }
  .card .value { font-size: 1.1rem; }
  div[role="radiogroup"] { display: grid; grid-template-columns: 1fr 1fr; }
  div[role="radiogroup"] label { padding: 0.7rem 0.5rem; }
  div[role="radiogroup"] label p { font-size: 1rem; }
  div[data-testid="stExpander"] summary { padding: 0.9rem 1rem; }
  .line { gap: 0.25rem; }
  .pl .shirt { width: 38px; height: 38px; font-size: 0.62rem; }
  .pl .nm { font-size: 0.68rem; }
  .pl .fx { font-size: 0.62rem; }
}
</style>
"""


# ---------- getting data (kept for 30 minutes so the page stays fast) ----------

@st.cache_data(ttl=1800, show_spinner=False)
def fetch(path):
    response = requests.get(API + path, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def back_to_start(message=None):
    """Forget the team and show the welcome screen again."""
    if "team" in st.query_params:
        del st.query_params["team"]
    for key in [k for k in st.session_state if k == "page" or k.startswith("w_")]:
        st.session_state.pop(key, None)
    st.session_state["problem"] = message
    st.rerun()


def load_team(team_id, current_gw):
    """Return (entry, picks, history, transfers), or go back to the start with a friendly message."""
    try:
        entry = fetch(f"entry/{team_id}/")
        picks = fetch(f"entry/{team_id}/event/{current_gw}/picks/")
        history = fetch(f"entry/{team_id}/history/")
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code == 404:
            back_to_start("I couldn't find a team with that ID. Could you check the number and try again?")
        back_to_start("FPL isn't answering right now. It may be updating scores, so try again in a few minutes.")
    except requests.RequestException:
        back_to_start("I couldn't reach FPL. Check your internet connection and try again.")
    try:
        transfers = fetch(f"entry/{team_id}/transfers/")
    except requests.RequestException:
        transfers = []  # not essential, so carry on without it
    return entry, picks, history, transfers


# ---------- small helpers for showing things ----------

def money(tenths):
    """The API stores £7.5m as 75."""
    return f"£{tenths / 10:.1f}m"


def local_time(iso_text):
    """Show a deadline in the visitor's own time zone when the browser tells us what it is."""
    moment = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
    try:
        from zoneinfo import ZoneInfo
        zone = st.context.timezone
        if zone:
            return moment.astimezone(ZoneInfo(zone)).strftime("%a %d %b, %H:%M"), "local time"
    except Exception:
        pass  # older Streamlit or unknown time zone: fall back to UTC
    return moment.strftime("%a %d %b, %H:%M"), "UTC"


def note(text, kind=""):
    """A message box. kind is "" for advice, "warn" for a warning, "danger" for a problem."""
    st.markdown(f'<div class="note {kind}">{text}</div>', unsafe_allow_html=True)


def name(player):
    return f"<b>{escape(player['web_name'])}</b>"


def fixture_cells(team_fixtures, team_names, gw_range):
    """Return (text per gameweek, difficulty per gameweek) for one team."""
    texts, difficulties = [], []
    for gw in gw_range:
        matches = team_fixtures.get(gw, [])
        if not matches:
            texts.append("No match")
            difficulties.append(0)
        else:
            texts.append(" + ".join(f"{team_names[opp]} ({venue})" for opp, venue, _ in matches))
            difficulties.append(round(sum(diff for _, _, diff in matches) / len(matches)))
    return texts, difficulties


def player_table(player_list, team_table, team_names, gw_range):
    """Build a colour-coded table of players as HTML and return it as text."""
    cell = "padding: 9px 10px; border-bottom: 1px solid rgba(255,255,255,0.15); white-space: nowrap"
    headings = ["Pos", "Player", "Team", "Price", "Form", "Owned by"] + [f"GW{gw}" for gw in gw_range]
    html = '<div style="overflow-x: auto"><table style="border-collapse: collapse; width: 100%"><tr>'
    html += "".join(f'<th style="{cell}; text-align: left">{h}</th>' for h in headings) + "</tr>"
    for p in player_list:
        texts, difficulties = fixture_cells(team_table.get(p["team"], {}), team_names, gw_range)
        values = [POSITIONS[p["element_type"]], name(p), team_names[p["team"]], money(p["now_cost"]),
                  f"{float(p['form'] or 0):.1f}", f"{advice.ownership(p):.0f}%"]
        html += "<tr>" + "".join(f'<td style="{cell}">{v}</td>' for v in values)
        for text, difficulty in zip(texts, difficulties):
            html += f'<td style="{cell}; {DIFFICULTY_COLOURS[difficulty]}; text-align: center">{escape(text)}</td>'
        html += "</tr>"
    return html + "</table></div>"


def next_match(player, team_table, team_names, gw):
    texts, _ = fixture_cells(team_table.get(player["team"], {}), team_names, [gw])
    return texts[0]


def show_swaps(moves, team_table, team_names, gw):
    for number, move in enumerate(moves, start=1):
        out, new = move["out"], move["in"]
        reasons = "".join(
            f'<div class="{"risk" if kind == "risk" else ""}">{"Risk: " if kind == "risk" else "Why: "}{escape(text)}</div>'
            for kind, text in advice.swap_notes(move))
        st.markdown(
            f'<div class="swap"><div class="title">Transfer {number}</div>'
            f'<span class="out">OUT</span> {name(out)} · {team_names[out["team"]]} · {money(out["now_cost"])} · '
            f'owned by {advice.ownership(out):.0f}%<br>'
            f'<span class="in">IN</span> {name(new)} · {team_names[new["team"]]} · {money(new["now_cost"])} · '
            f'next: {escape(next_match(new, team_table, team_names, gw))}<br>'
            f'Money left in the bank afterwards: <b>{money(move["bank_after"])}</b>'
            f'<div class="why">{reasons}</div></div>',
            unsafe_allow_html=True,
        )


def pitch(starters, bench, captain, vice, team_table, team_names, gw):
    """Draw the starting eleven on a pitch, with the bench underneath, as HTML."""
    def player_card(p):
        badge = "C" if p is captain else "V" if p is vice else ""
        badge_html = f'<span class="badge">{badge}</span>' if badge else ""
        doubt = " doubt" if advice.play_chance(p) < 1 else ""
        return (f'<div class="pl{doubt}"><div class="shirt">{team_names[p["team"]]}{badge_html}</div>'
                f'<div class="nm">{escape(p["web_name"])}</div>'
                f'<div class="fx">{escape(next_match(p, team_table, team_names, gw))}</div></div>')

    html = '<div class="pitch">'
    for position in (1, 2, 3, 4):
        row = [p for p in starters if p["element_type"] == position]
        html += '<div class="line">' + "".join(player_card(p) for p in row) + "</div>"
    html += '</div><div class="bench"><div class="label">Bench, in the order I would bring them on</div>'
    html += '<div class="line">' + "".join(player_card(p) for p in bench) + "</div></div>"
    return html


# ---------- the welcome screen (shown until a team is loaded) ----------

def welcome_screen():
    st.markdown('<div class="hero"><h1>FPL Assistant</h1>'
                "<p>Your friendly second opinion before every deadline.</p></div>", unsafe_allow_html=True)
    st.write("")
    problem = st.session_state.pop("problem", None)
    if problem:
        note(escape(problem), "danger")

    with st.form("team_form"):
        typed = st.text_input("Your FPL team ID", placeholder="For example 1234567")
        submitted = st.form_submit_button("Continue", type="primary")
    if submitted:
        typed = typed.strip()
        if typed.isdigit():
            st.query_params["team"] = typed
            st.rerun()
        note("A team ID is numbers only, for example 1234567.", "danger")

    with st.expander("Where do I find my team ID?", expanded=True):
        st.markdown("The FPL phone app doesn't show your ID, so this takes one quick visit to the website. "
                    "You only ever need to do it once.")
        st.markdown("**1.** Open **fantasy.premierleague.com** in your browser and log in.\n\n"
                    "**2.** Tap **Pick Team**, then tap **Gameweek History**.")
        if (ASSETS / "find_id_1.png").exists():
            st.image(str(ASSETS / "find_id_1.png"), width=420)
        st.markdown("**3.** Look at the address bar at the top. Your ID is the number after `/entry/`.")
        if (ASSETS / "find_id_2.png").exists():
            st.image(str(ASSETS / "find_id_2.png"), width=620)
        st.markdown("**4.** Type that number in the box above and press **Continue**. "
                    "Bookmark the page afterwards and it will open straight on your team next time.")


# ---------- start of the page ----------

st.set_page_config(page_title="FPL Assistant", layout="wide")
st.markdown(STYLE, unsafe_allow_html=True)

# Keep every choice made on one page (names starting w_) while the visitor looks at another page.
for key in [k for k in st.session_state if k.startswith("w_")]:
    st.session_state[key] = st.session_state[key]

team_id = st.query_params.get("team", "")
if not team_id.isdigit():
    welcome_screen()
    st.stop()

with st.spinner("Having a look at your team..."):
    try:
        bootstrap = fetch("bootstrap-static/")
        fixtures = fetch("fixtures/")
    except requests.RequestException:
        back_to_start("FPL isn't answering right now. It may be updating scores, so try again in a few minutes.")

    current_gw, next_gw = gameweeks(bootstrap)
    if current_gw is None:
        st.info("The season hasn't started yet, so there is no squad to look at. See you at Gameweek 1!")
        st.stop()
    if next_gw is None:
        st.info("The season has finished. Enjoy the break and come back when the new one starts.")
        st.stop()
    entry, picks, history, transfers = load_team(team_id, current_gw)

# Everything the page needs, worked out once
last_gw = min(next_gw + LOOK_AHEAD - 1, 38)
gw_range = range(next_gw, last_gw + 1)
team_names = {team["id"]: team["short_name"] for team in bootstrap["teams"]}
players = {p["id"]: p for p in bootstrap["elements"]}
all_players = list(players.values())
team_table = fixtures_by_team(fixtures, next_gw, 38)

entry_history = picks.get("entry_history", {})
squad_ids, bank, already_made = advice.apply_pending_transfers(
    [pick["element"] for pick in picks["picks"]], entry_history.get("bank", 0), transfers, next_gw)
squad = sorted((players[i] for i in squad_ids if i in players), key=lambda p: p["element_type"])
squad_value = sum(p["now_cost"] for p in squad) + bank
first_name = entry.get("player_first_name", "").strip() or "there"
deadline = next(gw["deadline_time"] for gw in bootstrap["events"] if gw["id"] == next_gw)
deadline_text, zone_text = local_time(deadline)

# Banner, headline numbers and menu
st.markdown(
    f'<div class="hero"><h1>{escape(entry.get("name", "Your team"))}</h1>'
    f"<p>Hi {escape(first_name)}, here's how things look for Gameweek {next_gw}.</p></div>"
    '<div class="cards">'
    f'<div class="card"><div class="label">Total points</div><div class="value">{entry.get("summary_overall_points") or 0:,}</div></div>'
    f'<div class="card"><div class="label">Overall rank</div><div class="value">{entry.get("summary_overall_rank") or 0:,}</div></div>'
    f'<div class="card"><div class="label">In the bank</div><div class="value">{money(bank)}</div></div>'
    f'<div class="card"><div class="label">Gameweek {next_gw} deadline ({zone_text})</div><div class="value">{deadline_text}</div></div>'
    "</div>",
    unsafe_allow_html=True,
)

# The menu remembers which page is open, so changing a number on a page never jumps you elsewhere.
page = st.radio("Menu", PAGES, horizontal=True, key="page", label_visibility="collapsed")
st.write("")


# ----- This week -----
if page == "This week":
    st.subheader("Before the deadline")
    worries = 0
    for p in squad:
        warning = availability_warning(p)
        if warning:
            worries += 1
            chance = p.get("chance_of_playing_next_round")
            note(escape(warning), "danger" if chance is not None and chance <= 25 else "warn")
        risk = yellow_warning(p, next_gw)
        if risk:
            worries += 1
            note(escape(risk), "warn")
    if worries == 0:
        note("<b>Good news:</b> everyone is fit and nobody is close to a suspension.")

    st.subheader(f"How I'd line up for Gameweek {next_gw}")
    starters, bench = advice.pick_lineup(squad, team_table, next_gw)
    captain, vice = advice.captain_pick(starters, team_table, next_gw)
    shape = "-".join(str(sum(1 for p in starters if p["element_type"] == pos)) for pos in (2, 3, 4))
    st.markdown(pitch(starters, bench, captain, vice, team_table, team_names, next_gw), unsafe_allow_html=True)
    note(f"<b>Formation {shape}.</b> Captain {name(captain)} "
         f"({escape(next_match(captain, team_table, team_names, next_gw))}), vice-captain {name(vice)}. "
         "C and V mark them on the pitch, and a yellow ring means the player is a doubt.")

    blanks = [p["web_name"] for p in squad if not team_table.get(p["team"], {}).get(next_gw)]
    if blanks:
        note(f"<b>Heads up:</b> {escape(', '.join(blanks))} "
             f"{'has' if len(blanks) == 1 else 'have'} no match this gameweek, so keep them on the bench.", "warn")
    note("<b>Transfers:</b> I've worked out who to sell and buy with the money you actually have. "
         "Open <b>Transfers</b> in the menu above.")

# ----- My squad -----
elif page == "My squad":
    st.subheader("Your squad and its next fixtures")
    if already_made:
        st.caption(f"This includes the {already_made} transfer{'s' if already_made != 1 else ''} "
                   f"you have already made for Gameweek {next_gw}.")
    st.markdown(player_table(squad, team_table, team_names, gw_range), unsafe_allow_html=True)
    st.caption("Green is an easy match, grey is average, red is hard. H = home, A = away. "
               "Owned by = the share of all FPL managers who have that player.")

# ----- Transfers -----
elif page == "Transfers":
    st.subheader("Your transfers")
    estimate = advice.free_transfers(history, already_made)
    left, right = st.columns(2)
    st.session_state.setdefault("w_free_transfers", estimate)
    free = left.number_input("Free transfers you have left", min_value=0, max_value=5, key="w_free_transfers")
    right.markdown(f'<div class="card"><div class="label">Money in the bank</div>'
                   f'<div class="value">{money(bank)}</div></div>', unsafe_allow_html=True)
    st.caption(f"My estimate is {estimate}. If FPL shows a different number, change it here and I'll redo the plan.")

    st.subheader(f"My suggestion for Gameweek {next_gw}")
    moves, squad_after, bank_after = advice.plan_transfers(
        squad, all_players, team_table, bank, free, next_gw, last_gw)
    if free == 0:
        note("You have no free transfers left this week, and I wouldn't take a points hit unless a starter is "
             "injured. Sit tight and you will have one next week.")
    elif not moves:
        note("Your squad looks good for the coming weeks, and nothing you can afford is a clear upgrade. "
             "<b>Save the transfer.</b> An extra free transfer next week gives you more options.")
    else:
        st.write("Every move fits your budget. I never suggest selling a fit player that a quarter or more of "
                 "managers own, buying someone who has gone off form, or doubling up on one club's defence.")
        show_swaps(moves, team_table, team_names, next_gw)
        if len(moves) < free:
            note(f"That uses {len(moves)} of your {free} free transfers. I couldn't find another move worth "
                 "making, so I'd save the rest.")

    if next_gw + 1 <= 38:
        with st.expander(f"Looking ahead to Gameweek {next_gw + 1}"):
            later_moves, _, _ = advice.plan_transfers(
                squad_after, all_players, team_table, bank_after, 1, next_gw + 1, min(next_gw + LOOK_AHEAD, 38))
            if later_moves:
                st.write("If you follow the plan above, this is the move I'd line up next:")
                show_swaps(later_moves, team_table, team_names, next_gw + 1)
            else:
                st.write("Nothing stands out for next week yet. I'll look again once this gameweek's results are in.")

    dream = advice.save_up_targets(squad_after, all_players, team_table, bank_after, next_gw, last_gw)
    if dream:
        with st.expander("Worth saving up for"):
            st.write("In form with good fixtures, but out of reach right now:")
            for target, short_by in dream:
                st.markdown(f"- **{target['web_name']}** ({team_names[target['team']]}, {money(target['now_cost'])}): "
                            f"you are {money(short_by)} short, even after selling your most expensive "
                            f"{POSITIONS[target['element_type']]}.")
    st.caption("Prices use each player's current price. FPL may give you slightly less when you sell a player "
               "whose price has risen since you bought him.")

# ----- Chip planner -----
else:
    st.subheader("Plan your chips")
    st.write("You get two of each chip: one for each half of the season. Tap a chip to open it.")
    status = advice.chip_status(bootstrap, history, next_gw)
    position_words = {2: "Defender", 3: "Midfielder", 4: "Forward"}

    def half_name(window):
        return "first half" if window["start"] < 10 else "second half"

    for chip, label in advice.CHIP_LABELS.items():
        open_windows = [w for w in status[chip] if w["open"]]
        playable_now = [w for w in open_windows if w["start"] <= next_gw]
        if playable_now:
            summary = f"ready to play, use by Gameweek {playable_now[0]['stop']}"
        elif open_windows:
            summary = f"next one from Gameweek {open_windows[0]['start']}"
        else:
            summary = "none left this season"

        with st.expander(f"{label}  ·  {summary}"):
            for w in status[chip]:
                if w["played"]:
                    st.write(f"Your {half_name(w)} {label} was played in Gameweek {w['played']}.")
                elif not w["open"]:
                    st.write(f"Your {half_name(w)} {label} was not used and has expired.")

            for w in open_windows:
                first, last = max(w["start"], next_gw), w["stop"]
                plan = advice.chip_advice(chip, squad, team_table, first, last)
                if plan is None:
                    continue
                gw = plan["gw"]
                if w["start"] > next_gw:
                    st.markdown(f"**Your {half_name(w)} {label}** (from Gameweek {w['start']}, an early view)")
                else:
                    st.markdown(f"**Your {half_name(w)} {label}** (use it by Gameweek {last})")

                if chip == "3xc":
                    twice = " He plays twice that week." if plan["player"]["web_name"] in plan["doubles"] else ""
                    note(f"<b>My favourite: {escape(plan['player']['web_name'])} in Gameweek {gw}</b> "
                         f"({escape(next_match(plan['player'], team_table, team_names, gw))}).{twice}")
                    lines = []
                    for position, (option_gw, option) in plan["options"].items():
                        lines.append(f"- {position_words[position]}: **{option['web_name']}** in Gameweek {option_gw} "
                                     f"({next_match(option, team_table, team_names, option_gw)})")
                    st.markdown("Best option in each position:\n" + "\n".join(lines))
                elif chip == "bboost":
                    extra = f" {len(plan['doubles'])} of your players play twice." if plan["doubles"] else ""
                    warn = (f" Watch out: {escape(', '.join(plan['blanks']))} would have no match."
                            if plan["blanks"] else "")
                    note(f"<b>When I'd play it: Gameweek {gw}.</b> That is when all 15 of your players have "
                         f"their best combined fixtures.{extra}{warn}")
                elif chip == "freehit":
                    extra = (f" {len(plan['blanks'])} of your players have no match that week."
                             if plan["blanks"] else "")
                    note(f"<b>When I'd play it: Gameweek {gw}.</b> That is your squad's toughest week.{extra}")
                else:
                    note(f"<b>When I'd play it: just before Gameweek {gw}.</b> Gameweek {gw} to {plan['until']} "
                         "is your squad's hardest spell, and playing it then still leaves "
                         f"{38 - gw + 1} gameweeks to get the benefit. I never suggest leaving a Wildcard "
                         "to the last few weeks.")

                if chip in ("freehit", "wildcard"):
                    weeks = list(range(first, last + 1))
                    gw_key, budget_key = f"w_gw_{chip}_{w['start']}", f"w_budget_{chip}_{w['start']}"
                    if st.session_state.get(gw_key) not in weeks:
                        st.session_state[gw_key] = gw
                    st.session_state.setdefault(budget_key, min(max(squad_value / 10, 80.0), 130.0))
                    left, right = st.columns(2)
                    build_gw = left.selectbox(
                        "Build a team for", weeks, key=gw_key,
                        format_func=lambda g, pick=gw: f"Gameweek {g}" + (" (my pick)" if g == pick else ""))
                    budget = right.number_input("Budget (£m)", min_value=80.0, max_value=130.0, step=0.1,
                                                key=budget_key,
                                                help="Your squad value plus the money in your bank.")
                    until = build_gw if chip == "freehit" else min(build_gw + LOOK_AHEAD - 1, 38)
                    built = advice.build_squad(all_players, team_table, build_gw, until, round(budget * 10),
                                               bench_weight=0.6 if chip == "wildcard" else 0.0)
                    if built is None:
                        st.write("I couldn't build a full squad with that budget. Try a slightly higher number.")
                    else:
                        starters, bench, cost = built
                        best = max(starters, key=lambda p: advice.captain_score(p, team_table, build_gw))
                        aim = (f"Gameweek {build_gw} only" if chip == "freehit"
                               else f"Gameweek {build_gw} to {until}")
                        st.write(f"A team for {aim}. It costs {money(cost)} of your {money(round(budget * 10))}. "
                                 f"Captain: {best['web_name']}.")
                        shown = [build_gw] if chip == "freehit" else range(build_gw, until + 1)
                        st.markdown("**Starting eleven**")
                        st.markdown(player_table(starters, team_table, team_names, shown), unsafe_allow_html=True)
                        st.markdown("**Bench**")
                        st.markdown(player_table(bench, team_table, team_names, shown), unsafe_allow_html=True)
                        if chip == "wildcard":
                            keepers = [p for p in starters + bench if p["element_type"] == 1]
                            rota = advice.keeper_rotation(keepers, team_table, build_gw, until)
                            if len({k["id"] for _, k in rota}) == 1:
                                other = next(k for k in keepers if k["id"] != rota[0][1]["id"])
                                st.write(f"Goalkeepers: {rota[0][1]['web_name']} starts every week, with "
                                         f"{other['web_name']} as cheap cover. The bench is built to be played, "
                                         "so rotate the outfield players by fixture.")
                            else:
                                plan_text = ", ".join(f"GW{g} {k['web_name']}" for g, k in rota)
                                st.write(f"Goalkeepers: two to rotate by fixture. Start {plan_text}.")
                        else:
                            st.write("The bench is the cheapest cover available, so the money goes on the "
                                     "eleven who play.")
                st.write("")
    st.caption("Based on your squad today and the fixtures as they stand. Matches get moved during the season, "
               "so check back before you commit.")

st.divider()
left, right = st.columns([3, 1])
left.caption("FPL Assistant is a student project and is not affiliated with the Premier League. "
             "Advice is based on form, fixtures and ownership and is an estimate, not a prediction.")
if right.button("Switch to another team"):
    back_to_start()
