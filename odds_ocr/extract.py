"""Koeficientų nuskaitymas iš nuotraukos per Claude API.

Claude gauna nuotrauką ir privalo grąžinti duomenis per įrankį `record_odds`,
todėl atsakymas visada yra struktūrizuotas (ne laisvas tekstas).
"""
from __future__ import annotations

import base64
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODEL = os.environ.get("ODDS_OCR_MODEL", "claude-sonnet-5-5")

MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # Claude API riba vienai nuotraukai

MARKETS = ("hcp", "tot", "home", "away")
MARKET_ORDER = {m: i for i, m in enumerate(MARKETS)}

SYSTEM_PROMPT = """You read decimal betting odds from bookmaker screenshots (often Lithuanian: \
"Daugiau" = over, "Mažiau" = under, "Handikapas"/"Fora" = handicap) and record them with the \
record_odds tool. Never guess: only record numbers you can actually read in the image.

Markets (use these keys):
- hcp: HANDICAP / point spread for the whole game. line = the HOME (first-listed) team's \
handicap exactly as shown (e.g. -11.5); odds_a = home team with that handicap; odds_b = away \
team with the opposite handicap.
- tot: TOTAL POINTS over/under for the whole game. line = total (e.g. 165.5); odds_a = OVER; \
odds_b = UNDER.
- home: the HOME team's own points over/under. line e.g. 88.5; odds_a = OVER; odds_b = UNDER.
- away: the AWAY team's own points over/under. line e.g. 77.5; odds_a = OVER; odds_b = UNDER.

Rules:
- The home team is the one listed first in the event name ("A vs B", "A - B": A is home).
- Only full-game lines. Skip quarters, halves, periods, 1X2/moneyline, player props and any \
market that is not one of the four above.
- One row per line; each row needs both odds. Skip a line if either price is unreadable \
or suspended.
- Odds are decimal (e.g. 1.85). If the screenshot shows fractional or American odds, convert \
to decimal.
- Use a dot as the decimal separator."""

RECORD_TOOL = {
    "name": "record_odds",
    "description": "Record every readable odds line from the screenshot.",
    "input_schema": {
        "type": "object",
        "properties": {
            "bookmaker": {"type": "string", "description": "Bookmaker name if visible, else empty."},
            "home": {"type": "string", "description": "Home (first-listed) team, else empty."},
            "away": {"type": "string", "description": "Away (second-listed) team, else empty."},
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "market": {"type": "string", "enum": list(MARKETS)},
                        "line": {"type": "number"},
                        "odds_a": {"type": "number"},
                        "odds_b": {"type": "number"},
                    },
                    "required": ["market", "line", "odds_a", "odds_b"],
                },
            },
            "notes": {"type": "string", "description": "Anything unclear or skipped, briefly."},
        },
        "required": ["rows"],
    },
}


@dataclass(frozen=True)
class OddsRow:
    market: str
    line: float
    odds_a: float
    odds_b: float

    @property
    def margin(self) -> float:
        return 1 / self.odds_a + 1 / self.odds_b - 1


@dataclass
class Extraction:
    image: str
    bookmaker: str = ""
    home: str = ""
    away: str = ""
    rows: list[OddsRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: str = ""


def load_image(path: str | Path) -> tuple[str, str]:
    """Grąžina (media_type, base64 duomenys)."""
    p = Path(path)
    media = MEDIA_TYPES.get(p.suffix.lower())
    if not media:
        raise ValueError(f"{p.name}: nepalaikomas formatas (tinka: {', '.join(sorted(MEDIA_TYPES))})")
    data = p.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"{p.name}: nuotrauka didesnė nei 5 MB, sumažinkite ją")
    return media, base64.standard_b64encode(data).decode("ascii")


def _num(v) -> float:
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return math.nan


def clean_rows(raw_rows: list[dict]) -> tuple[list[OddsRow], list[str]]:
    """Patikrina Claude grąžintas eilutes: atmeta netinkamas, pašalina dublikatus, surikiuoja."""
    rows: dict[tuple[str, float], OddsRow] = {}
    warnings: list[str] = []
    for i, r in enumerate(raw_rows or [], 1):
        market = str(r.get("market", "")).strip().lower()
        line, a, b = _num(r.get("line")), _num(r.get("odds_a")), _num(r.get("odds_b"))
        if market not in MARKETS:
            warnings.append(f"eilutė {i}: nežinoma rinka {market!r}, praleista")
            continue
        if not all(math.isfinite(x) for x in (line, a, b)):
            warnings.append(f"eilutė {i}: trūksta skaičių, praleista")
            continue
        if a <= 1 or b <= 1:
            warnings.append(f"eilutė {i} ({market} {line:g}): koeficientas ≤ 1, praleista")
            continue
        row = OddsRow(market, line, round(a, 3), round(b, 3))
        if not -0.02 <= row.margin <= 0.25:
            warnings.append(f"{market} {line:g}: neįprasta marža {row.margin:.1%}, patikrinkite")
        key = (market, line)
        if key in rows and rows[key] != row:
            warnings.append(f"{market} {line:g}: skirtingi koeficientai tai pačiai linijai, paliktas pirmas")
            continue
        rows.setdefault(key, row)
    ordered = sorted(rows.values(), key=lambda r: (MARKET_ORDER[r.market], r.line))
    return ordered, warnings


def extract(image_path: str | Path, client=None, model: str = DEFAULT_MODEL,
            home: str = "", away: str = "") -> Extraction:
    """Nuskaito vieną nuotrauką. `client` – anthropic.Anthropic (arba testinis pakaitalas)."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    media, data = load_image(image_path)
    hint = ""
    if home or away:
        hint = f"\nThe match is {home or '?'} (home) vs {away or '?'} (away)."
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[RECORD_TOOL],
        tool_choice={"type": "tool", "name": "record_odds"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
                {"type": "text", "text": "Record all odds from this screenshot." + hint},
            ],
        }],
    )
    payload = next((b.input for b in msg.content if getattr(b, "type", "") == "tool_use"), None)
    if payload is None:
        raise RuntimeError(f"{Path(image_path).name}: Claude negrąžino koeficientų")
    rows, warnings = clean_rows(payload.get("rows", []))
    return Extraction(
        image=Path(image_path).name,
        bookmaker=(payload.get("bookmaker") or "").strip(),
        home=home or (payload.get("home") or "").strip(),
        away=away or (payload.get("away") or "").strip(),
        rows=rows,
        warnings=warnings,
        notes=(payload.get("notes") or "").strip(),
    )
