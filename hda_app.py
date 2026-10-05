"""
Interactive test bench for the DestinE Data Lake — Harmonized Data Access (HDA) API
    https://hda.data.destination-earth.eu/stac/v2

  • Authentication : DESP account (username/password) → DESP token → DEDL token (OAuth2 token exchange)
                     or paste an existing DEDL access token
  • Metadata       : services, collections (free text + CQL2), collection detail, queryables
  • Applications   : EARSC taxonomy (markets / themes) → collections, through WMO OSCAR variables and
                     link tables stored in ./taxonomy (see ei_links.py); links are proposals to validate
  • Data           : STAC item search (bbox, datetime, queryables) → assets download / lazy Zarr opening
                     ECMWF on-demand datasets → order → poll → download

Run:  streamlit run hda_app.py
Credentials stay in this local session's memory; they are never written to disk or displayed.
"""
import base64
import datetime as dt
import json
import os
import time
from urllib.parse import parse_qs, urlparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
import xarray as xr

try:
    import ei_links
except Exception as _e:  # the test bench keeps working without the taxonomy module
    ei_links, _EI_ERROR = None, str(_e)

HDA = "https://hda.data.destination-earth.eu"
STAC = f"{HDA}/stac/v2"
DESP_IAM = "https://auth.destine.eu/realms/desp/protocol/openid-connect"
DESP_CLIENT = "dedl-hda"
DESP_REDIRECT = f"{HDA}/stac"
DEDL_TOKEN_URL = "https://identity.data.destination-earth.eu/auth/realms/dedl/protocol/openid-connect/token"
DEDL_CLIENT = "hda-public"
CQL2_EXAMPLES = {
    "(none)": "",
    "Climate DT gen. 2 collections": "id like 'EO.ECMWF.DAT.D1.DT_CLIMATE.G2%'",
    "Hosted on LUMI backend": "A_CONTAINS(federation:backends,('dedt_lumi'))",
    "Processing level L1": "A_CONTAINS(summaries.processing:level,('L1'))",
}
PROVIDERS = {"EO.ESA": "ESA", "EO.EUM": "EUMETSAT", "EO.ECMWF": "ECMWF", "EO.CLMS": "CLMS",
             "EO.MO": "Mercator Ocean", "EO.GBIF": "GBIF", "STAT.EUSTAT": "Eurostat"}

st.set_page_config(page_title="HDA API test bench", page_icon="🌐", layout="wide")


# ============================================================================
# Helpers
# ============================================================================
class ApiError(Exception):
    pass


def token():
    t = st.session_state.get("token")
    if t and st.session_state.get("token_exp", 1e18) < time.time():
        st.session_state.pop("token")
        return None
    return t


def auth_headers():
    t = token()
    return {"Authorization": f"Bearer {t}"} if t else {}


def http(method, url, auth=False, **kw):
    headers = {"Accept": "application/json", **kw.pop("headers", {})}
    if auth:
        headers.update(auth_headers())
    t0 = time.perf_counter()
    r = requests.request(method, url, headers=headers, timeout=kw.pop("timeout", 90), **kw)
    st.session_state["last_call"] = (f"{method} {url.split('?')[0].replace(HDA, '')} → "
                                     f"HTTP {r.status_code} in {time.perf_counter() - t0:.2f} s")
    if not r.ok:
        hint = ""
        if r.status_code == 401:
            hint = "\n→ Get a token in the sidebar (or it has expired)."
        elif r.status_code == 403:
            hint = "\n→ This collection may need extended access (e.g. Digital Twin outputs)."
        elif r.status_code == 429:
            hint = "\n→ Rate limit reached (default quota: 4 requests/second)."
        raise ApiError(f"HTTP {r.status_code} on {method} {url}\n{r.text[:800]}{hint}")
    return r


def human(n):
    if n is None:
        return "–"
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:,.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def jwt_claims(tok):
    try:
        p = tok.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
    except Exception:
        return {}


def get_dedl_token(username, password):
    """DESP login (authorization-code flow on the Keycloak form) then token exchange for a DEDL token."""
    from lxml import html
    with requests.Session() as s:
        page = s.get(f"{DESP_IAM}/auth", timeout=60, params={
            "client_id": DESP_CLIENT, "redirect_uri": DESP_REDIRECT,
            "scope": "openid", "response_type": "code"})
        page.raise_for_status()
        action = html.fromstring(page.content.decode()).forms[0].action
        login = s.post(action, data={"username": username, "password": password},
                       allow_redirects=False, timeout=60)
        if login.status_code == 200:
            msg = html.fromstring(login.content).xpath('//span[@id="input-error"]/text()')
            raise ApiError(f"DESP login refused: {msg[0].strip() if msg else 'check username/password'}")
        if login.status_code != 302:
            raise ApiError(f"DESP login failed (HTTP {login.status_code})")
        code = parse_qs(urlparse(login.headers["Location"]).query).get("code", [None])[0]
        if not code:
            raise ApiError("No authorization code returned by DESP (is 2-factor authentication enabled?)")
        r = s.post(f"{DESP_IAM}/token", timeout=60, data={
            "client_id": DESP_CLIENT, "redirect_uri": DESP_REDIRECT, "code": code,
            "grant_type": "authorization_code", "scope": ""})
        if not r.ok:
            raise ApiError(f"DESP token request failed: HTTP {r.status_code} {r.text[:300]}")
        desp = r.json()["access_token"]
    r = requests.post(DEDL_TOKEN_URL, timeout=60, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": desp, "subject_issuer": "desp-oidc",
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "client_id": DEDL_CLIENT, "audience": DEDL_CLIENT})
    if not r.ok:
        raise ApiError(f"DEDL token exchange failed: HTTP {r.status_code} {r.text[:300]}")
    j = r.json()
    return j["access_token"], time.time() + j.get("expires_in", 36000)


def bbox_map(n, w, s, e, key, features=None, height=260):
    layers = [pdk.Layer("PolygonLayer", data=[{"p": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}],
                        get_polygon="p", get_fill_color=[230, 120, 40, 40],
                        get_line_color=[230, 120, 40], line_width_min_pixels=2, stroked=True)]
    if features:
        fc = {"type": "FeatureCollection",
              "features": [{"type": "Feature", "geometry": f["geometry"], "properties": {"id": f["id"]}}
                           for f in features if f.get("geometry")]}
        layers.append(pdk.Layer("GeoJsonLayer", fc, get_fill_color=[40, 120, 220, 50],
                                get_line_color=[40, 120, 220], line_width_min_pixels=1,
                                pickable=True))
    span = max(abs(e - w), abs(n - s), 0.5)
    view = pdk.ViewState(latitude=(n + s) / 2, longitude=(w + e) / 2,
                         zoom=float(np.clip(np.log2(360 / span) - 0.5, 0, 10)))
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, map_style=None,
                             tooltip={"text": "{id}"} if features else None),
                    height=height, key=key)


