"""
Links between DestinE Data Lake (HDA) collections and application taxonomies.  Version 2 (3 Oct 2026).

Three evidence channels, each traceable in the output table:
  A. sensor chain   : collection -> instrument (HDA metadata) -> variable (WMO OSCAR expert rating)
                      -> EARSC service (taxonomy/variable_to_service.csv, proposed, not validated)
  B. detection      : instrument -> EARSC service for applications based on feature/event detection,
                      which OSCAR does not describe (taxonomy/instrument_to_service.csv, proposed)
  C. product family : rule on the collection id for model outputs and derived products that declare
                      no instrument (taxonomy/collection_rules.csv, proposed, with a plain-language rationale)

What "direct" and "enabling" mean
  direct   = the collection already is the information of the service (ready-to-use product)
  enabling = the collection is an input: the service still needs processing or modelling
  For channel A this now follows the `role` column of variable_to_service.csv (product / input).

How a level-2+ product collection is read (changed in v2)
  1. the variables named in its TITLE decide what the product is;
  2. failing that, the variables named in its catalogue keywords (medium confidence);
  3. failing that, variables named only in its description, if OSCAR rates them for the instrument
     (medium confidence, flagged).

Spatial resolution per collection (new in v2): build_meta() reads it from the catalogue title or
description, or from the WMO OSCAR page of the declared instrument. Nothing is filled from memory.

Rebuild from the live catalogue:  python ei_links.py
"""
import csv
import json
import os
import re

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TAX_DIR = os.path.join(HERE, "taxonomy")
LINKS_CSV = os.path.join(TAX_DIR, "collection_service_links.csv")
META_JSON = os.path.join(TAX_DIR, "collection_meta.json")
STAC = "https://hda.data.destination-earth.eu/stac/v2"
BOK_URL = "https://bok.eo4geo.eu/{}"

# HDA instrument name -> OSCAR instrument page (chosen by hand; AVHRR, HIRS, GNSS-RO, MWR are assumptions)
INSTRUMENT_TO_OSCAR = {
    "SEVIRI": "seviri", "ASCAT": "ascat", "OLCI": "olci", "SRAL": "sral", "Poseidon-4": "poseidon_4",
    "IASI": "iasi", "FCI": "fci", "MVIRI": "mviri", "SLSTR": "slstr", "AVHRR": "avhrr_3", "LI": "li",
    "GOME-2": "gome_2", "MHS": "mhs", "HIRS": "hirs_4", "AMR-C": "amr_c", "C-SAR": "sar_c_sentinel_1",
    "MSI": "msi_sentinel_2a", "TROPOMI": "tropomi", "AMSU-A": "amsu_a", "GNSS-RO RECEIVER": "gras",
    "MWR": "mwr_sentinel_3", "MSS": "mss", "TM": "tm", "ETM+": "etm_plus", "OLI": "oli", "TIRS": "tirs"}
# Level-2 collections that are still generic imagery (surface reflectance / temperature)
GENERIC_L2 = {"EO.ESA.DAT.SENTINEL-2.MSI.L2A", "EO.NASA.DAT.LANDSAT.C2_L2"}
# Level-2 collections bundling several products of the instrument, with the OSCAR variables they really contain.
# Sentinel-5P operational level-2 products: O3 (total, tropospheric, profile), NO2, SO2, CO, CH4, HCHO, cloud,
# UV aerosol index, aerosol layer height. Source: Copernicus SentiWiki, "S5P Products", read 3 Oct 2026.
# Surface irradiance and aerosol optical depth are NOT among them, whatever the sensor could measure.
MULTI_PRODUCT_L2 = {"EO.ESA.DAT.SENTINEL-5P.TROPOMI.L2": {
    "O3", "O3 Total Column", "NO2", "NO2 Total Column", "SO2", "SO2 Total Column", "CO", "CH4 mole fraction",
    "HCHO", "HCHO Total Column"}}
