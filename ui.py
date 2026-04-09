from __future__ import annotations

import os
import sys
from typing import Iterable


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
BLUE = "\033[34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"


def render_matches(matches: list[dict]) -> str:
    use_color = _supports_color()
    use_unicode = _supports_unicode()
    lines = []
    for index, match in enumerate(matches, start=1):
        lines.append(_card_header(f"{index}. {match['name']}", use_color, use_unicode))
        lines.append(
            f"  {_label('Format', use_color)} {str(match['matchType']).upper()}   "
            f"{_label('Status', use_color)} {match['status']}"
        )
        if match.get("venue"):
            lines.append(f"  {_label('Venue', use_color)} {match['venue']}")
        for innings_score in match.get("score", []):
            inning = innings_score.get("inning", "Innings")
            runs = innings_score.get("r", 0)
            wickets = innings_score.get("w", 0)
            overs = _format_overs(innings_score.get("o", 0))
            lines.append(f"  {_score_chip(inning, runs, wickets, overs, use_color)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_scorecard(scorecard: dict) -> str:
    use_color = _supports_color()
    use_unicode = _supports_unicode()
    match = scorecard["match"]
    lines = [
        _hero_banner(match["name"], use_color),
        f"{_label('Format', use_color)} {str(match['match_type']).upper()}   "
        f"{_label('Status', use_color)} {match['status']}",
        f"{_label('Venue', use_color)} {match['venue']}",
    ]

    if match.get("date"):
        lines.append(f"{_label('Date', use_color)} {match['date']}")

    if scorecard.get("score"):
        lines.append("")
        lines.append(_section_title("Match Score", use_color, use_unicode))
        for innings_score in scorecard["score"]:
            inning = innings_score.get("inning", "Innings")
            runs = innings_score.get("r", 0)
            wickets = innings_score.get("w", 0)
            overs = _format_overs(innings_score.get("o", 0))
            lines.append(f"  {_score_chip(inning, runs, wickets, overs, use_color)}")

    for innings in scorecard.get("innings", []):
        lines.append("")
        lines.append(_innings_header(innings["title"], innings["summary"], use_color, use_unicode))
        lines.append("")
        lines.append(_section_title("Batting", use_color, use_unicode))
        lines.extend(
            _render_table(
                headers=["Batter", "Dismissal", "R", "B", "4s", "6s", "SR"],
                rows=[
                    [
                        row["player"],
                        row["dismissal"],
                        row["runs"],
                        row["balls"],
                        row["fours"],
                        row["sixes"],
                        row["strike_rate"],
                    ]
                    for row in innings.get("batting", [])
                ],
                empty_message="No batting data available.",
                use_color=use_color,
            )
        )

        if innings.get("extras"):
            lines.append(f"{_label('Extras', use_color)} {innings['extras']}")
        if innings.get("did_not_bat"):
            lines.append(f"{_label('Did not bat', use_color)} {', '.join(innings['did_not_bat'])}")

        lines.append("")
        lines.append(_section_title("Bowling", use_color, use_unicode))
        lines.extend(
            _render_table(
                headers=["Bowler", "O", "M", "R", "W", "Econ", "NB", "WD"],
                rows=[
                    [
                        row["player"],
                        row["overs"],
                        row["maidens"],
                        row["runs"],
                        row["wickets"],
                        row["economy"],
                        row["no_balls"],
                        row["wides"],
                    ]
                    for row in innings.get("bowling", [])
                ],
                empty_message="No bowling data available.",
                use_color=use_color,
            )
        )

    lines.append(_footer_rule(use_color, use_unicode))
    return "\n".join(lines)


def _render_table(headers: list[str], rows: list[list[str]], empty_message: str, use_color: bool) -> list[str]:
    if not rows:
        return [empty_message]

    widths = []
    for column_index, header in enumerate(headers):
        column_values = [str(row[column_index]) for row in rows]
        widths.append(max(len(header), *(len(value) for value in column_values)))

    rendered = [_render_row(headers, widths, use_color, header_row=True), _render_separator(widths, use_color)]
    rendered.extend(_render_row(row, widths) for row in rows)
    return rendered


def _render_row(values: Iterable[str], widths: list[int], use_color: bool = False, header_row: bool = False) -> str:
    cells = [str(value).ljust(widths[index]) for index, value in enumerate(values)]
    row = " | ".join(cells)
    if header_row and use_color:
        return f"{BOLD}{WHITE}{row}{RESET}"
    return row


def _render_separator(widths: list[int], use_color: bool = False) -> str:
    separator = "-+-".join("-" * width for width in widths)
    return f"{DIM}{separator}{RESET}" if use_color else separator


def _format_overs(value: object) -> str:
    text = str(value)
    if "." not in text:
        return text

    whole, balls = text.split(".", 1)
    if balls == "6":
        try:
            return str(int(whole) + 1)
        except ValueError:
            return text
    return text


def _supports_color() -> bool:
    return os.getenv("TERM") is not None or os.getenv("WT_SESSION") is not None or os.name == "nt"


def _supports_unicode() -> bool:
    encoding = (sys.stdout.encoding or "").lower()
    return "utf" in encoding


def _paint(text: str, color: str, use_color: bool, *, bold: bool = False, dim: bool = False) -> str:
    if not use_color:
        return text
    prefix = ""
    if bold:
        prefix += BOLD
    if dim:
        prefix += DIM
    return f"{prefix}{color}{text}{RESET}"


def _hero_banner(title: str, use_color: bool) -> str:
    use_unicode = _supports_unicode()
    if use_unicode:
        top = "╔" + "═" * 70 + "╗"
        middle = f"║ {title[:68].ljust(68)} ║"
        bottom = "╚" + "═" * 70 + "╝"
    else:
        top = "+" + "-" * 70 + "+"
        middle = f"| {title[:68].ljust(68)} |"
        bottom = "+" + "-" * 70 + "+"
    if not use_color:
        return "\n".join([top, middle, bottom])
    return "\n".join(
        [
            _paint(top, CYAN, use_color, bold=True),
            _paint(middle, CYAN, use_color, bold=True),
            _paint(bottom, CYAN, use_color, bold=True),
        ]
    )


def _card_header(title: str, use_color: bool, use_unicode: bool) -> str:
    marker = "◆" if use_unicode else ">"
    return _paint(f"{marker} {title}", BLUE, use_color, bold=True)


def _section_title(title: str, use_color: bool, use_unicode: bool) -> str:
    marker = "▸" if use_unicode else ">"
    return _paint(f"{marker} {title}", MAGENTA, use_color, bold=True)


def _innings_header(title: str, summary: str, use_color: bool, use_unicode: bool) -> str:
    marker = "◉" if use_unicode else "*"
    text = f"{marker} {title}  |  {summary}"
    return _paint(text, GREEN, use_color, bold=True)


def _label(label: str, use_color: bool) -> str:
    return _paint(f"{label}:", YELLOW, use_color, bold=True)


def _score_chip(inning: object, runs: object, wickets: object, overs: object, use_color: bool) -> str:
    base = f"{inning}: {runs}/{wickets} ({overs} ov)"
    return _paint(base, WHITE, use_color)


def _footer_rule(use_color: bool, use_unicode: bool) -> str:
    rule = ("═" * 72) if use_unicode else ("-" * 72)
    return _paint(rule, CYAN, use_color, dim=True)