def plot_dataset(ds, key):
    if not ds.data_vars:
        return
    var = st.selectbox("Variable to plot", list(ds.data_vars), key=f"{key}_var")
    da = ds[var]
    tdim = next((d for d in da.dims if "time" in d), None)
    sdims = [d for d in da.dims if d in ("latitude", "longitude", "lat", "lon", "x", "y")]
    other = [d for d in da.dims if d not in sdims and d != tdim]
    if other:
        da = da.isel({d: 0 for d in other})
        st.caption(f"Secondary dimensions fixed at index 0: {', '.join(other)}")
    c1, c2 = st.columns(2)
    if tdim and da.sizes[tdim] > 1:
        c1.markdown(f"**{da.attrs.get('long_name', var)}** ({da.attrs.get('units', '')}) — spatial mean")
        c1.line_chart((da.mean(sdims) if sdims else da).to_series(), height=280)
    if len(sdims) == 2 and all(da.sizes[d] > 1 for d in sdims):
        fig, ax = plt.subplots(figsize=(5, 3.6))
        (da.isel({tdim: 0}) if tdim else da).plot(ax=ax, cmap="viridis")
        c2.pyplot(fig, clear_figure=True)


def download_to_disk(href, folder, name=None):
    os.makedirs(folder, exist_ok=True)
    t0 = time.perf_counter()
    with requests.get(href, headers=auth_headers(), stream=True, timeout=600) as r:
        if not r.ok:
            raise ApiError(f"HTTP {r.status_code} downloading {href}\n{r.text[:400]}")
        total = int(r.headers.get("content-length") or 0)
        name = name or _filename(r, href)
        path = os.path.join(folder, name)
        bar = st.progress(0.0, text=f"Downloading {name}…")
        done = 0
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    bar.progress(min(done / total, 1.0), text=f"{human(done)} / {human(total)}")
        bar.empty()
    dur = time.perf_counter() - t0
    return path, done, dur


def _filename(r, href):
    cd = r.headers.get("content-disposition", "")
    if "filename=" in cd:
        return cd.split("filename=")[-1].strip('"; ')
    return os.path.basename(urlparse(href).path) or "download.bin"


def show_file(path, key):
    st.success(f"Saved to `{path}`")
    if path.endswith((".nc", ".nc4", ".netcdf")):
        try:
            ds = xr.open_dataset(path)
            with st.expander("File structure"):
                st.text(str(ds))
            plot_dataset(ds, key)
        except Exception as e:
            st.warning(f"Could not open with xarray: {e}")


def queryable_form(props, required, key, skip=(), derived=None, ecmwf_style=False):
    """Build widgets from a JSON-schema 'queryables' document; returns {property: STAC query clause}."""
    derived = derived or {}
    out, cols = {}, st.columns(2)
    i = 0
    for name, sch in props.items():
        if name in skip:
            continue
        enum = sch.get("enum") or sch.get("items", {}).get("enum")
        typ = sch.get("type")
        label = f"{sch.get('title', name)}  ·  `{name}`" + ("  *" if name in required else "")
        col = cols[i % 2]
        short = name.split(":")[-1]
        if short in derived:
            vals = derived[short]
            if enum:
                vals = [v for v in vals if v in enum]
            if vals:
                out[name] = {"eq": vals if (typ == "array" or ecmwf_style) else vals[0]}
            continue
        if enum:
            i += 1
            default = sch.get("default")
            if typ == "array":
                dflt = [d for d in (default if isinstance(default, list) else [default]) if d in enum]
                if not dflt and name in required:
                    dflt = enum[:1]
                v = col.multiselect(label, enum, default=dflt, key=f"{key}_{name}")
                if v:
                    out[name] = {"eq": v}
            else:
                opts = ["(any)"] + list(enum) if name not in required else list(enum)
                if ecmwf_style and short == "data_format" and "netcdf" in enum:
                    default = "netcdf"  # enables the in-app preview
                idx = opts.index(default) if default in opts else 0
                v = col.selectbox(label, opts, index=idx, key=f"{key}_{name}")
                if v != "(any)":
                    out[name] = {"eq": [v] if ecmwf_style else v}
        elif typ in ("number", "integer"):
            i += 1
            lo, hi = sch.get("minimum", 0), sch.get("maximum", 100)
            if col.checkbox(f"Filter {label} ≤", key=f"{key}_{name}_on"):
                v = col.slider(name, float(lo), float(hi), float(hi), key=f"{key}_{name}")
                out[name] = {"lte": v}
    return out


# ============================================================================
# Sidebar — authentication + common space/time parameters
# ============================================================================
def apply_nav_request():
    """Fill area, period and collection from a request file saved by the Earth data navigator."""
    req = st.session_state.pop("nav_request", None)
    if not req:
        return
    try:
        if req.get("prototype_plan"):                       # plan for the "Prototypes" tab
            if req.get("bbox"):
                w, s_, e, n = [float(x) for x in req["bbox"]]
                st.session_state.update(bb_n=n, bb_s=s_, bb_w=w, bb_e=e)
            if req.get("start"):
                st.session_state["d0"] = dt.date.fromisoformat(req["start"])
            if req.get("end"):
                st.session_state["d1"] = dt.date.fromisoformat(req["end"])
            st.session_state["proto_plan"] = req
            st.session_state["proto_ingr"] = str(req.get("ingredient", ""))
            st.session_state["proto_need"] = str(req.get("need", ""))
            st.session_state.pop("proto_res", None)
            st.session_state["nav_msg"] = f"Prototype plan loaded for “{req.get('ingredient', '')}”. Open the tab “Prototypes · on demand”."
            return
        b = req.get("bbox", {})
        st.session_state.update(bb_n=float(b["north"]), bb_s=float(b["south"]), bb_w=float(b["west"]), bb_e=float(b["east"]))
        if req.get("start"):
            st.session_state["d0"] = dt.date.fromisoformat(req["start"])
        if req.get("end"):
            st.session_state["d1"] = dt.date.fromisoformat(req["end"])
        cid = str(req["collection"])
        st.session_state["cid"] = cid
        st.session_state["cid_from_app"] = True
        if req.get("mode") == "order":
            st.session_state["o_cid"] = cid
        else:
            st.session_state["s_cid"] = cid
        tab = "ECMWF orders · data" if req.get("mode") == "order" else "Search items · data"
        st.session_state["nav_msg"] = f"Request loaded for `{cid}`. Get a token below, then open the tab “{tab}”."
    except Exception as e:
        st.session_state["nav_msg"] = f"This file is not a navigator request: {e}"


