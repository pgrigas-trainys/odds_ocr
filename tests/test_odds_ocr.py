import base64
import csv
from types import SimpleNamespace

import pytest

from odds_ocr.cli import main
from odds_ocr.csvout import write_split
from odds_ocr.extract import clean_rows, extract, load_image

# 1x1 PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


class FakeClient:
    """Pakeičia anthropic.Anthropic: grąžina iš anksto paruoštą record_odds atsakymą."""

    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        block = SimpleNamespace(type="tool_use", name="record_odds", input=self.payloads.pop(0))
        return SimpleNamespace(content=[block])


HCP = {
    "bookmaker": "Betsson", "home": "Fenerbahce", "away": "Partizan",
    "rows": [
        {"market": "hcp", "line": -12.5, "odds_a": 2.15, "odds_b": 1.70},
        {"market": "hcp", "line": -14.5, "odds_a": 2.45, "odds_b": 1.50},
        {"market": "hcp", "line": -14.5, "odds_a": 2.45, "odds_b": 1.50},   # dublikatas
        {"market": "tot", "line": 165.5, "odds_a": 1.0, "odds_b": 1.85},    # blogas koef.
        {"market": "q1", "line": 40.5, "odds_a": 1.9, "odds_b": 1.9},       # nežinoma rinka
    ],
}
TOT = {"bookmaker": "Betsson", "rows": [{"market": "tot", "line": "165,5", "odds_a": "1,87", "odds_b": 1.87}]}


@pytest.fixture
def img(tmp_path):
    p = tmp_path / "shot.png"
    p.write_bytes(PNG)
    return p


def test_clean_rows_filters_and_sorts():
    rows, warnings = clean_rows(HCP["rows"])
    assert [(r.market, r.line) for r in rows] == [("hcp", -14.5), ("hcp", -12.5)]
    assert len(warnings) == 2


def test_clean_rows_accepts_comma_decimals():
    rows, _ = clean_rows(TOT["rows"])
    assert rows[0].line == 165.5 and rows[0].odds_a == 1.87


def test_load_image_rejects_unknown_format(tmp_path):
    p = tmp_path / "a.heic"
    p.write_bytes(b"x")
    with pytest.raises(ValueError):
        load_image(p)


def test_extract_sends_image_and_forces_tool(img):
    client = FakeClient(HCP)
    ex = extract(img, client=client, model="m")
    call = client.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "record_odds"}
    assert call["messages"][0]["content"][0]["source"]["media_type"] == "image/png"
    assert (ex.bookmaker, ex.home, ex.away) == ("Betsson", "Fenerbahce", "Partizan")
    assert len(ex.rows) == 2


def test_cli_combines_images_into_one_csv(tmp_path, img):
    img2 = tmp_path / "shot2.png"
    img2.write_bytes(PNG)
    out = tmp_path / "out.csv"
    code = main([str(tmp_path), "-o", str(out), "--split", str(tmp_path / "split")],
                client=FakeClient(HCP, TOT))
    assert code == 0
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert [r["market"] for r in rows] == ["hcp", "hcp", "tot"]
    assert rows[2]["home"] == "Fenerbahce"           # komandos perimtos iš pirmos nuotraukos
    assert rows[0]["odds_a"] == "2.45"
    split = list(csv.reader(open(tmp_path / "split" / "tot.csv", encoding="utf-8")))
    assert split == [["line", "odds_a", "odds_b"], ["165.5", "1.87", "1.87"]]


def test_output_matches_event_probability_reader(tmp_path, img):
    """event_probability/python/model.py ima pirmus tris skaitinius stulpelius: linija, A, B."""
    out = tmp_path / "out.csv"
    main([str(img), "-o", str(out)], client=FakeClient(HCP))
    nums = []
    for rec in csv.reader(open(out, encoding="utf-8")):
        vals = []
        for c in rec:
            try:
                vals.append(float(c))
            except ValueError:
                pass
        if len(vals) >= 3:
            nums.append(tuple(vals[:3]))
    assert nums == [(-14.5, 2.45, 1.5), (-12.5, 2.15, 1.7)]


def test_cli_without_odds_returns_error(img, tmp_path):
    code = main([str(img), "-o", str(tmp_path / "x.csv")], client=FakeClient({"rows": []}))
    assert code == 1
    assert not (tmp_path / "x.csv").exists()
