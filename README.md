# odds_ocr

Bukmekerių koeficientų nuotraukas (ekranvaizdžius) paverčia CSV failu. Nuotraukas skaito Claude per Anthropic API.

CSV formatas tinka projektui [event_probability](https://github.com/pgrigas-trainys/event_probability): failą galima įkelti mygtuku „Įkelti CSV“ arba paduoti `python/model.py`.

## Programėlė

`app/index.html` yra naršyklės programėlė. Joje įkeli ekranvaizdžius (nutempdamas, įklijuodamas Ctrl+V arba pasirinkdamas telefone), Claude nuskaito koeficientus, gautą lentelę gali pataisyti ir atsisiųsti CSV. Programėlė veikia kaip Claude artifact puslapis ir naudoja tavo Claude paskyrą, todėl API rakto nereikia. Jei Claude nepasiekiamas, koeficientus galima suvesti ranka.

## Komandinė eilutė (Python)

### Įdiegimas

```bash
git clone https://github.com/pgrigas-trainys/odds_ocr
cd odds_ocr
pip install -e .
export ANTHROPIC_API_KEY=sk-ant-...      # raktą gausite https://console.anthropic.com
```

### Naudojimas

```bash
# viena ar kelios nuotraukos, arba visas aplankas -> vienas CSV
odds-ocr nuotraukos/ -o fenerbahce_partizan.csv

# jei komandų pavadinimai nuotraukoje nesimato
odds-ocr hcp.png tot.png --home Fenerbahce --away Partizan

# papildomai po atskirą failą kiekvienai rinkai
odds-ocr nuotraukos/ --split csv/
```

Programa parodo, kiek eilučių rado kiekvienoje nuotraukoje, ir įspėja apie įtartinas eilutes, pvz. kai marža neįprasta arba tai pačiai linijai rasti skirtingi koeficientai. Prieš skaičiuodami vis tiek peržiūrėkite CSV failą.

Palaikomi formatai: JPG, PNG, WEBP, GIF. Vienas failas turi būti iki 5 MB. iPhone HEIC nuotraukas pirma konvertuokite į JPG.

## Rinkos

| `market` | Kas tai | `line` | `odds_a` | `odds_b` |
|---|---|---|---|---|
| `hcp` | handikapas | namų komandos handikapas, pvz. -11.5 | namai | svečiai |
| `tot` | taškų suma | pvz. 165.5 | daugiau | mažiau |
| `home` | namų komandos taškai | pvz. 88.5 | daugiau | mažiau |
| `away` | svečių komandos taškai | pvz. 77.5 | daugiau | mažiau |

Namų komanda yra ta, kuri įvykio pavadinime nurodyta pirma. Ketvirčiai, kėliniai, 1X2 ir žaidėjų rinkos praleidžiamos.

## Rezultato pavyzdys

```csv
market,line,odds_a,odds_b,bookmaker,home,away,image
hcp,-14.5,2.45,1.50,Betsson,Fenerbahce,Partizan,hcp.png
hcp,-12.5,2.15,1.70,Betsson,Fenerbahce,Partizan,hcp.png
tot,165.5,1.87,1.87,Betsson,Fenerbahce,Partizan,tot.png
```

Su `--split` sukuriami `hcp.csv`, `tot.csv`, `home.csv`, `away.csv`, kuriuos galima paduoti tiesiai:

```bash
python3 python/model.py --hcp csv/hcp.csv --tot csv/tot.csv --home-name Fenerbahce --away-name Partizan
```

## Nustatymai

- `--model` arba aplinkos kintamasis `ODDS_OCR_MODEL` nustato Claude modelį. Numatytasis yra `claude-sonnet-5-5`.
- Python kode: `from odds_ocr import extract; extract("shot.png").rows`

## Testai

```bash
pip install -e '.[dev]'
pytest
```

Testai API nekviečia, todėl raktas jiems nereikalingas.