with st.sidebar:
    st.header("📥 Request from the navigator")
    up = st.file_uploader("Load a request or a prototype plan (.json) saved by the Earth data navigator", type=["json"], key="nav_file")
    if up is not None and st.session_state.get("nav_loaded") != up.file_id:
        st.session_state["nav_loaded"] = up.file_id
        try:
            st.session_state["nav_request"] = json.loads(up.getvalue().decode("utf-8"))
        except Exception as e:
            st.session_state["nav_msg"] = f"Unreadable file: {e}"
    apply_nav_request()
    if st.session_state.get("nav_msg"):
        st.info(st.session_state["nav_msg"])
    st.header("🔑 Authentication")
    mode = st.radio("Method", ["DESP username / password", "Paste a DEDL access token"],
                    label_visibility="collapsed", key="auth_mode")
    if mode.startswith("DESP"):
        user = st.text_input("DESP username", os.environ.get("DESP_USERNAME", ""))
        pwd = st.text_input("DESP password", type="password", value=os.environ.get("DESP_PASSWORD", ""))
        if st.button("Get token", type="primary", disabled=not (user and pwd)):
            try:
                with st.spinner("DESP login → DEDL token exchange…"):
                    tok, exp = get_dedl_token(user, pwd)
                st.session_state.update(token=tok, token_exp=exp)
            except Exception as e:
                st.error(str(e).replace(pwd, "•••"))
    else:
        pasted = st.text_input("Bearer token", type="password", key="auth_paste")
        if st.button("Use this token", disabled=not pasted, key="auth_use"):
            exp = jwt_claims(pasted).get("exp", time.time() + 36000)
            st.session_state.update(token=pasted, token_exp=exp)
    if token():
        c = jwt_claims(token())
        left = st.session_state["token_exp"] - time.time()
        st.success(f"Token active · {c.get('preferred_username', '')} · expires in {left / 3600:.1f} h")
        if st.button("Forget token"):
            st.session_state.pop("token", None)
            st.rerun()
    else:
        st.caption("Metadata (collections, queryables, services) is public. Search, orders and "
                   "downloads need a token.")

    st.header("🌍 Area and period")
    c1, c2 = st.columns(2)
    for _k, _v in (("bb_n", 51.5), ("bb_s", 49.5), ("bb_w", 2.0), ("bb_e", 4.5)):
        st.session_state.setdefault(_k, _v)
    north = c1.number_input("North", -90.0, 90.0, step=0.25, key="bb_n")
    south = c2.number_input("South", -90.0, 90.0, step=0.25, key="bb_s")
    west = c1.number_input("West", -180.0, 180.0, step=0.25, key="bb_w")
    east = c2.number_input("East", -180.0, 180.0, step=0.25, key="bb_e")
    if south >= north or west >= east:
        st.error("Check the bounding box (South < North, West < East).")
    st.session_state.setdefault("d0", dt.date(2024, 7, 1))
    st.session_state.setdefault("d1", dt.date(2024, 7, 7))
    date0 = st.date_input("Start", key="d0")
    date1 = st.date_input("End", key="d1")
    hours = st.multiselect("Hours (UTC, ECMWF orders)", [f"{h:02d}:00" for h in range(24)],
                           default=["00:00", "12:00"])
    bbox_map(north, west, south, east, "map_sidebar", height=200)
    st.header("💾 Downloads")
    dl_dir = st.text_input("Local folder", os.path.abspath("hda_downloads"))
    if "last_call" in st.session_state:
        st.caption(f"Last call: {st.session_state['last_call']}")

st.title("🌐 DestinE Data Lake — HDA API test bench")
t_app, t_proto, t_col, t_search, t_order, t_srv = st.tabs(
    ["Applications · taxonomy", "Prototypes · on demand", "Collections · metadata", "Search items · data", "ECMWF orders · data", "Services"])


# ============================================================================
# Cached metadata calls (public)
# ============================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def list_collections(q, limit, cql2):
    params = {"limit": limit}
    if q:
        params["q"] = q
    if cql2:
        params["filter"] = cql2
    return http("GET", f"{STAC}/collections", params=params).json()


@st.cache_data(ttl=3600, show_spinner=False)
def get_collection(cid):
    return http("GET", f"{STAC}/collections/{cid}").json()


@st.cache_data(ttl=600, show_spinner=False)
def get_queryables(cid, frozen_params=()):
    return http("GET", f"{STAC}/collections/{cid}/queryables", params=list(frozen_params)).json()


def provider_of(cid):
    return next((v for k, v in PROVIDERS.items() if cid.startswith(k)), cid.split(".")[1] if "." in cid else "")


# ============================================================================
# Applications · taxonomy  (EARSC services ↔ HDA collections)
# ============================================================================
@st.cache_data(show_spinner=False)
def ei_reference():
    return ei_links.load_reference() if ei_links else None


def ei_table():
    if ei_links is None:
        return pd.DataFrame()
    if "ei_links_df" not in st.session_state:
        st.session_state["ei_links_df"] = ei_links.load_links()
    return st.session_state["ei_links_df"]


def _to_data_tabs(cid):
    st.session_state["s_cid"] = cid
    if cid.startswith("EO.ECMWF"):
        st.session_state["o_cid"] = cid


def _pick_from_list():
    st.session_state["cid"] = st.session_state["col_pick"]
    st.session_state["cid_from_app"] = False
    _to_data_tabs(st.session_state["cid"])


def use_collection(cid):
    """Callback: push a collection chosen in the Applications tab to the metadata and data tabs."""
    st.session_state.update(cid=cid, cid_from_app=True)
    _to_data_tabs(cid)