# labelled L1 in the catalogue but actually a geophysical product
PRODUCT_OVERRIDE = {"EO.EUM.DAT.MSG.CLM"}
# services that only make sense at local scale: reachable through the sensor chain only with these instruments.
# HIGH_RES = finest resolution of 100 m or better on the instrument's OSCAR page; MEDIUM_RES = 300 to 500 m.
LOCAL_SCALE_SERVICES = {"Monitor urban areas", "Monitor urban green & blue areas", "Monitor urban surroundings",
                        "Monitor construction & buildings", "Monitor vegetation encroachment",
                        "Asset infrastructure monitoring", "Map line of sight visibility (land surface)"}
HIGH_RES = {"C-SAR", "MSI", "TM", "ETM+", "OLI", "MSS", "TIRS"}
MEDIUM_RES = {"OLCI", "SLSTR"}
OCEAN_VARS = re.compile(r"Ocean |Colour Dissolved|Sea[- ]|Coastal sea|Significant wave|Dominant wave|Oil spill")
INSTRUMENT_NAMES = r"Ocean and Land Colou?r( Instrument| Imager)?|Sea and Land Surface Temperature Radiometer"
RANK = {"high": 2, "medium": 1}


def _read(name):
    with open(os.path.join(TAX_DIR, name), encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def load_reference():
    """Taxonomy + hand-made tables. Raises FileNotFoundError if the taxonomy folder is missing."""
    tax = json.load(open(os.path.join(TAX_DIR, "earsc_taxonomy.json"), encoding="utf-8"))
    oscar = json.load(open(os.path.join(TAX_DIR, "oscar_extract.json"), encoding="utf-8"))
    return {"tax": tax, "oscar": oscar, "var2svc": _read("variable_to_service.csv"),
            "inst2svc": _read("instrument_to_service.csv"), "rules": _read("collection_rules.csv")}


def _level_kind(c):
    """generic = raw/generic imagery (every use needs processing); multi = bundle of several products;
    product = one or a few geophysical products."""
    cid = c["id"]
    if cid in GENERIC_L2:
        return "generic"
    if cid in MULTI_PRODUCT_L2:
        return "multi"
    if cid in PRODUCT_OVERRIDE:
        return "product"
    lv = [str(x).upper() for x in (c.get("summaries") or {}).get("processing:level") or []]
    # the catalogue labels some Sentinel-3 level-2 collections as L1B: trust the "_2_" in the id
    if re.search(r"_2_|\.L2", cid):
        return "product"
    if any(x.startswith("L1") for x in lv) or re.search(r"level[- ]?1", c.get("title", ""), re.I):
        return "generic"
    return "product"


def build_links(collections, ref=None):
    """Returns a DataFrame: one row per (collection, EARSC service)."""
    ref = ref or load_reference()
    oscar_i = ref["oscar"]["instruments"]
    v2s = {}
    for r in ref["var2svc"]:
        if r["earsc_service"]:
            v2s.setdefault(r["oscar_variable"], []).append(r)
    i2s = {}
    for r in ref["inst2svc"]:
        i2s.setdefault(r["hda_instrument"], []).append(r)
    rules = [(re.compile(r["collection_id_regex"]), r) for r in ref["rules"]]

    rows = []

    def add(c, service, link_type, channel, path, conf, origin):
        rows.append({"collection_id": c["id"], "collection_title": c.get("title", ""), "earsc_service": service,
                     "link_type": link_type, "channel": channel, "path": path, "confidence": conf,
                     "origin": origin, "validated": "no"})

    def limits(v):
        """OSCAR's stated limitations, shortened: 'cloud sensitive, daylight only'."""
        parts = [p.strip().lower() for p in re.split(r"\.\.\s*|\.\s*$", v.get("limitations", "")) if p.strip()]
        parts = [p for p in parts if p != "no specific limitation"]
        return ("; limits: " + ", ".join(parts[:3])) if parts else ""

    def rating(instruments, var):
        """(instrument, relevance, label, limits) of the best OSCAR rating of `var` among the declared instruments."""
        best = None
        for inst in instruments:
            for v in oscar_i.get(INSTRUMENT_TO_OSCAR.get(inst, ""), {}).get("variables", []):
                if v["variable"] == var and (best is None or v["relevance"] < best[1]):
                    best = (inst, v["relevance"], v["relevance_label"], limits(v))
        return best

    for c in collections:
        instruments = (c.get("summaries") or {}).get("instruments") or []
        if instruments:
            kind = _level_kind(c)
            title = re.sub(INSTRUMENT_NAMES, " ", c.get("title", ""), flags=re.I)
            kw = " ; ".join(k for k in c.get("keywords", []) if ":" not in k)
            body = re.sub(INSTRUMENT_NAMES, " ", c.get("description", "") or "", flags=re.I)
            land_only = bool(re.search(r"\bland\b", title, re.I)) and not re.search(r"ocean|marine|sea\b|water", title, re.I)

            if kind == "generic":
                # --- A. raw or generic imagery: every OSCAR variable the instrument measures well is a possible use
                for inst in instruments:
                    for v in oscar_i.get(INSTRUMENT_TO_OSCAR.get(inst, ""), {}).get("variables", []):
                        if v["relevance"] > 2:
                            continue
                        # OSCAR rates a sensor's potential; when it calls the measurement "highly indirect" and the
                        # variable is not a declared objective of the mission, the link is too weak to propose
                        if "highly indirect" in v.get("limitations", "").lower() and not v.get("mission_objective"):
                            continue
                        strong = v["relevance"] == 1 or bool(v.get("mission_objective"))
                        for l in v2s.get(v["variable"], []):
                            svc = l["earsc_service"]
                            if svc in LOCAL_SCALE_SERVICES and inst not in HIGH_RES | MEDIUM_RES:
                                continue
                            conf = "high" if (l["confidence"] == "high" and strong
                                              and not (svc in LOCAL_SCALE_SERVICES and inst in MEDIUM_RES)) else "medium"
                            add(c, svc, "enabling", "A sensor chain",
                                f"{inst} → {v['variable']} (OSCAR {v['relevance']} – {v['relevance_label']}{limits(v)})",
                                conf, "WMO OSCAR + variable table (proposed)")
                    # --- B. detection-type applications
                    for l in i2s.get(inst, []):
                        if l.get("only_if_id_matches") and not re.search(l["only_if_id_matches"], c["id"]):
                            continue
                        add(c, l["earsc_service"], "enabling", "B detection",
                            f"{inst}: {l['rationale']}", l["confidence"], "instrument table (proposed)")
            else:
                # --- A. geophysical product(s): find which variables the collection carries
                cand = []   # (variable, how)
                if kind == "multi":
                    cand = [(var, "listed") for var in sorted(MULTI_PRODUCT_L2[c["id"]]) if var in v2s]
                else:
                    for var, links in v2s.items():
                        if re.search(links[0]["match_terms"], title, re.I):
                            cand.append((var, "title"))
                    if not cand:
                        for var, links in v2s.items():
                            if re.search(links[0]["match_terms"], kw, re.I):
                                cand.append((var, "keywords"))
                    if not cand:
                        for var, links in v2s.items():
                            rt = rating(instruments, var)
                            if rt and rt[1] <= 3 and re.search(links[0]["match_terms"], body, re.I):
                                cand.append((var, "description"))
                    if land_only:
                        cand = [x for x in cand if not OCEAN_VARS.match(x[0])]
                cand.sort(key=lambda x: ((rating(instruments, x[0]) or (None, 9))[1], x[0]))   # best-rated variable first
                for var, how in cand:
                    rt = rating(instruments, var)
                    inst = rt[0] if rt else instruments[0]
                    if rt:
                        label = f"{inst} → {var} (OSCAR {rt[1]} – {rt[2]}{rt[3]})"
                    else:
                        label = f"product title → {var} (no OSCAR rating for {inst})" if how == "title" \
                            else f"{inst} → {var} (no OSCAR rating)"
                    if how == "keywords":
                        label += " [variable named in the catalogue keywords]"
                    elif how == "description":
                        label += " [variable named in description only]"
                    for l in v2s[var]:
                        svc = l["earsc_service"]
                        if svc in LOCAL_SCALE_SERVICES and not (set(instruments) & (HIGH_RES | MEDIUM_RES)):
                            continue
                        ltype = "direct" if l.get("role", "product") == "product" else "enabling"
                        conf = l["confidence"] if how in ("title", "listed") else "medium"
                        if rt and rt[1] > 3:
                            conf = "medium"
                        if svc in LOCAL_SCALE_SERVICES and not (set(instruments) & HIGH_RES):
                            conf = "medium"
                        add(c, svc, ltype, "A sensor chain", label, conf, "WMO OSCAR + variable table (proposed)")
        # --- C. product families (rule on the id, explained in plain language)
        for rx, r in rules:
            if rx.search(c["id"]):
                add(c, r["earsc_service"], r["link_type"], "C product family",
                    r.get("rationale") or f"id matches /{r['collection_id_regex']}/", r["confidence"],
                    "family rule (proposed)")

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # one row per (collection, service): best confidence, direct beats enabling, keep up to 3 paths
    df["_r"] = df["confidence"].map(RANK) * 2 + (df["link_type"] == "direct").astype(int)
    df = df.sort_values("_r", ascending=False, kind="stable")
    agg = df.groupby(["collection_id", "earsc_service"], sort=False).agg(
        collection_title=("collection_title", "first"), link_type=("link_type", "first"),
        channel=("channel", lambda s: " + ".join(sorted(set(s)))),
        path=("path", lambda s: " | ".join(list(dict.fromkeys(s))[:3])),
        confidence=("confidence", "first"), origin=("origin", lambda s: " + ".join(sorted(set(s)))),
        validated=("validated", "first")).reset_index()
    return agg.sort_values(["earsc_service", "confidence", "collection_id"]).reset_index(drop=True)


# ----------------------------------------------------------------------------------------------------------
# Spatial resolution per collection, read from the catalogue text or from the instrument's OSCAR page
# ----------------------------------------------------------------------------------------------------------
_U = r"(?:km|m|met(?:er|re)s?|kilomet(?:er|re)s?|°|deg(?:ree)?s?\.?|arc[- ]?sec(?:ond)?s?|arc[- ]?min(?:ute)?s?)"
_N = r"(?:\d+/\d+|\d+(?:\.\d+)?)"
_NOT_RES = re.compile(r"^\s{0,2}(temperature|wind|height|above|depth|altitude|level|dew|gust|vertical|swath|orbit|wavelength|"
                      r"accurac|precision|uncertaint|error|bias|long\b|wide|width|thick|radius|distance|range|of high|away|"
                      r"apart|\u00b2|2\b(?!\s*(for|at|x))|elevation\b)", re.I)
_CTX_AFTER = r"[^.;:\n]{0,28}?\b(?:resolution|grid|gridded|pixel|sampling|raster|posting|IFOV|s\.s\.p|at nadir|near nadir|spacing|footprint)"
_CTX_BEFORE = r"\b(?:resolutions?|grid|gridded|pixel size|sampling|raster|posting|IFOV|spacing)\b(?:[^.;\n]|(?<=\d)\.(?=\d)){0,45}?"
_TILE = re.compile(r"tiles?|granules?|scenes?|swath|ortho-?image|area of|domain of|covering an area", re.I)


def _to_m(v, u):
    v = float(v.split("/")[0]) / float(v.split("/")[1]) if "/" in v else float(v)
    u = u.lower().rstrip(".")
    if u.startswith("km") or u.startswith("kilomet"):
        return v * 1000
    if u == "m" or u.startswith("met"):
        return v
    if u.startswith("°") or u.startswith("deg"):
        return v * 111320          # degrees of latitude; an approximation for longitude away from the equator
    if "sec" in u:
        return v / 3600 * 111320
    if "min" in u:
        return v / 60 * 111320
    return None


def scan_resolution(text, strict=True):
    """Finds statements of spatial resolution in `text`. Returns [(metres, as_written, snippet)].
    strict=True requires a resolution-like context (resolution, grid, pixel, sampling...)."""
    out = []
    text = re.sub(r"approx\.", "approx", text or "").replace("\u00bc", "1/4").replace("\u00bd", "1/2")
    text = re.sub(r"(\d+) x (\d+)-km IFOV", r"\2-km IFOV", text)      # "4 x 12-km IFOV" = four detectors of 12 km

    def add(groups, a, b):
        unit = groups[-1]
        tail = text[b:b + 22]
        pair = any(g is not None for g in groups[1:-1])
        if _NOT_RES.search(tail) and not (pair and re.match(r"\s?(2|\u00b2)\b", tail)) \
                and not re.match(r"\s{0,2}(x|by)\s*\d", tail):
            return
        if re.search(r"[A-Za-z_]$", text[max(0, a - 1):a]) or re.search(r"\d,$", text[max(0, a - 2):a]):
            return                                                      # t_2m, u10m, 2,544 km
        if _TILE.search(text[max(0, a - 45):b + 40]) \
                and not re.search(r"resolution|pixel|sampling|grid spacing|raster", text[max(0, a - 30):b + 25], re.I):
            return                                                      # tile or scene size, not a resolution
        for g in groups[:-1]:
            if g is None:
                continue
            mm = _to_m(g, unit)
            if mm and 0.2 <= mm <= 600000:
                out.append((mm, f"{g} {unit}".strip(), re.sub(r"\s+", " ", text[max(0, a - 60):b + 50]).strip()))

    pat2 = rf"({_N})\s?({_U})\s?(?:x|X|×|by)\s?({_N})\s?({_U})(?![A-Za-z])"
    for m in re.finditer(pat2, text):
        if strict and not re.search(r"resol|grid|pixel|raster|sampl", text[max(0, m.start() - 90):m.end() + 60], re.I):
            continue
        add((m.group(1), m.group(2)), m.start(), m.end())
        add((m.group(3), m.group(4)), m.start(), m.end())
    pat = rf"({_N})(?:\s?(?:to|and|or|–|-|x|X|×|by)\s?({_N}))?(?:\s?(?:to|and|or|–|-|x|X|×|by)\s?({_N}))?\s?-?\s?({_U})(?![A-Za-z])"
    for m in re.finditer(pat, text):
        a, b = m.span()
        if strict:
            before, after = text[max(0, a - 70):a], text[b:b + 60]
            if not (re.search(_CTX_BEFORE + r"$", before, re.I | re.S) or re.match(_CTX_AFTER, after, re.I)
                    or re.search(r"\d\s?[xX×]\s?\d", m.group(0))
                    or (re.search(r"(°|deg)", m.group(4)) and re.search(r"grid|resol", text[max(0, a - 80):b + 80], re.I))):
                continue
        add((m.group(1), m.group(2), m.group(3), m.group(4)), a, b)
    return out


def build_meta(collections, ref=None):
    """{collection_id: {res_m, res_txt, res_src, snip, sensor_res, revisit}}.
    res_m is the FINEST value stated, so a 'too coarse' warning is raised only when even the best case is too coarse."""
    ref = ref or load_reference()
    oscar_i = ref["oscar"]["instruments"]
    meta = {}
    for c in collections:
        title, desc = c.get("title", ""), c.get("description", "") or ""
        insts = [i for i in ((c.get("summaries") or {}).get("instruments") or []) if i in INSTRUMENT_TO_OSCAR]
        rec = {"res_m": None, "res_txt": "", "res_src": "", "snip": "", "sensor_res": "", "revisit": ""}
        cand = []
        if re.search(r"(raster|grid|swath|DEM|resol|\(|meters|metres)", title, re.I):
            for mm, shown, snip in scan_resolution(title, strict=False):
                if re.search(r"(surface and|depth|height|level|above)\s*$", title[:title.find(shown.split(" ")[0])], re.I):
                    continue
                cand.append((mm, shown, snip, "catalogue title"))
        if not cand:
            cand = [(mm, shown, snip, "catalogue description") for mm, shown, snip in scan_resolution(desc, strict=True)]
        if cand:
            best = min(cand, key=lambda x: x[0])
            several = len({round(x[0]) for x in cand}) > 1
            rec.update(res_m=round(best[0], 1), res_txt=best[1] + (" (finest of several values stated)" if several else ""),
                       res_src=best[3], snip=best[2])
        if insts:
            fields = [(i, oscar_i.get(INSTRUMENT_TO_OSCAR[i], {})) for i in insts]
            rec["sensor_res"] = " | ".join(f"{i}: {f['resolution']}" for i, f in fields if f.get("resolution"))
            rec["revisit"] = " | ".join(f"{i}: {f['coverage']}" for i, f in fields if f.get("coverage"))
            if rec["res_m"] is None and rec["sensor_res"]:
                found = [x for i, f in fields for x in scan_resolution(f.get("resolution", ""), strict=False)]
                if found:
                    best = min(found, key=lambda x: x[0])
                    rec.update(res_m=round(best[0], 1), res_txt=rec["sensor_res"],
                               res_src="WMO OSCAR (sensor, best case)", snip=rec["sensor_res"])
        meta[c["id"]] = rec
    return meta


def save_meta(meta):
    json.dump(meta, open(META_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return META_JSON


def load_meta():
    if not os.path.exists(META_JSON):
        return {}
    return json.load(open(META_JSON, encoding="utf-8"))


def format_resolution(m):
    """10 -> '10 m', 27830 -> '28 km'."""
    if m is None or m == "":
        return ""
    m = float(m)
    return f"{m:.0f} m" if m < 1000 else (f"{m / 1000:.1f} km" if m < 10000 else f"{m / 1000:.0f} km")


def load_links():
    """Stored links; rows edited by hand (validated = yes / rejected) are kept as they are."""
    if not os.path.exists(LINKS_CSV):
        return pd.DataFrame()
    return pd.read_csv(LINKS_CSV, sep=";", dtype=str).fillna("")


def save_links(df, keep_validation=True):
    """Writes the table. Validation marks set by hand in the previous file are carried over."""
    if keep_validation:
        old = load_links()
        if not old.empty:
            marks = {(r.collection_id, r.earsc_service): r.validated for r in old.itertuples()
                     if r.validated and r.validated != "no"}
            df = df.copy()
            df["validated"] = [marks.get((r.collection_id, r.earsc_service), r.validated) for r in df.itertuples()]
    df.to_csv(LINKS_CSV, sep=";", index=False, encoding="utf-8")
    return LINKS_CSV


def fetch_collections():
    import requests
    r = requests.get(f"{STAC}/collections", params={"limit": 1000}, headers={"Accept": "application/json"}, timeout=120)
    r.raise_for_status()
    return r.json().get("collections", [])


if __name__ == "__main__":
    cols = fetch_collections()
    ref = load_reference()
    links = build_links(cols, ref)
    path = save_links(links)
    meta = build_meta(cols, ref)
    save_meta(meta)
    covered = links["collection_id"].nunique()
    print(f"{len(cols)} collections, {len(links)} links, {covered} collections linked, "
          f"{links['earsc_service'].nunique()} services reached → {path}")
    print(f"{sum(1 for v in meta.values() if v['res_m'])} collections with a stated spatial resolution → {META_JSON}")
