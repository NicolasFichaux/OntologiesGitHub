# Earth data navigator — notes for a coding agent

Read this before changing anything. It states what the project is, how it is built and tested, and the rules that must survive every change.

## What it is

A prototype that takes a need written in plain language ("which districts overheat in summer?") and leads to data of the DestinE Data Lake, through the Data-Information-Value (DIV) view of the DestinE co-design toolkit:
usage ecosystem → value-embedding usage → valuable information (expected information, then its ingredients) → data → digital infrastructure.

Two tools, linked by small JSON files:

| Tool | Where it runs | What it can do | What it cannot do |
|---|---|---|---|
| `page/` → `dist/earth-data-navigator.html` | Published as a Claude artifact (claude.ai) | Ask Claude (no API key: each viewer's own account), DIV graph, layers, e-shape pilots, workshops, prototype plans | Contact any other site (no data, no DestinE, no map tiles) |
| `local_app/` (Streamlit) | The user's machine | DestinE login (typed by the user), HDA search/order/download, OpenStreetMap, prototypes generated on demand | Ask a language model (no key configured yet) |

Bridge files: `navigator_request_*.json` (area, period, collection) and `prototype_plan_*.json` (ingredient, recipe, area, period), saved by the page and loaded in the sidebar of the local app.

## Layout

```
page/page.html          source of the page (HTML + CSS + JS in one file; two placeholders /*__DATA__*/ and /*__MAP__*/)
page/build.py           builds dist/earth-data-navigator.html (embeds tables, catalogue snapshot, basemap, thumbnails)
page/pilots_build.py    rebuilds data/pilots_v2.json (e-shape catalogue + Data Management Plans + hand-made pilot → EARSC table)
page/data/              catalogue snapshot (hda_cols.json), Natural Earth basemap, thumbnails, e-shape inputs
page/tests/             Playwright tests (pw*.py); Claude is always mocked
local_app/hda_app.py    Streamlit app (tabs: Applications, Prototypes, Collections, Search, Orders, Services)
local_app/ei_links.py   collection → EARSC service links (3 channels) and per-collection resolution; `python ei_links.py` rebuilds the link table
local_app/ei_proto.py   prototype engine: 4 recipes, each returning figure + trace; `python ei_proto.py plan.json`
local_app/make_tables.py  generates the variable/instrument/rule tables in taxonomy/
local_app/taxonomy/     EARSC taxonomy, WMO OSCAR extract, the tables, the generated link table, collection_meta.json
local_app/tests/        Streamlit AppTest and engine tests (the engine tests need the network)
```

## Commands

```
pip install -r local_app/requirements-hda.txt playwright && playwright install chromium
streamlit run local_app/hda_app.py
(cd local_app && python make_tables.py && python ei_links.py)   # after editing the tables; ei_links reads the live catalogue
python page/build.py                                               # after editing page.html or any table
for f in page/tests/pw*.py; do python $f; done                     # every test must end with "errors []"
python local_app/tests/t6.py ; python local_app/tests/t10.py
```

## Rules that must hold

1. **Nothing invented.** No reference, URL, figure, resolution or dataset id may be written from memory. Every reference in the code was seen on the date given next to it. If something is unknown, the interface says so ("not stated in the catalogue", "no recipe yet").
2. **Closed lists.** The language model may only return EARSC service names, OSCAR variable names and collection ids that exist in the embedded tables; anything else is dropped in code.
3. **Traceability of processing.** Every step of a prototype carries one nature: `documented` (published method, with its source), `choice` (parameter or shortcut, with who set it), `interpretation` (reading not validated), `service` (existing service, not reprocessed). A drafted method uses `named` (method named by the model, reference to verify). Never present an interpretation as a result.
4. **"Ready to use" means the collection carries the information itself** (`role = product` in `variable_to_service.csv`). Inputs are "needs processing".
5. **Say where a figure comes from.** Resolution: catalogue title, catalogue description or WMO OSCAR sensor page, with "at best" when it is a best case. Snapshot dates are shown at the top of the page.
6. **The user's wording wins** over the model's rewording in the DIV view.
7. **No credentials in files.** DestinE password and any API key are typed by the user or read from the environment; never written to the repository, the page or a bridge file.
8. **The page must work without a model** (manual choice of a service) and must fail with a readable reason.
9. Interface text is English, plain, without jargon; comments in English.

## Constraints of the published page

- No network at all, except the capabilities of the Claude artifact runtime: `window.claude.use("sample")` (ask Claude), `"downloads"` (save a file). Scripts may load only from the allowed CDNs; everything else is inlined.
- The same page falls back to the chat-preview API when `sample` is absent (`llmJSON` in page.html). This path failed in the user's desktop app; treat it as unreliable.
- A published artifact can only be updated from a Claude conversation.

## Known limits (do not hide them)

- The three link tables and the pilot → EARSC table are proposals by Claude, not validated by experts.
- The prototype recipes read public copies of the data (Sentinel-2 and Copernicus DEM on AWS, Landsat on Microsoft Planetary Computer, PVGIS), not the DestinE API.
- HDA scripts and the DestinE path have never been run with real credentials by the author.
- The page was tested with a mocked Claude only; the real model's behaviour was observed by the user, not measured.
- 88 of 314 collections state no resolution; 63 have a usable regional extent.

## Next steps, in the order that removes the most uncertainty

1. **DestinE reading for the recipes.** Run "Run the DestinE check" (Prototypes tab) with a real token; it lists asset names and properties without downloading. Write the `destine` backend of `ei_proto.py` from that report.
2. **One app.** Add a model layer to the local app (OpenAI-compatible endpoint: base URL, key from the environment, model name) and port the page's prompts (`prompt()`, `analysisPrompt()`, `pilotPrompt()`, `regPrompt()`, `draftPrompt()` in page.html).
3. **A test bench of about ten real needs**, to compare models on: service chosen, valid JSON, French, ingredients.
4. Validation of the tables with domain experts; more recipes (each with a verified reference and a test on two areas).