with t_app:
    st.subheader("From an application to the data")
    try:
        ref = ei_reference()
    except Exception as e:
        ref = None
        st.error(f"Taxonomy files not readable: {e}")
    if ei_links is None:
        st.info(f"Module `ei_links.py` not found next to this app ({_EI_ERROR}).")
    elif ref:
        links = ei_table()
        services = ref["tax"]["thematic_services"]
        by_name = {s["service"]: s for s in services}
        n_per = links.groupby("earsc_service").size().to_dict() if not links.empty else {}
        st.caption("EARSC taxonomy (portal extraction) · sensor→variable ratings from WMO OSCAR · variable→service, "
                   "detection and product-family tables are **proposals to validate** (CSV files in `./taxonomy`).")

        entry = st.radio("Entry point", ["Market (who uses it)", "Theme (what is observed)", "Free text"],
                         horizontal=True, key="app_entry")
        cands = []
        if entry.startswith("Market"):
            sectors = ref["tax"]["market_sectors"]
            c1, c2 = st.columns(2)
            mk = c1.selectbox("Market", list(dict.fromkeys(x["market"] for x in sectors)), key="app_mk")
            secs = [x for x in sectors if x["market"] == mk]
            sec = c2.selectbox("Sector", [x["sector"] for x in secs], key=f"app_sec_{mk}")
            srec = next(x for x in secs if x["sector"] == sec)
            st.caption(f"**{sec}** — {srec['composition']}")
            cands = list(dict.fromkeys(v["thematic_service"] for v in srec["services"] if v.get("thematic_service")))
            if not cands:
                st.warning("The EARSC portal lists no service for this sector; use the Theme or Free text entry.")
        elif entry.startswith("Theme"):
            c1, c2 = st.columns(2)
            dom = c1.selectbox("Domain", list(dict.fromkeys(x["domain"] for x in services)), key="app_dom")
            areas = list(dict.fromkeys(x["area"] for x in services if x["domain"] == dom))
            area = c2.selectbox("Thematic area", ["(all)"] + areas, key=f"app_area_{dom}")
            cands = [x["service"] for x in services if x["domain"] == dom and area in ("(all)", x["area"])]
        else:
            ft = st.text_input("Describe the need", "", key="app_ft",
                               placeholder="e.g. urban heat island, solar farm siting, oil spill, flood extent…")
            toks = [t for t in ft.lower().split() if len(t) > 2]
            if toks:
                scored = []
                for x in services:
                    txt = f"{x['service']} {x['area']} {x['description']}".lower()
                    n = sum(t in txt for t in toks)
                    if n:
                        scored.append((n + 2 * sum(t in x["service"].lower() for t in toks), x["service"]))
                cands = [name for _, name in sorted(scored, key=lambda z: -z[0])]
                if not cands:
                    st.warning("No EARSC service description contains these words.")

        if cands:
            svc = st.selectbox("EARSC service", cands, key=f"app_svc_{entry[:4]}",
                               format_func=lambda n: f"{n}  ·  {n_per.get(n, 0)} collection(s)")
            rec = by_name[svc]
            st.markdown(f"**{rec['domain']} › {rec['area']} › {svc}**")
            st.write(rec["description"])
            meta = []
            if rec.get("markets"):
                meta.append("Markets: " + "; ".join(rec["markets"]))
            code = rec.get("bok_service") or rec.get("bok_area")
            if code:
                meta.append(f"EO4GEO BoK: [{code}]({ei_links.BOK_URL.format(code)})")
            if rec.get("wiki_url"):
                meta.append(f"[EARSC wiki page]({rec['wiki_url']})")
            st.caption(" · ".join(meta))

            mine = links[links["earsc_service"] == svc] if not links.empty else links
            c1, c2 = st.columns(2)
            only_high = c1.checkbox("High confidence only", False, key="app_high")
            hide_rej = c2.checkbox("Hide rejected links", True, key="app_rej")
            if only_high:
                mine = mine[mine["confidence"] == "high"]
            if hide_rej and not mine.empty:
                mine = mine[mine["validated"] != "rejected"]
            meta_ = ei_links.load_meta()
            if not mine.empty:
                mine = mine.copy()
                mine["resolution"] = [ei_links.format_resolution((meta_.get(c) or {}).get("res_m")) for c in mine["collection_id"]]
                mine["resolution_source"] = [(meta_.get(c) or {}).get("res_src", "") for c in mine["collection_id"]]
            show = ["collection_id", "collection_title", "confidence", "resolution", "path", "resolution_source", "validated"]
            for ltype, title, help_ in (
                    ("direct", "Ready-to-use products", "The collection already contains the information."),
                    ("enabling", "Data that need processing", "Sensor or model data from which the service can be "
                                                               "derived with a processing chain.")):
                part = mine[mine["link_type"] == ltype] if not mine.empty else mine
                st.markdown(f"**{title}** ({len(part)}) — {help_}")
                if ltype == "direct" and len(part):
                    st.caption("Resolution is the finest value stated in the catalogue, or the sensor's best case on its "
                               "WMO OSCAR page; blank when neither states one.")
                if len(part):
                    st.dataframe(part[show].sort_values(["confidence", "collection_id"]),
                                 hide_index=True, width="stretch")
            if mine.empty:
                st.info("No collection of the HDA catalogue is linked to this service yet.")
            else:
                c1, c2 = st.columns([3, 1])
                pick = c1.selectbox("Collection", mine["collection_id"].tolist(), key=f"app_pick_{svc}",
                                    label_visibility="collapsed")
                c2.button("Use in data tabs", type="primary", key="app_use", on_click=use_collection, args=(pick,))
                if st.session_state.get("cid_from_app") and st.session_state.get("cid") == pick:
                    st.success(f"`{pick}` is now selected in *Collections · metadata* and in the data tabs.")

        with st.expander("Coverage, provenance and maintenance"):
            if links.empty:
                st.warning("No link table yet: build it from the live catalogue.")
            else:
                m = st.columns(4)
                m[0].metric("Links", len(links))
                m[1].metric("Collections linked", links["collection_id"].nunique())
                m[2].metric("Services reached", f"{links['earsc_service'].nunique()} / {len(services)}")
                m[3].metric("Validated", int((links["validated"] == "yes").sum()))
                st.dataframe(links.groupby(["channel", "link_type", "confidence"]).size().rename("links").reset_index(),
                             hide_index=True)
                missing = [x["service"] for x in services if x["service"] not in n_per]
                st.caption("EARSC services without any collection: " + "; ".join(missing))
            st.markdown(
                "- **A sensor chain**: collection → instrument (HDA metadata) → variable (WMO OSCAR expert rating) "
                "→ service (`variable_to_service.csv`). The `role` column of that table says whether the variable is "
                "the information itself (*product*: ready to use) or one ingredient (*input*: needs processing). "
                "A product collection is read from its title first, then its keywords, then its description.\n"
                "- **B detection**: instrument → service for applications based on feature detection, absent from "
                "OSCAR (`instrument_to_service.csv`).\n"
                "- **C product family**: rule on the collection id for model outputs and derived products "
                "(`collection_rules.csv`), each with a plain-language rationale shown in the *path* column.\n"
                "- To validate or reject a link, set `validated` to `yes` or `rejected` in "
                "`collection_service_links.csv`; these marks survive a rebuild.")
            if st.button("Rebuild links from the live catalogue", key="app_rebuild"):
                try:
                    with st.spinner("Reading the catalogue and applying the three tables…"):
                        cols_ = list_collections("", 1000, "").get("collections", [])
                        ref_ = ei_links.load_reference()
                        new = ei_links.build_links(cols_, ref_)
                        ei_links.save_links(new)
                        ei_links.save_meta(ei_links.build_meta(cols_, ref_))
                        st.session_state["ei_links_df"] = ei_links.load_links()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            if not links.empty:
                st.download_button("Download the link table (CSV)", links.to_csv(sep=";", index=False),
                                   "collection_service_links.csv", "text/csv", key="app_dl")


# ============================================================================
# Services
# ============================================================================
with t_srv:
    st.subheader("DEDL edge services")
    c1, c2 = st.columns([4, 1])
    sq = c1.text_input("Free text", "", key="srv_q", placeholder="e.g. jupyter, stack, islet…")
    if c2.button("List services", key="srv_btn"):
        try:
            j = http("GET", f"{HDA}/services", params={"q": sq} if sq else None).json()
            items = j.get("services") or j.get("features") or (j if isinstance(j, list) else [])
            rows = [{"id": s.get("id"), "title": s.get("title") or s.get("properties", {}).get("title"),
                     "description": (s.get("description") or s.get("properties", {}).get("description") or "")[:200]}
                    for s in items]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            with st.expander("Raw response"):
                st.json(j, expanded=False)
        except Exception as e:
            st.error(str(e))


