from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from config import AppConfig, get_config


def _fetch_json(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    config: AppConfig | None = None,
    endpoint: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    if config is None:
        try:
            config = get_config()
        except RuntimeError as exc:
            return None, str(exc)

    url = urljoin(f"{config.base_url.rstrip('/')}/", path.lstrip("/"))
    if params:
        url = f"{url}?{urlencode(params)}"

    request = Request(
        url,
        headers={
            "x-atd-key": config.api_key,
            "x-apihub-key": config.api_key,
            "x-apihub-host": config.api_host,
            "x-apihub-endpoint": endpoint or config.home_endpoint,
        },
    )

    try:
        with urlopen(request, timeout=config.timeout_seconds) as response:
            payload = response.read().decode("utf-8")
            data = json.loads(payload)
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        return None, f"HTTP {exc.code}: {message}"
    except URLError as exc:
        return None, f"Network error: {exc.reason}"
    except json.JSONDecodeError:
        return None, "The API returned invalid JSON."
    except Exception as exc:  # pragma: no cover
        return None, str(exc)

    if isinstance(data, dict) and data.get("status") == "failure":
        return None, data.get("reason", "The API reported a failure.")

    return data, None


def get_current_matches() -> tuple[list[dict[str, Any]] | None, str | None]:
    try:
        config = get_config()
    except RuntimeError as exc:
        return None, str(exc)

    data, error = _fetch_json(config.live_matches_path, config=config, endpoint=config.home_endpoint)
    if error:
        return None, error
    return _extract_live_matches(data), None


def get_match_scorecard(match_id: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        config = get_config()
    except RuntimeError as exc:
        return None, str(exc)

    scorecard_path = config.scorecard_path_template.format(match_id=match_id)
    data, error = _fetch_json(scorecard_path, config=config, endpoint=config.scorecard_endpoint)
    if error:
        return None, error

    payload = _extract_scorecard_payload(data)
    if not isinstance(payload, dict):
        return None, "No scorecard payload was returned for this match."
    return payload, None


def get_match_info(match_id: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        config = get_config()
    except RuntimeError as exc:
        return None, str(exc)

    match_info_path = config.match_info_path_template.format(match_id=match_id)
    data, error = _fetch_json(match_info_path, config=config, endpoint=config.match_info_endpoint)
    if error:
        return None, error
    if not isinstance(data, dict):
        return None, "No match info payload was returned for this match."
    return data, None


def parse_matches(matches: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    parsed_matches: list[dict[str, Any]] = []

    for match in matches or []:
        if not isinstance(match, dict):
            continue

        parsed_matches.append(
            {
                "id": str(_pick_nested_value(match, [["id"], ["matchId"], ["matchInfo", "matchId"]], "")),
                "name": _build_match_name(match),
                "matchType": _pick_nested_value(
                    match,
                    [["matchType"], ["matchFormat"], ["matchInfo", "matchFormat"]],
                    "unknown",
                ),
                "status": _pick_nested_value(
                    match,
                    [["status"], ["statusText"], ["matchInfo", "status"]],
                    "Status unavailable",
                ),
                "venue": _build_venue(match),
                "date": _pick_nested_value(match, [["date"], ["startDate"], ["matchInfo", "startDate"]], ""),
                "score": _extract_match_score(match),
                "teams": _extract_match_teams(match),
            }
        )

    return parsed_matches


def parse_scorecard(scorecard_payload: dict[str, Any]) -> dict[str, Any]:
    innings_payload = (
        scorecard_payload.get("scorecard")
        or scorecard_payload.get("innings")
        or scorecard_payload.get("scoreCard")
        or []
    )

    innings: list[dict[str, Any]] = []
    for innings_item in innings_payload:
        if not isinstance(innings_item, dict):
            continue

        batting_rows = _extract_batting_rows(innings_item)
        active_batting = [row for row in batting_rows if not row.get("_did_not_bat")]
        did_not_bat = [row["player"] for row in batting_rows if row.get("_did_not_bat")]

        innings.append(
            {
                "title": _build_innings_title(innings_item),
                "summary": _build_innings_summary(innings_item),
                "batting": active_batting,
                "bowling": _extract_bowling_rows(innings_item),
                "did_not_bat": did_not_bat
                or _extract_name_list(
                    innings_item,
                    ["did_not_bat", "didNotBat", "yetToBat", "yet_to_bat"],
                ),
                "extras": _extract_extras(innings_item),
            }
        )

    return {
        "match": {
            "id": str(scorecard_payload.get("id", "")),
            "name": scorecard_payload.get("name") or _build_match_name(scorecard_payload),
            "match_type": _pick_first_value(scorecard_payload, ["matchType", "matchFormat"], default="unknown"),
            "status": _pick_first_value(scorecard_payload, ["status", "statusText"], default="Status unavailable"),
            "venue": scorecard_payload.get("venue") or _build_venue(scorecard_payload),
            "date": _pick_first_value(scorecard_payload, ["date", "startDate"]),
            "teams": scorecard_payload.get("teams") or _extract_match_teams(scorecard_payload),
            "toss": _pick_first_value(scorecard_payload, ["tossWinner", "tossResults"]),
            "result": _pick_first_value(scorecard_payload, ["status", "statusText"]),
        },
        "score": scorecard_payload.get("score") or _extract_match_score(scorecard_payload),
        "innings": innings,
    }


def _extract_live_matches(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []

    extracted = _flatten_match_containers(data)
    return _dedupe_matches(extracted)


def _flatten_match_containers(value: Any) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue

            if isinstance(item.get("match"), dict):
                matches.extend(_flatten_match_containers(item["match"]))
                continue

            if "matchInfo" in item or "matchScore" in item or "status" in item:
                matches.append(item)
                continue

            for key in ["match", "seriesMatches", "matchDetailsMap", "matches", "data"]:
                nested = item.get(key)
                matches.extend(_flatten_match_containers(nested))

    elif isinstance(value, dict):
        if "matchInfo" in value or "matchScore" in value or "status" in value:
            matches.append(value)

        for key in ["match", "matchInfo", "seriesMatches", "matchDetailsMap", "matches", "data"]:
            nested = value.get(key)
            if nested is not None:
                matches.extend(_flatten_match_containers(nested))

        for nested in value.values():
            if isinstance(nested, (dict, list)):
                matches.extend(_flatten_match_containers(nested))

    return matches


def _dedupe_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for match in matches:
        match_id = str(_pick_nested_value(match, [["id"], ["matchId"], ["matchInfo", "matchId"]], ""))
        fingerprint = match_id or json.dumps(match, sort_keys=True, default=str)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(match)

    return deduped


def _extract_scorecard_payload(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None

    for key in ["data", "scoreCard", "scorecard"]:
        candidate = data.get(key)
        if isinstance(candidate, dict):
            return candidate

    return data


def _extract_team_names(team_info: Any) -> list[str]:
    teams: list[str] = []
    for item in team_info or []:
        if isinstance(item, dict):
            name = item.get("name") or item.get("shortname")
            if name:
                teams.append(str(name))
        elif item:
            teams.append(str(item))
    return teams


def _extract_match_teams(match: dict[str, Any]) -> list[str]:
    teams = match.get("teams")
    if isinstance(teams, list) and teams:
        return [str(team) for team in teams]

    team_names: list[str] = []
    team1 = _extract_team_name_obj(match.get("team1")) or _extract_team_name_obj(_pick_nested_object(match, ["matchInfo", "team1"]))
    team2 = _extract_team_name_obj(match.get("team2")) or _extract_team_name_obj(_pick_nested_object(match, ["matchInfo", "team2"]))

    for team in [team1, team2]:
        if team:
            team_names.append(team)

    if team_names:
        return team_names

    return _extract_team_names(match.get("teamInfo"))


def _extract_team_name_obj(value: Any) -> str:
    if isinstance(value, dict):
        for key in ["teamName", "teamname", "name", "teamSName", "teamsname", "shortName"]:
            if value.get(key):
                return str(value[key])
    elif value not in (None, ""):
        return str(value)
    return ""


def _build_match_name(match: dict[str, Any]) -> str:
    if match.get("name"):
        return str(match["name"])

    teams = _extract_match_teams(match)
    match_desc = _pick_first_value(match, ["matchDesc", "matchdesc"])
    if len(teams) >= 2 and match_desc:
        return f"{teams[0]} vs {teams[1]} - {match_desc}"
    if len(teams) >= 2:
        return f"{teams[0]} vs {teams[1]}"

    for key in ["seriesName", "seriesname"]:
        if match.get(key):
            return str(match[key])

    info = match.get("matchInfo")
    if isinstance(info, dict):
        if info.get("matchDesc"):
            teams = _extract_match_teams(match)
            if len(teams) >= 2:
                return f"{teams[0]} vs {teams[1]} - {info['matchDesc']}"
        if info.get("seriesName"):
            return str(info["seriesName"])

    if teams:
        return " vs ".join(teams)
    return "Unknown match"


def _build_venue(match: dict[str, Any]) -> str:
    if match.get("venue"):
        return str(match["venue"])

    venue_info = match.get("venueInfo") or match.get("venueinfo")
    if isinstance(venue_info, dict):
        parts = [venue_info.get("ground"), venue_info.get("city"), venue_info.get("country")]
        rendered = ", ".join(str(part) for part in parts if part)
        if rendered:
            return rendered

    info = match.get("matchInfo")
    if isinstance(info, dict) and isinstance(info.get("venueInfo"), dict):
        parts = [
            info["venueInfo"].get("ground"),
            info["venueInfo"].get("city"),
            info["venueInfo"].get("country"),
        ]
        rendered = ", ".join(str(part) for part in parts if part)
        if rendered:
            return rendered

    return "Venue unavailable"


def _extract_match_score(match: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(match.get("score"), list):
        return match["score"]

    match_score = match.get("matchScore")
    if isinstance(match_score, dict):
        innings_rows: list[dict[str, Any]] = []
        for key, label in [
            ("team1Score", "Team 1"),
            ("team2Score", "Team 2"),
        ]:
            team_score = match_score.get(key)
            if not isinstance(team_score, dict):
                continue

            innings_rows.append(
                {
                    "inning": team_score.get("inngs1", {}).get("inningsId")
                    or team_score.get("inngs1", {}).get("inningsNum")
                    or label,
                    "r": _pick_nested_value(team_score, [["inngs1", "runs"]], 0),
                    "w": _pick_nested_value(team_score, [["inngs1", "wickets"]], 0),
                    "o": _pick_nested_value(team_score, [["inngs1", "overs"]], 0),
                }
            )
            if isinstance(team_score.get("inngs2"), dict):
                innings_rows.append(
                    {
                        "inning": team_score.get("inngs2", {}).get("inningsId")
                        or team_score.get("inngs2", {}).get("inningsNum")
                        or f"{label} 2",
                        "r": _pick_nested_value(team_score, [["inngs2", "runs"]], 0),
                        "w": _pick_nested_value(team_score, [["inngs2", "wickets"]], 0),
                        "o": _pick_nested_value(team_score, [["inngs2", "overs"]], 0),
                    }
                )
        return innings_rows

    return []


def _pick_first_value(source: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def _pick_nested_value(source: dict[str, Any], paths: list[list[str]], default: Any = "") -> Any:
    for path in paths:
        current: Any = source
        found = True
        for key in path:
            if not isinstance(current, dict) or key not in current:
                found = False
                break
            current = current[key]
        if found and current not in (None, ""):
            return current
    return default


def _pick_nested_object(source: dict[str, Any], path: list[str]) -> dict[str, Any] | None:
    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, dict) else None


def _extract_batting_rows(innings_item: dict[str, Any]) -> list[dict[str, str]]:
    rows = _extract_table_rows(
        innings_item,
        ["batting", "battingScorecard", "batters", "batsman", "batsmenData"],
    )
    parsed: list[dict[str, str]] = []

    for row in rows:
        player_name = _extract_player_name(row, ["batsman", "batter", "player", "name"])
        dismissal = _pick_first_value(
            row,
            ["dismissal-text", "dismissal", "wicket", "howOut", "out_desc", "outDesc", "outdec"],
            default="not out",
        )
        runs = _stringify_stat(row, ["r", "runs"])
        balls = _stringify_stat(row, ["b", "balls"])
        did_not_bat = _is_did_not_bat_batter(row, dismissal, runs, balls)

        parsed.append(
            {
                "player": player_name,
                "dismissal": dismissal,
                "runs": runs,
                "balls": balls,
                "fours": _stringify_stat(row, ["4s", "fours"]),
                "sixes": _stringify_stat(row, ["6s", "sixes"]),
                "strike_rate": _stringify_stat(row, ["sr", "strikeRate", "s/r", "strkrate"]),
                "_did_not_bat": "yes" if did_not_bat else "",
            }
        )

    return parsed


def _extract_bowling_rows(innings_item: dict[str, Any]) -> list[dict[str, str]]:
    rows = _extract_table_rows(
        innings_item,
        ["bowling", "bowlingScorecard", "bowlers", "bowler", "bowlersData"],
    )
    parsed: list[dict[str, str]] = []

    for row in rows:
        player_name = _extract_player_name(row, ["bowler", "player", "name"])
        parsed.append(
            {
                "player": player_name,
                "overs": _stringify_stat(row, ["o", "overs"]),
                "maidens": _stringify_stat(row, ["m", "maidens"]),
                "runs": _stringify_stat(row, ["r", "runs"]),
                "wickets": _stringify_stat(row, ["w", "wickets"]),
                "economy": _stringify_stat(row, ["eco", "economy"]),
                "no_balls": _stringify_stat(row, ["nb", "noballs", "noBalls"]),
                "wides": _stringify_stat(row, ["wd", "wides"]),
            }
        )

    return parsed


def _extract_table_rows(source: dict[str, Any], keys: list[str]) -> list[dict[str, Any]]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            rows = [item for item in value.values() if isinstance(item, dict)]
            if rows:
                return rows
    return []


def _extract_name_list(source: dict[str, Any], keys: list[str]) -> list[str]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            names = [_extract_player_name(item, ["player", "name"]) for item in value]
            return [name for name in names if name]
        if isinstance(value, str) and value.strip():
            return [name.strip() for name in value.split(",") if name.strip()]
    return []


def _extract_extras(innings_item: dict[str, Any]) -> str:
    extras = innings_item.get("extras")
    if isinstance(extras, dict):
        total = extras.get("total") or extras.get("r") or extras.get("runs")
        breakdown = []
        for key in ["b", "lb", "wd", "nb", "penalty"]:
            if extras.get(key) not in (None, "", 0, "0"):
                breakdown.append(f"{key} {extras[key]}")
        if total not in (None, ""):
            suffix = f" ({', '.join(breakdown)})" if breakdown else ""
            return f"{total}{suffix}"
    if extras not in (None, ""):
        return str(extras)
    return ""


def _build_innings_title(innings_item: dict[str, Any]) -> str:
    explicit = _pick_first_value(
        innings_item,
        ["inning", "innings", "title", "name"],
    )
    if explicit:
        return explicit

    innings_id = innings_item.get("inningsid")
    if innings_id not in (None, ""):
        return f"Innings {innings_id}"

    return "Innings"


def _is_did_not_bat_batter(row: dict[str, Any], dismissal: str, runs: str, balls: str) -> bool:
    dismissal_text = dismissal.strip().lower()
    no_balls_faced = balls in {"0", "-", "0.0"}
    no_runs = runs in {"0", "-"}
    if dismissal_text in {"", "-", "dnb"} and no_balls_faced and no_runs:
        return True
    if dismissal_text == "not out" and no_balls_faced and no_runs and not row.get("outdec"):
        return True
    return False


def _extract_player_name(row: Any, keys: list[str]) -> str:
    if isinstance(row, str):
        return row

    if not isinstance(row, dict):
        return "Unknown"

    for key in keys:
        value = row.get(key)
        if isinstance(value, dict):
            nested = value.get("name") or value.get("fullName") or value.get("shortName")
            if nested:
                return str(nested)
        elif value not in (None, ""):
            return str(value)

    return "Unknown"


def _stringify_stat(source: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return str(value)
    return "-"


def _build_innings_summary(innings_item: dict[str, Any]) -> str:
    runs = _pick_first_value(innings_item, ["r", "runs", "score", "inngs1"])
    wickets = _pick_first_value(innings_item, ["w", "wickets"], default="-")
    overs = _pick_first_value(innings_item, ["o", "overs"], default="-")

    if runs:
        return f"{runs}/{wickets} ({_format_overs_value(overs)} ov)"
    return "Score unavailable"


def _format_overs_value(value: Any) -> str:
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


def enrich_scorecard_with_match_info(scorecard: dict[str, Any], match_info_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(match_info_payload, dict):
        return scorecard

    merged = dict(scorecard)
    match = dict(scorecard.get("match", {}))

    match["id"] = str(
        _pick_nested_value(match_info_payload, [["matchInfo", "matchId"], ["matchId"]], match.get("id", ""))
    )
    match["name"] = _build_match_name(match_info_payload) or match.get("name", "Unknown match")
    match["match_type"] = _pick_nested_value(
        match_info_payload,
        [["matchInfo", "matchFormat"], ["matchFormat"], ["matchformat"], ["matchType"], ["matchtype"]],
        match.get("match_type", "unknown"),
    )
    match["status"] = _pick_nested_value(
        match_info_payload,
        [["matchInfo", "status"], ["shortstatus"], ["status"], ["statusText"]],
        match.get("status", "Status unavailable"),
    )
    match["venue"] = _build_venue(match_info_payload) or match.get("venue", "Venue unavailable")
    match["date"] = _pick_nested_value(
        match_info_payload,
        [["matchInfo", "startDate"], ["startDate"], ["date"]],
        match.get("date", ""),
    )
    match["teams"] = _extract_match_teams(match_info_payload) or match.get("teams", [])

    merged["match"] = match
    return merged
