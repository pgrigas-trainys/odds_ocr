"""CSV rašymas formatu, kurį supranta event_probability (app ir python/model.py).

Bendras failas: market,line,odds_a,odds_b,bookmaker,home,away,image
  - stulpelis `market` (hcp/tot/home/away) leidžia programai paskirstyti eilutes rinkoms;
  - pirmi trys skaitiniai stulpeliai yra linija, A, B – taip juos skaito model.py.
Atskiri failai (--split): po vieną kiekvienai rinkai, tinka `model.py --hcp/--tot/--home/--away`.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .extract import MARKETS, Extraction

HEADER = ["market", "line", "odds_a", "odds_b", "bookmaker", "home", "away", "image"]


def _fmt(x: float) -> str:
    return f"{x:g}"


def records(extractions: list[Extraction]) -> list[list[str]]:
    out, seen = [], set()
    for ex in extractions:
        for r in ex.rows:
            key = (r.market, r.line, ex.bookmaker.lower())
            if key in seen:
                continue
            seen.add(key)
            out.append([r.market, _fmt(r.line), f"{r.odds_a:.2f}", f"{r.odds_b:.2f}",
                        ex.bookmaker, ex.home, ex.away, ex.image])
    return out


def write_combined(extractions: list[Extraction], path: str | Path) -> int:
    rows = records(extractions)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    return len(rows)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "rungtynes"


def write_split(extractions: list[Extraction], folder: str | Path, prefix: str = "") -> dict[str, Path]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rows = records(extractions)
    written = {}
    for m in MARKETS:
        sub = [r for r in rows if r[0] == m]
        if not sub:
            continue
        path = folder / f"{prefix}{m}.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["line", "odds_a", "odds_b"])
            w.writerows(r[1:4] for r in sub)
        written[m] = path
    return written