# ============================================================================
# Collections · metadata
# ============================================================================
with t_col:
    st.subheader("Collection discovery")
    c1, c2, c3 = st.columns([3, 1, 2])
    q = c1.text_input("Free text (supports OR / AND)", "temperature", key="col_q")
    limit = c2.number_input("Max results", 1, 1000, 100, key="col_limit")
    ex = c3.selectbox("CQL2 filter example", list(CQL2_EXAMPLES), key="col_ex")
    cql2 = st.text_input("CQL2 filter (optional)", CQL2_EXAMPLES[ex], key=f"col_cql2_{ex}")
    if st.button("Search collections", type="primary", key="col_btn"):
        try:
            with st.spinner("Querying the catalogue…"):
                st.session_state["cols"] = list_collections(q, int(limit), cql2)
        except Exception as e:
            st.error(str(e))

    res = st.session_state.get("cols")
    if res:
        rows = []
        for c in res.get("collections", []):
            ti = (c.get("extent", {}).get("temporal", {}).get("interval") or [[None, None]])[0]
            rows.append({"id": c["id"], "provider": provider_of(c["id"]), "title": c.get("title"),
                         "start": (ti[0] or "")[:10], "end": (ti[1] or "…")[:10],
                         "backends": ", ".join(c.get("summaries", {}).get("federation:backends", [])),
                         "keywords": ", ".join(c.get("keywords", [])[:5])})
        df = pd.DataFrame(rows)
        provs = sorted(df["provider"].unique()) if not df.empty else []
        pf = st.multiselect("Filter by provider (empty = all)", provs, default=[],
                            placeholder="All providers", key=f"col_prov_{hash(tuple(provs))}")
        df = df[df["provider"].isin(pf)] if (pf and not df.empty) else df
        st.caption(f"{len(df)} collections shown ({len(rows)} returned"
                   f"{', numberMatched=' + str(res['numberMatched']) if res.get('numberMatched') else ''})")
        st.dataframe(df, hide_index=True, width="stretch")
        if not df.empty:
            ids = df["id"].tolist()
            if st.session_state.get("cid") in ids:
                st.session_state["col_pick"] = st.session_state["cid"]
            elif st.session_state.get("col_pick") not in ids:
                st.session_state.pop("col_pick", None)
            st.selectbox("Collection to inspect", ids, key="col_pick", on_change=_pick_from_list)
            if not st.session_state.get("cid_from_app") or st.session_state.get("cid") is None:
                st.session_state["cid"] = st.session_state["col_pick"]

    cid = st.session_state.get("cid")
    if cid:
        st.divider()
        try:
            col = get_collection(cid)
            qa = get_queryables(cid)
        except Exception as e:
            st.error(str(e))
        else:
            st.subheader(col.get("title", cid))
            st.caption(f"`{cid}`")
            ti = col.get("extent", {}).get("temporal", {}).get("interval", [[None, None]])[0]
            m = st.columns(4)
            m[0].metric("Start", (ti[0] or "–")[:10])
            m[1].metric("End", (ti[1] or "ongoing")[:10])
            m[2].metric("Licence", col.get("license", "–"))
            m[3].metric("DOI", col.get("sci:doi", "–"))
            orderable = any(l.get("rel") == "retrieve" for l in col.get("links", []))
            st.info("**On-demand (orderable) collection** → use the *ECMWF orders* tab." if orderable
                    else "**Archive collection** → use the *Search items* tab.")
            with st.expander("Description"):
                st.markdown(col.get("dedl:short_description") or col.get("description", ""))
            with st.expander(f"Links ({len(col.get('links', []))})"):
                st.dataframe(pd.DataFrame([{"rel": l.get("rel"), "method": l.get("method", "GET"),
                                            "title": l.get("title"), "href": l.get("href")}
                                           for l in col.get("links", [])]), hide_index=True, width="stretch")
            if col.get("cube:variables"):
                with st.expander(f"Datacube variables ({len(col['cube:variables'])})"):
                    st.dataframe(pd.DataFrame([{"variable": k, **{kk: str(vv) for kk, vv in v.items()}}
                                               for k, v in col["cube:variables"].items()]),
                                 hide_index=True, width="stretch")
            with st.expander("Raw STAC collection"):
                st.json(col, expanded=False)

            st.markdown("**Queryables** (filters accepted by search / order)")
            props, req = qa.get("properties", {}), set(qa.get("required", []))
            st.dataframe(pd.DataFrame([{
                "property": k, "required": k in req, "type": str(v.get("type")),
                "title": v.get("title", ""),
                "n values": len(v.get("enum") or v.get("items", {}).get("enum") or []) or None,
                "default": str(v.get("default", "")),
                "examples": ", ".join(map(str, (v.get("enum") or v.get("items", {}).get("enum") or [])[:4]))}
                for k, v in props.items()]), hide_index=True, width="stretch")
            var_prop = next((k for k in props if k.endswith("variable")), None)
            if var_prop:
                allv = props[var_prop].get("enum") or props[var_prop].get("items", {}).get("enum") or []
                f = st.text_input("Filter variables", "", key="col_vfilt", placeholder="e.g. temperature, wind…")
                hits = [v for v in allv if f.lower() in v.lower()]
                st.caption(f"{len(hits)} / {len(allv)} variables")
                st.write(", ".join(f"`{v}`" for v in hits))
            _links = ei_table()
            if not _links.empty:
                mine = _links[_links["collection_id"] == cid]
                with st.expander(f"Applications served — EARSC services ({len(mine)})", expanded=bool(len(mine))):
                    if mine.empty:
                        st.caption("No link found for this collection.")
                    else:
                        st.dataframe(mine[["earsc_service", "link_type", "confidence", "path", "validated"]],
                                     hide_index=True, width="stretch")
                        st.caption("direct = the collection already is the information · enabling = input that needs "
                                   "processing. Proposed links, not validated unless stated.")
            st.button("Use this collection in the data tabs", key="col_use", on_click=_to_data_tabs, args=(cid,))
            if st.session_state.get("s_cid") == cid:
                st.caption("This collection is selected in *Search items*"
                           + (" and *ECMWF orders*." if st.session_state.get("o_cid") == cid else "."))


# ============================================================================
# Search items · data
# ============================================================================
def run_search(body=None, next_link=None):
    if next_link:
        if next_link.get("method", "GET").upper() == "POST":
            b = next_link.get("body", {})
            if next_link.get("merge"):
                b = {**st.session_state["search_body"], **b}
            return http("POST", next_link["href"], auth=True, json=b).json()
        return http("GET", next_link["href"], auth=True).json()
    return http("POST", f"{STAC}/search", auth=True, json=body).json()


