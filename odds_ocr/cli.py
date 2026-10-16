"""Komandinė eilutė: odds-ocr NUOTRAUKOS... -o rezultatas.csv"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .csvout import slug, write_combined, write_split
from .extract import DEFAULT_MODEL, MEDIA_TYPES, extract

LABELS = {"hcp": "handikapas", "tot": "taškų suma", "home": "namų taškai", "away": "svečių taškai"}


def collect_images(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in MEDIA_TYPES)
        elif p.is_file():
            files.append(p)
        else:
            print(f"Nerasta: {item}", file=sys.stderr)
    return files


def main(argv: list[str] | None = None, client=None) -> int:
    ap = argparse.ArgumentParser(
        prog="odds-ocr",
        description="Bukmekerių koeficientų nuotraukos -> CSV (per Claude API)")
    ap.add_argument("images", nargs="+", help="nuotraukos arba aplankai su nuotraukomis")
    ap.add_argument("-o", "--output", help="bendro CSV failo kelias (numatyta: <namai>_<svečiai>.csv)")
    ap.add_argument("--split", metavar="APLANKAS",
                    help="papildomai įrašyti po atskirą CSV kiekvienai rinkai (hcp.csv, tot.csv, ...)")
    ap.add_argument("--home", default="", help="namų komanda (jei nuotraukoje nesimato)")
    ap.add_argument("--away", default="", help="svečių komanda")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude modelis (numatyta {DEFAULT_MODEL})")
    args = ap.parse_args(argv)

    images = collect_images(args.images)
    if not images:
        print("Nėra nuotraukų (tinka: " + ", ".join(sorted(MEDIA_TYPES)) + ")", file=sys.stderr)
        return 2

    if client is None:
        try:
            import anthropic
        except ImportError:
            print("Įdiekite priklausomybes: pip install -e .", file=sys.stderr)
            return 2
        client = anthropic.Anthropic()

    results, failed = [], 0
    home, away = args.home, args.away
    for img in images:
        try:
            ex = extract(img, client=client, model=args.model, home=home, away=away)
        except Exception as e:  # viena bloga nuotrauka nesustabdo kitų
            failed += 1
            print(f"✗ {img.name}: {e}", file=sys.stderr)
            continue
        home, away = home or ex.home, away or ex.away  # komandas imame iš pirmos nuotraukos
        ex.home, ex.away = home, away
        counts = {}
        for r in ex.rows:
            counts[r.market] = counts.get(r.market, 0) + 1
        summary = ", ".join(f"{LABELS[m]} {n}" for m, n in counts.items()) or "koeficientų nerasta"
        print(f"✓ {img.name}: {summary}")
        for w in ex.warnings:
            print(f"   ! {w}")
        if ex.notes:
            print(f"   · {ex.notes}")
        results.append(ex)

    if not any(ex.rows for ex in results):
        print("Neišsaugota: nė vienoje nuotraukoje nerasta koeficientų.", file=sys.stderr)
        return 1

    out = args.output or f"{slug(home)}_{slug(away)}.csv"
    n = write_combined(results, out)
    print(f"\nĮrašyta {n} eil. -> {out}")
    if args.split:
        for m, p in write_split(results, args.split).items():
            print(f"  {LABELS[m]}: {p}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
