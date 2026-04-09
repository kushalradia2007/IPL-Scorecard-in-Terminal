from __future__ import annotations

import sys

from api import (
    enrich_scorecard_with_match_info,
    get_current_matches,
    get_match_info,
    get_match_scorecard,
    parse_matches,
    parse_scorecard,
)
from ui import render_matches, render_scorecard


def main() -> None:
    encoding = (sys.stdout.encoding or "").lower()
    use_unicode = "utf" in encoding
    if use_unicode:
        print("╔══════════════════════════════════════════════════════════════════════╗")
        print("║                         IPL Live Scorecard CLI                       ║")
        print("╚══════════════════════════════════════════════════════════════════════╝")
    else:
        print("+----------------------------------------------------------------------+")
        print("|                         IPL Live Scorecard CLI                       |")
        print("+----------------------------------------------------------------------+")

    matches, error = get_current_matches()
    if error:
        print(f"\n[ERROR] {error}")
        return

    parsed_matches = parse_matches(matches)
    if not parsed_matches:
        print("No live or current matches were returned by the API.")
        return

    print(render_matches(parsed_matches))
    print("")
    try:
        choice = input("Select a match number for the full scorecard, or 0 to exit: ").strip()
    except EOFError:
        print("No interactive input was provided. Exiting after match list.")
        return

    if choice == "0":
        print("Exited without loading a scorecard.")
        return

    try:
        selected_index = int(choice) - 1
    except ValueError:
        print("Please enter a valid match number.")
        return

    if selected_index < 0 or selected_index >= len(parsed_matches):
        print("That match number is out of range.")
        return

    selected_match = parsed_matches[selected_index]
    payload, scorecard_error = get_match_scorecard(selected_match["id"])
    if scorecard_error:
        print(f"[ERROR] {scorecard_error}")
        return

    parsed_scorecard = parse_scorecard(payload)
    match_info_payload, _ = get_match_info(selected_match["id"])
    parsed_scorecard = enrich_scorecard_with_match_info(parsed_scorecard, match_info_payload)
    print("")
    print(render_scorecard(parsed_scorecard))


if __name__ == "__main__":
    main()