with t_search:
    st.subheader("STAC item search (one collection per request)")
    st.session_state.setdefault("s_cid", st.session_state.get("cid") or "EO.ESA.DAT.SENTINEL-2.MSI.L2A")
    cid_s = st.text_input("Collection", key="s_cid")
    c1, c2, c3, c4 = st.columns(4)
    use_bbox = c1.checkbox("Use sidebar bbox", True, key="s_bbox")
    use_dt = c2.checkbox("Use sidebar period", True, key="s_dt")
    lim = c3.number_input("Items per page", 1, 200, 20, key="s_lim")
    sort = c4.selectbox("Sort", ["(none)", "-datetime", "datetime", "eo:cloud_cover"], key="s_sort")
    qtext = st.text_input("Free text `q` (optional)", "", key="s_q")

    query = {}
    try:
        qa = get_queryables(cid_s)
        with st.expander("Queryable filters", expanded=True):
            query = queryable_form(qa.get("properties", {}), set(), f"sq_{cid_s}",
                                   skip=("datetime", "bbox", "geometry", "id", "collection"))
    except Exception as e:
        st.caption(f"Queryables unavailable: {str(e)[:160]}")

    body = {"collections": [cid_s], "limit": int(lim)}
    if use_bbox:
        body["bbox"] = [west, south, east, north]
    if use_dt:
        body["datetime"] = f"{date0}T00:00:00Z/{date1}T23:59:59Z"
    if qtext:
        body["q"] = qtext
    if sort != "(none)":
        body["sortby"] = [{"field": sort.lstrip("-"), "direction": "desc" if sort.startswith("-") else "asc"}]
    if query:
        body["query"] = query
    with st.expander("Request"):
        st.code(json.dumps(body, indent=2), language="json")
        st.code(f"curl -X POST {STAC}/search -H 'Authorization: Bearer $TOKEN' "
                f"-H 'Content-Type: application/json' -d '{json.dumps(body)}'", language="bash")

    b1, b2 = st.columns(2)
    if b1.button("Search", type="primary", key="s_btn", disabled=not token()):
        try:
            t0 = time.perf_counter()
            st.session_state["search_res"] = run_search(body)
            st.session_state["search_body"] = body
            st.session_state["search_pages"] = [st.session_state["search_res"]]
            st.session_state["search_time"] = time.perf_counter() - t0
        except Exception as e:
            st.error(str(e))
    if not token():
        st.caption("Item search needs a token (sidebar).")

    sr = st.session_state.get("search_res")
    if sr:
        nxt = next((l for l in sr.get("links", []) if l.get("rel") == "next"), None)
        if nxt and b2.button("Load next page", key="s_next"):
            try:
                sr = run_search(next_link=nxt)
                st.session_state["search_res"] = sr
                st.session_state["search_pages"].append(sr)
                nxt = next((l for l in sr.get("links", []) if l.get("rel") == "next"), None)
            except Exception as e:
                st.error(str(e))
        feats = [f for p in st.session_state["search_pages"] for f in p.get("features", [])]
        st.caption(f"{len(feats)} items loaded over {len(st.session_state['search_pages'])} page(s) · "
                   f"numberMatched={sr.get('numberMatched')} · first page in "
                   f"{st.session_state.get('search_time', 0):.2f} s · next page: {'yes' if nxt else 'no'}")
        rows = []
        for f in feats:
            p = f.get("properties", {})
            size = sum((a.get("file:size") or 0) for a in f.get("assets", {}).values())
            rows.append({"id": f["id"], "datetime": p.get("datetime") or p.get("start_datetime"),
                         "cloud %": p.get("eo:cloud_cover"), "platform": p.get("platform"),
                         "order:status": p.get("order:status"), "assets": len(f.get("assets", {})),
                         "size": human(size) if size else ""})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        bbox_map(north, west, south, east, "map_items", features=feats, height=320)

        if feats:
            iid = st.selectbox("Item", [f["id"] for f in feats], key="s_item")
            item = next(f for f in feats if f["id"] == iid)
            with st.expander("Item properties"):
                st.json(item.get("properties", {}), expanded=False)
            assets = item.get("assets", {})
            if not assets:
                st.warning("No assets: this item is orderable — use the ECMWF orders tab.")
            else:
                st.dataframe(pd.DataFrame([{"key": k, "title": a.get("title"), "type": a.get("type"),
                                            "roles": ", ".join(a.get("roles", [])),
                                            "size": human(a.get("file:size")), "href": a.get("href")}
                                           for k, a in assets.items()]), hide_index=True, width="stretch")
                akey = st.selectbox("Asset", list(assets), key="s_asset")
                a = assets[akey]
                c1, c2, c3 = st.columns(3)
                if c1.button("HEAD (size, type)", key="s_head"):
                    try:
                        h = requests.head(a["href"], headers=auth_headers(), allow_redirects=True, timeout=60)
                        st.json({"status": h.status_code, "content-type": h.headers.get("content-type"),
                                 "content-length": human(int(h.headers.get("content-length", 0) or 0)),
                                 "accept-ranges": h.headers.get("accept-ranges")})
                    except Exception as e:
                        st.error(str(e))
                if c2.button("Download to local folder", key="s_dl"):
                    try:
                        path, n, d = download_to_disk(a["href"], dl_dir)
                        st.caption(f"{human(n)} in {d:.1f} s ({human(n / d if d else 0)}/s)")
                        st.session_state["s_file"] = path
                    except Exception as e:
                        st.error(str(e))
                is_zarr = ".zarr" in a["href"] or "zarr" in (a.get("type") or "")
                if c3.button("Open lazily (Zarr)", key="s_zarr", disabled=not is_zarr):
                    try:
                        ds = xr.open_dataset(a["href"], engine="zarr", chunks={},
                                             storage_options={"client_kwargs": {"headers": auth_headers()}})
                        st.text(str(ds))
                    except Exception as e:
                        st.error(str(e))
                if "thumbnail" in a.get("roles", []) or akey in ("thumbnail", "quicklook"):
                    try:
                        img = requests.get(a["href"], headers=auth_headers(), timeout=60)
                        if img.ok:
                            st.image(img.content, caption=akey, width=320)
                    except Exception:
                        pass
                if st.session_state.get("s_file"):
                    show_file(st.session_state["s_file"], "s_plot")


# ============================================================================
# ECMWF orders · data
# ============================================================================
with t_order:
    st.subheader("On-demand datasets: order → poll → download")
    st.session_state.setdefault("o_cid", st.session_state["cid"]
                                if str(st.session_state.get("cid") or "").startswith("EO.ECMWF")
                                else "EO.ECMWF.DAT.REANALYSIS_ERA5_SINGLE_LEVELS")
    cid_o = st.text_input("Collection", key="o_cid")
    dates = pd.date_range(date0, date1, freq="D")
    derived = {"year": sorted({f"{d.year}" for d in dates}),
               "month": sorted({f"{d.month:02d}" for d in dates}),
               "day": sorted({f"{d.day:02d}" for d in dates}),
               "time": hours}

    # Dynamic queryables: narrowing by the current selection updates the allowed values
    narrow = st.session_state.get(f"o_narrow_{cid_o}", ())
    try:
        qa = get_queryables(cid_o, narrow)
    except Exception as e:
        st.error(str(e))
        qa = {}
    props, req = qa.get("properties", {}), set(qa.get("required", []))
    if props:
        sel = queryable_form(props, req, f"oq_{cid_o}", skip=("datetime", "ecmwf:area", "area"),
                             derived=derived, ecmwf_style=True)
        area_key = next((k for k in props if k.endswith("area")), None)
        if area_key:
            sel[area_key] = {"eq": [north, west, south, east]}
        missing = [r for r in req if r not in sel]
        if missing:
            st.warning(f"Required queryables missing: {missing}")
        if len(derived["month"]) > 1:
            st.warning("ECMWF combines years × months × days: a multi-month period requests more days "
                       "than the exact range.")

        c1, c2 = st.columns([1, 3])
        if c1.button("Refresh queryables with this selection", key="o_narrow",
                     help="ECMWF queryables are dynamic: allowed values depend on what is already selected."):
            params = []
            for k, v in sel.items():
                if k == area_key:
                    continue
                for x in (v["eq"] if isinstance(v["eq"], list) else [v["eq"]]):
                    params.append((k, x))
            st.session_state[f"o_narrow_{cid_o}"] = tuple(params)
            st.rerun()
        if narrow and c2.button("Reset", key="o_reset"):
            st.session_state.pop(f"o_narrow_{cid_o}")
            st.rerun()

        strip = st.checkbox("Send order parameters without the `ecmwf:` prefix (as in the HDA docs)",
                            True, key="o_strip")
        order_body = {}
        for k, v in sel.items():
            val = v["eq"]
            if props.get(k, {}).get("type") == "string" and isinstance(val, list) and len(val) == 1:
                val = val[0]  # single-valued parameters (e.g. data_format) are sent as plain strings
            order_body[k.split(":", 1)[1] if strip and k.startswith("ecmwf:") else k] = val
        search_body = {"collections": [cid_o], "query": sel}
        with st.expander("Requests", expanded=False):
            st.markdown("Search (check the order is valid):")
            st.code(json.dumps(search_body, indent=2), language="json")
            st.markdown("Order body:")
            st.code(json.dumps(order_body, indent=2), language="json")

        b1, b2 = st.columns(2)
        if b1.button("Search (validate request)", key="o_search", disabled=not token()):
            try:
                r = http("POST", f"{STAC}/search", auth=True, json=search_body).json()
                fs = r.get("features", [])
                st.success(f"{len(fs)} item(s) · order:status = "
                           f"{[f.get('properties', {}).get('order:status') for f in fs]}")
                with st.expander("Response"):
                    st.json(r, expanded=False)
            except Exception as e:
                st.error(str(e))
        if b2.button("Submit order", type="primary", key="o_submit", disabled=not token()):
            try:
                col = get_collection(cid_o)
                link = next((l for l in col.get("links", []) if l.get("rel") == "retrieve"), {})
                r = http("POST", link.get("href", f"{STAC}/collections/{cid_o}/order"), auth=True, json=order_body)
                item = r.json()
                poll = next((l["href"] for l in item.get("links", []) if l.get("rel") == "self"),
                            r.headers.get("Location"))
                st.session_state["order"] = {"item": item, "poll": poll, "t0": time.time()}
            except Exception as e:
                st.error(str(e))
        if not token():
            st.caption("Orders need a token (sidebar).")

    o = st.session_state.get("order")
    if o:
        st.divider()
        st.markdown(f"**Order** `{o['item'].get('id', '')}` · poll URL: `{o['poll']}`")
        tmax = st.slider("Max wait (min)", 1, 120, 20, key="o_tmax")
        if st.button("Poll until ready", key="o_poll"):
            with st.status("Polling order…", expanded=True) as status:
                line = st.empty()
                t0 = time.time()
                while True:
                    item = http("GET", o["poll"], auth=True).json()
                    s = item.get("properties", {}).get("order:status")
                    line.write(f"{time.time() - o['t0']:5.0f} s since submission · status **{s}**")
                    if s in ("succeeded", "failed") or item.get("assets"):
                        break
                    if time.time() - t0 > tmax * 60:
                        break
                    time.sleep(5)
                o["item"] = item
                if s == "failed":
                    status.update(label="Order failed", state="error")
                    st.json(item, expanded=False)
                elif item.get("assets"):
                    status.update(label=f"Ready after {time.time() - o['t0']:.0f} s", state="complete")
                else:
                    status.update(label="Still processing — poll again later", state="running")
        assets = o["item"].get("assets", {})
        if assets:
            akey, a = next(iter(assets.items()))
            st.write(f"Asset `{akey}` · {a.get('type')} · {human(a.get('file:size'))}")
            if st.button("Download result", key="o_dl"):
                try:
                    path, n, d = download_to_disk(a["href"], dl_dir)
                    st.caption(f"{human(n)} in {d:.1f} s")
                    st.session_state["o_file"] = path
                except Exception as e:
                    st.error(str(e))
        if st.session_state.get("o_file"):
            show_file(st.session_state["o_file"], "o_plot")


# ============================================================================
# Prototypes on demand: from data to one ingredient of information, with a traceable method
# ============================================================================
HOW_LABEL = {"documented": (":green[**Documented method**]", "a published or official method, applied as written"),
             "choice": (":orange[**Choice**]", "a parameter or shortcut chosen by the tool, by the plan or by you"),
             "interpretation": (":red[**Interpretation, not validated**]", "a reading of the result that has not been checked"),
             "service": (":blue[**Existing service, not reprocessed**]", "the output of a service, used as delivered")}


def show_prototype(res):
    st.markdown(f"### {res['title']}")
    where = f"{res['place']}, " if res.get("place") else ""
    b = res["bbox"]
    st.caption(f"Generated on {res['computed']} for {where}longitudes {b[0]} to {b[2]}, latitudes {b[1]} to {b[3]}. "
               f"Data source: {'public copies of the data, not the DestinE API' if res['backend'] == 'public' else 'DestinE Data Lake'}.")
    st.markdown(f"**How far to trust it.** {res.get('trust', '')}")
    for w in res.get("warnings", []):
        st.warning(w)
    st.markdown("#### What you see")
    if res.get("image") and os.path.exists(res["image"]):
        st.image(res["image"])
    for t in res["see"]:
        st.write(t)
    st.dataframe(pd.DataFrame(res["figures"], columns=["Key figure", "Value"]), hide_index=True)
    st.markdown("#### How it was computed, step by step")
    tally = {}
    for x in res["steps"]:
        tally[x["how"]] = tally.get(x["how"], 0) + 1
    st.caption(f"Of {len(res['steps'])} steps: " + "; ".join(f"{n} {k}" for k, n in tally.items()) + ".")
    for i, x in enumerate(res["steps"], 1):
        line = f"{i}. {HOW_LABEL[x['how']][0]} — {x['t']}"
        if x.get("by"):
            line += f"  \n   *Set by {x['by']}.*"
        if x.get("note"):
            line += f"  \n   {x['note']}"
        if x.get("ref"):
            line += f"  \n   Source: [{x['ref']['t']}]({x['ref']['u']})"
        st.markdown(line)
    with st.expander("What the four labels mean"):
        for k, (lab, txt) in HOW_LABEL.items():
            st.markdown(f"- {lab}: {txt}")
    st.markdown("#### Data used")
    for i in res["inputs"]:
        st.markdown(f"**{i['what']}**  \n{i['used']}  \n{'Related' if i.get('rel') else 'Same'} data in the DestinE Data Lake: `{i['lake']}` (not used for this figure)"
                    + (f"  \n*{i['note']}*" if i.get("note") else ""))
    st.markdown("#### What is missing")
    for t in res["missing"]:
        st.markdown(f"- {t}")
    c1, c2 = st.columns(2)
    if res.get("image") and os.path.exists(res["image"]):
        c1.download_button("Save the figure", open(res["image"], "rb").read(), file_name=os.path.basename(res["image"]), mime="image/png", key="proto_dl_img")
    trace = {k: v for k, v in res.items() if k not in ("image",)}
    c2.download_button("Save the trace (JSON)", json.dumps(trace, indent=1, ensure_ascii=False), file_name=f"prototype_trace_{res['recipe']}.json", mime="application/json", key="proto_dl_trace")


with t_proto:
    import inspect
    import ei_proto

    st.subheader("Prototypes on demand: from data to one ingredient of information")
    st.caption("A prototype is generated when you ask for it, on the area and period of the sidebar. Each one states how every step was done "
               "(documented method, choice, interpretation, existing service), what you are looking at and what is missing. "
               "Load a plan saved by the navigator (sidebar), or describe the ingredient here.")
    plan0 = st.session_state.get("proto_plan") or {}
    c1, c2 = st.columns([2, 1])
    ingr = c1.text_input("Ingredient (in your own words)", key="proto_ingr", placeholder="tree canopy, slope of the terrain, solar radiation…")
    need = c2.text_input("Detail needed", key="proto_need", placeholder="1 m, 10 m, 1 km…")
    auto = plan0.get("recipe") or ei_proto.recipe_for(ingr, plan0.get("variable", ""), plan0.get("service", ""))
    keys = list(ei_proto.RECIPES)
    labels = {k: ei_proto.RECIPES[k]["title"] for k in keys}
    choice = st.selectbox("Recipe", ["(none)"] + keys, index=(keys.index(auto) + 1) if auto in keys else 0,
                          format_func=lambda k: "No recipe matches this ingredient" if k == "(none)" else labels[k], key=f"proto_recipe_{auto}")
    if choice == "(none)":
        st.info("No recipe exists yet for this ingredient, so nothing is computed rather than something invented. "
                "The recipes available today: " + "; ".join(labels.values()) + ".")
        d = plan0.get("draft")
        if d and plan0.get("ingredient", "") == ingr:
            NAT = {"named": ":blue[**Method named by Claude, reference to verify**]", "choice": ":orange[**Choice made by Claude**]",
                   "interpretation": ":red[**Claude's interpretation, not validated**]"}
            st.markdown(f"#### Draft method: {d.get('title', '')}")
            st.warning(f"Drafted by Claude in the navigator on {d.get('on', '')}. Nothing was computed and no reference was verified: "
                       "it is a starting point for a developer, not an executable recipe.")
            for i, x in enumerate(d.get("steps", []), 1):
                st.markdown(f"{i}. {NAT.get(x.get('how'), NAT['interpretation'])} — {x.get('t', '')}")
            if d.get("data"):
                st.markdown("**Data it would read:** " + ", ".join(f"`{x}`" for x in d["data"]))
            st.markdown("**What is missing**")
            for t in d.get("missing", []):
                st.markdown(f"- {t}")
    else:
        rc = ei_proto.RECIPES[choice]
        st.markdown("**What will be done**")
        for t, how in rc["outline"]:
            st.markdown(f"- {HOW_LABEL[how][0]} — {t}")
        params, set_by_user = dict(plan0.get("params") or {}), []
        if rc["needs_period"]:
            st.caption(f"Period used: {date0} to {date1} (sidebar). The least cloudy image of the period is kept.")
        if choice == "vegetation_index":
            lim = st.slider("Class limits of the index", 0.0, 0.9, tuple(params.get("class_limits", (0.2, 0.5))), 0.05, key="proto_lim")
            if list(lim) != list(params.get("class_limits", (0.2, 0.5))):
                set_by_user.append("class_limits")
            params["class_limits"] = list(lim)
        src = st.radio("Data source", ["Public copies of the data (tested)", "DestinE Data Lake (not available yet)"], horizontal=True, key="proto_src")
        if src.startswith("DestinE"):
            st.warning("Reading through the DestinE API is not written yet: the structure of what the API returns must first be observed with a real account. "
                       "Use the check below with your own token and send the report.")
        if st.button("Generate the prototype", type="primary", disabled=src.startswith("DestinE"), key="proto_go"):
            plan = {"prototype_plan": 1, "recipe": choice, "ingredient": ingr or plan0.get("ingredient", ""), "place": plan0.get("place", ""),
                    "bbox": [west, south, east, north], "need": need, "params": params, "set_by_user": set_by_user}
            if rc["needs_period"]:
                plan["start"], plan["end"] = str(date0), str(date1)
                if plan0 and (plan0.get("start") != plan["start"] or plan0.get("end") != plan["end"]):
                    set_by_user.append("start")
                elif not plan0:
                    set_by_user.append("start")
            box = st.empty()
            with st.spinner("Generating…"):
                res = ei_proto.run(plan, backend="public", workdir=os.path.join(dl_dir, "prototypes"), progress=lambda t: box.caption(t))
            box.empty()
            st.session_state["proto_res"] = res
        res = st.session_state.get("proto_res")
        if res and res.get("recipe") == choice:
            st.divider()
            if res.get("ok"):
                show_prototype(res)
                with st.expander("The processing code that ran"):
                    st.code(inspect.getsource(ei_proto.RUNNERS[choice]), language="python")
            else:
                st.error(f"The prototype could not be generated: {res.get('error')}")
    with st.expander("Check what DestinE returns for these collections (needs your token; nothing is downloaded)"):
        st.caption("This looks at one item of each collection the recipes need and lists its asset names and properties. "
                   "The report is what is needed to write the DestinE reading code from facts.")
        if st.button("Run the DestinE check", key="proto_probe", disabled=not token()):
            rep = ei_proto.probe_destine(token(), [west, south, east, north], str(date0), str(date1))
            st.session_state["proto_probe_rep"] = rep
        if not token():
            st.caption("Get a token in the sidebar first.")
        if st.session_state.get("proto_probe_rep"):
            st.json(st.session_state["proto_probe_rep"], expanded=False)
            st.download_button("Save the report", json.dumps(st.session_state["proto_probe_rep"], indent=1), file_name="destine_check.json", mime="application/json", key="proto_probe_dl")
