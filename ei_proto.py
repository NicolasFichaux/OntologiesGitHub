"""
On-demand prototypes: turn data into one ingredient of information, with a traceable method.

A prototype is generated when asked, for the area and period of the request. Each run returns
  - a figure and key figures, with a plain explanation of what is shown;
  - every processing step with its nature:
        documented      a published or official method, applied as written (with its source)
        choice          a parameter or shortcut chosen by the tool, by the plan or by the user
        interpretation  a reading of the result that has NOT been validated
        service         the output of an existing service, not reprocessed
  - the data actually used, the equivalent collection of the DestinE Data Lake, and what is missing.

Data sources
  "public"   open copies of the same datasets (Sentinel-2 L2A and Copernicus DEM on AWS, PVGIS). Tested.
  "destine"  the DestinE Data Lake through the HDA API. Not implemented yet: run probe_destine() with your own
             token and send the report, so that the access code is written from facts and not from guesses.

Written by Claude (4 October 2026). The recipes are proposals: read the "interpretation" steps before using a result.
"""
import datetime as dt
import json
import math
import os
import re

import numpy as np
import requests

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
PVGIS = "https://re.jrc.ec.europa.eu/api/v5_3/MRcalc"
DEM_BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"
HDA_STAC = "https://hda.data.destination-earth.eu/stac/v2"

# sources seen and checked on 4 October 2026
REF = {
    "esa_l2a": {"t": "ESA, Sentinel-2 MSI technical guide, Level-2A algorithms and products",
                "u": "https://sentinel.esa.int/web/sentinel/technical-guides/sentinel-2-msi/level-2a-algorithms-products"},
    "tucker": {"t": "Tucker, C. J. (1979). Red and photographic infrared linear combinations for monitoring vegetation. "
                    "Remote Sensing of Environment 8(2), 127–150", "u": "https://ntrs.nasa.gov/citations/19790049033"},
    "horn": {"t": "Horn, B. K. P. (1981). Hill shading and the reflectance map. Proceedings of the IEEE 69(1), 14–47",
             "u": "https://people.csail.mit.edu//bkph/papers/Hill-Shading.pdf"},
    "awsdem": {"t": "Registry of Open Data on AWS, Copernicus Digital Elevation Model",
               "u": "https://registry.opendata.aws/copernicus-dem/"},
    "usgs_st": {"t": "USGS, Landsat Collection 2 Surface Temperature (scaling factor)",
                "u": "https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature"},
}
PLANETARY = "https://planetarycomputer.microsoft.com/api"

# What each recipe can stand for. Shared with the navigator page, which uses the same rules to propose a recipe.
RECIPES = {
    "vegetation_index": {
        "title": "Vegetation greenness (NDVI) from one Sentinel-2 image",
        "res_m": 10, "needs_period": True, "lake": ["EO.ESA.DAT.SENTINEL-2.MSI.L2A"],
        "vars": ["Normalised Difference Vegetation Index (NDVI)", "Fraction of vegetated land", "Leaf Area Index (LAI)", "Vegetation type"],
        "svcs": ["Monitor urban green & blue areas", "Monitor vegetation encroachment"],
        "rx": r"canop|\btrees?\b|arbre|v[eé]g[eé]t|vegetation|\bNDVI\b|green (cover|space)|espaces? verts?|couvert v[eé]g",
        "outline": [["Choose the least cloudy Sentinel-2 image over your area in your period", "choice"],
                    ["Read the red and near-infrared bands at 10 m and convert them to surface reflectance", "documented"],
                    ["Compute NDVI = (near infrared − red) / (near infrared + red)", "documented"],
                    ["Mask the pixels that the product flags as cloud or cloud shadow", "choice"],
                    ["Group the index into three classes for reading", "choice"],
                    ["Read high values as vegetation cover or tree canopy", "interpretation"]],
        "gaps": ["Greenness is not tree canopy: grass and crops are green too.", "One image, one date.", "No check against ground truth."]},
    "terrain_slope": {
        "title": "Height, slope and aspect of the surface from the Copernicus DEM (30 m)",
        "res_m": 30, "needs_period": False, "lake": ["EO.DEM.DAT.COP-DEM_GLO-30-DGED"],
        "vars": ["Land surface topography"], "svcs": ["Baseline mapping", "Map line of sight visibility (land surface)"],
        "rx": r"elevation|[eé]l[eé]vation|altitude|relief|terrain|topograph|slope|pente|aspect|orientation|surface model|mod[eè]le num[eé]rique|\bDEM\b|\bDSM\b|\bDTM\b|\bMNT\b|\bMNS\b",
        "outline": [["Read the heights of the Copernicus surface model over your area", "documented"],
                    ["Convert the grid spacing from degrees to metres at your latitude", "choice"],
                    ["Compute slope and aspect with Horn's method (8 neighbours)", "documented"],
                    ["Group the slope into classes for reading", "choice"],
                    ["Read terrain slope and aspect as roof tilt and orientation", "interpretation"]],
        "gaps": ["A 30 m cell blends roofs, streets and trees.", "No shading computed.", "Surface model: ground, buildings and vegetation are not separated."]},
    "surface_temperature": {
        "title": "Temperature of the surface from one Landsat image",
        "res_m": 30, "needs_period": True, "lake": ["EO.NASA.DAT.LANDSAT.C2_L2"],
        "vars": ["Land surface temperature"], "svcs": [],
        "rx": r"temp[eé]rature|chaleur|\bheat|overheat|surchauffe|thermal|thermique|\bLST\b|fra[iî]cheur|cool",
        "not": r"\bsea\b|\bmer\b|oc[eé]an|marine|\bair\b",
        "outline": [["Choose the least cloudy Landsat 8 or 9 image over your area in your period", "choice"],
                    ["Read the surface temperature band of the Level-2 product", "documented"],
                    ["Convert it to degrees Celsius with the official scale factor and offset", "documented"],
                    ["Express each pixel as a difference from the median of the area", "choice"],
                    ["Read the hottest surfaces as places where people overheat", "interpretation"]],
        "gaps": ["Surface temperature is not air temperature.", "One morning overpass, one date.", "No pixel-level cloud mask."]},
    "solar_monthly": {
        "title": "Solar energy received at one point, month by month (PVGIS)",
        "res_m": 5000, "needs_period": False, "lake": ["EO.EUM.DAT.MSG.SEVIRI-SARAH-CDR-V003", "EO.ECMWF.DAT.CAMS_SOLAR_RADIATION_TIMESERIES"],
        "vars": ["Downward short-wave irradiance at Earth surface"],
        "svcs": ["Map & monitor solar energy (solar farms)", "Forecasting sunlight exposure"],
        "rx": r"irradia|solar radiation|rayonnement|ensoleillement|sunlight|insolation|\bGHI\b|sunshine",
        "outline": [["Ask the PVGIS service for the monthly irradiation at the centre of your area", "service"],
                    ["Average each month over the years available; keep the lowest and highest year", "choice"],
                    ["Add the months into annual totals", "choice"],
                    ["Take this single point as the value for the whole area", "interpretation"]],
        "gaps": ["One point, not a map.", "No roof tilt, orientation or shading.", "No conversion into electricity."]},
}


def recipe_for(name="", variable="", service=""):
    """Same rule as the page: OSCAR variable first, then the words of the ingredient, then its EARSC service."""
    for k, r in RECIPES.items():
        if variable and variable in r["vars"]:
            return k
    for k, r in RECIPES.items():
        if name and re.search(r["rx"], name, re.I) and not (r.get("not") and re.search(r["not"], name, re.I)):
            return k
    for k, r in RECIPES.items():
        if service and service in r["svcs"]:
            return k
    return None


# ---------------------------------------------------------------------------------------------- helpers
def _env():
    import rasterio
    opts = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "AWS_NO_SIGN_REQUEST": "YES", "GDAL_HTTP_TIMEOUT": "90",
            "GDAL_HTTP_MAX_RETRY": "2", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.jp2"}
    if os.environ.get("EI_PROTO_UNSAFE_SSL") == "1":       # only for networks that re-sign TLS traffic (test sandboxes)
        opts["GDAL_HTTP_UNSAFESSL"] = "YES"
    return rasterio.Env(**opts)


def _http(method, url, tries=3, **kw):
    """requests with a few retries: public catalogues answer 502/504 or time out now and then."""
    import time
    last = None
    for i in range(tries):
        try:
            r = requests.request(method, url, **kw)
            if r.status_code in (429, 500, 502, 503, 504) and i < tries - 1:
                last = RuntimeError(f"{r.status_code} from {url.split('?')[0]}")
                time.sleep(2 + 3 * i)
                continue
            return r
        except (requests.Timeout, requests.ConnectionError) as ex:
            last = ex
            time.sleep(2 + 3 * i)
    raise RuntimeError(f"The data service did not answer after {tries} attempts ({last}). Try again in a minute.")


def _step(text, how, ref=None, note="", by=""):
    s = {"t": text, "how": how}
    if ref:
        s["ref"] = REF[ref] if isinstance(ref, str) else ref
    if note:
        s["note"] = note
    if by:
        s["by"] = by
    return s


def _fmt_m(m):
    return f"{m:.0f} m" if m < 1000 else (f"{m / 1000:.1f} km" if m < 10000 else f"{m / 1000:.0f} km")


def _need_m(text):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(km|kilom[eè]tres?|m|m[eè]t(?:er|re)s?)(?![a-zà-ÿ])", str(text or ""), re.I)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return v * 1000 if m.group(2).lower().startswith("k") else v


def _nice_km(width_km):
    for v in (0.5, 1, 2, 5, 10, 20, 50, 100, 200):
        if v >= width_km / 4.5:
            return v
    return 500


def _check_bbox(bbox):
    w, s, e, n = [float(x) for x in bbox]
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError("The area is not a valid box (west, south, east, north in degrees).")
    return w, s, e, n


def _box_km(bbox):
    w, s, e, n = bbox
    lat = (s + n) / 2
    return (e - w) * 111.32 * math.cos(math.radians(lat)), (n - s) * 111.32


def _horn(dem, dx, dy):
    """Slope (degrees) and aspect (compass bearing of the downslope direction) after Horn (1981)."""
    p = np.pad(dem, 1, mode="edge")
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * dx)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * dy)
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    aspect = (np.degrees(np.arctan2(dzdy, -dzdx)) + 360) % 360
    aspect = np.where(aspect > 90, 450 - aspect, 90 - aspect)
    return slope, aspect


def _result(recipe, plan, bbox, backend):
    return {"ok": True, "recipe": recipe, "title": RECIPES[recipe]["title"], "ingredient": plan.get("ingredient", ""),
            "place": plan.get("place", ""), "bbox": list(bbox), "backend": backend,
            "computed": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "figures": [], "see": [], "steps": [], "inputs": [], "missing": [], "warnings": [], "image": None}


# ---------------------------------------------------------------------------------------------- recipe 1
def vegetation_index(plan, backend="public", workdir=".", progress=None):
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    say = progress or (lambda t: None)
    bbox = _check_bbox(plan["bbox"])
    res = _result("vegetation_index", plan, bbox, backend)
    p = plan.get("params") or {}
    who = lambda key: "you" if key in (plan.get("set_by_user") or []) else ("the plan" if key in p or key in plan else "the tool's default")
    today = dt.date.today()
    end = plan.get("end") or today.isoformat()
    start = plan.get("start") or (dt.date.fromisoformat(end) - dt.timedelta(days=60)).isoformat()
    max_cloud = float(p.get("max_cloud", 30))
    lo, hi = [float(x) for x in p.get("class_limits", [0.2, 0.5])]
    max_px = int(p.get("max_pixels", 2600))

    say("Searching Sentinel-2 images…")
    body = {"collections": ["sentinel-2-l2a"], "bbox": list(bbox), "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
            "limit": 100, "query": {"eo:cloud_cover": {"lt": max_cloud}}}
    r = _http("POST", f"{EARTH_SEARCH}/search", json=body, timeout=90)
    r.raise_for_status()
    feats = r.json().get("features", [])
    if not feats:
        raise RuntimeError(f"No Sentinel-2 image with less than {max_cloud:.0f} % cloud between {start} and {end} over this area. Widen the period.")

    def cover(f):                                    # share of the requested box inside the image's bounding box
        b = f.get("bbox") or [0, 0, 0, 0]
        iw = max(0, min(b[2], bbox[2]) - max(b[0], bbox[0])); ih = max(0, min(b[3], bbox[3]) - max(b[1], bbox[1]))
        return iw * ih / ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
    cands = sorted([f for f in feats if cover(f) >= 0.5] or feats, key=lambda f: f["properties"].get("eo:cloud_cover", 100))

    best = None
    for f in cands[:5]:
        say(f"Reading {f['id']}…")
        with _env():
            arr = {}
            for name in ("red", "nir", "scl"):
                with rasterio.open(f["assets"][name]["href"]) as ds:
                    b = transform_bounds("EPSG:4326", ds.crs, *bbox, densify_pts=21)
                    win = from_bounds(*b, transform=ds.transform)
                    h, w = int(round(win.height)), int(round(win.width))
                    if name != "scl":
                        k = max(1.0, max(h, w) / max_px)
                        if k == 1.0:                     # small box: read the native pixels exactly, no resampling
                            win = win.round_offsets().round_lengths()
                            h, w = int(win.height), int(win.width)
                            b = rasterio.windows.bounds(win, ds.transform)
                        shape = (max(1, int(round(h / k))), max(1, int(round(w / k))))
                        meta = {"crs": str(ds.crs), "bounds": b, "pixel_m": ds.res[0] * k, "native_m": ds.res[0], "shape": shape}
                    elif meta["pixel_m"] == meta["native_m"]:
                        win = from_bounds(*meta["bounds"], transform=ds.transform)
                    arr[name] = ds.read(1, window=win, out_shape=shape, boundless=True, fill_value=0,
                                        resampling=rasterio.enums.Resampling.average if name != "scl" else rasterio.enums.Resampling.nearest)
        valid = (arr["red"] > 0) & (arr["nir"] > 0)
        frac = float(valid.mean())
        if best is None or frac > best[0] + 0.05:
            best = (frac, f, arr, meta, valid)
        if frac >= 0.9:                      # the least cloudy image that covers at least 90 % of the box is kept
            break
    frac, f, arr, meta, valid = best
    props = f["properties"]
    date = props["datetime"][:10]
    if frac < 0.05:
        raise RuntimeError("The images found do not cover this area. Check the box.")

    # digital numbers -> surface reflectance (offset of -1000 since processing baseline 04.00)
    baseline = str(props.get("s2:processing_baseline", ""))
    declared = props.get("earthsearch:boa_offset_applied")
    red_p1 = float(np.percentile(arr["red"][valid], 1))
    newer = baseline >= "04.00" if baseline else date >= "2022-01-25"
    if not newer:
        offset, why = 0, f"Processing baseline {baseline or 'before 04.00'}: no offset in this product."
    elif declared is True or (declared is None and red_p1 < 700):
        offset, why = 0, (f"This public copy declares that the offset is already removed. Checked on the data: 1 % of the red values are below {red_p1:.0f}, "
                          "which could not happen with the offset still in. A product downloaded from DestinE still carries it: subtract 1000 first.")
    else:
        offset, why = -1000, f"Offset of −1000 applied (processing baseline {baseline}); 1 % of the red values are below {red_p1:.0f} before correction."
    red = (arr["red"].astype("float32") + offset) / 10000.0
    nir = (arr["nir"].astype("float32") + offset) / 10000.0
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = np.where(valid & ((nir + red) != 0), (nir - red) / (nir + red), np.nan)
    scl = arr["scl"]
    cloudy = np.isin(scl, (3, 8, 9, 10))
    cloud_pct = float(cloudy[valid].mean() * 100) if valid.any() else 0.0
    masked = cloud_pct >= 0.5
    if masked:
        ndvi = np.where(cloudy, np.nan, ndvi)
    v = ndvi[np.isfinite(ndvi)]
    if v.size == 0:
        raise RuntimeError("Every pixel of the area is cloudy or empty in the images found. Widen the period.")
    shares = [float((v < lo).mean() * 100), float(((v >= lo) & (v < hi)).mean() * 100), float((v >= hi).mean() * 100)]
    water = float((v < 0).mean() * 100)
    wkm, hkm = (meta["bounds"][2] - meta["bounds"][0]) / 1000, (meta["bounds"][3] - meta["bounds"][1]) / 1000

    say("Drawing the map…")
    cmap = LinearSegmentedColormap.from_list("ndvi", [(0, "#3b6ea5"), (0.25, "#d9c9a8"), (0.45, "#efe6c8"), (0.6, "#b5d389"), (0.8, "#4f9d4a"), (1, "#14561f")])
    cmap.set_bad("#bbbbbb")
    b = meta["bounds"]
    fw = 7.2; fh = max(3.5, min(9.0, fw * hkm / max(wkm, 1e-6) * 0.92))
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=120)
    im = ax.imshow(ndvi, cmap=cmap, vmin=-0.2, vmax=0.9, extent=[b[0], b[2], b[1], b[3]], interpolation="nearest")
    L = _nice_km(wkm) * 1000
    x0, y0 = b[0] + (b[2] - b[0]) * 0.04, b[1] + (b[3] - b[1]) * 0.05
    ax.plot([x0, x0 + L], [y0, y0], color="black", lw=3)
    ax.text(x0 + L / 2, y0 + (b[3] - b[1]) * 0.018, f"{L / 1000:g} km", ha="center", fontsize=9, bbox=dict(fc="white", ec="none", alpha=.8, pad=1))
    ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02).set_label("NDVI (no unit)")
    fig.tight_layout()
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, f"prototype_vegetation_{date}.png")
    fig.savefig(path, dpi=120); plt.close(fig)

    res["image"] = path
    res["figures"] = [["Image used", f"{f['id']}, acquired on {date}"],
                      ["Area computed", f"{wkm:.1f} km by {hkm:.1f} km, {ndvi.shape[1]} by {ndvi.shape[0]} pixels of {meta['pixel_m']:.0f} m"],
                      ["Mean index", f"{float(np.nanmean(ndvi)):.2f}"],
                      [f"Index of {hi:g} and above", f"{shares[2]:.1f} % of the area"], [f"Index from {lo:g} to {hi:g}", f"{shares[1]:.1f} %"],
                      [f"Index below {lo:g}", f"{shares[0]:.1f} %"],
                      ["Cloud or cloud shadow, as flagged in the product", f"{cloud_pct:.1f} %" + (" (masked, grey on the map)" if masked else "")],
                      ["Part of the box covered by the image", f"{frac * 100:.0f} %"]]
    res["see"] = [f"Each pixel covers {meta['pixel_m']:.0f} m by {meta['pixel_m']:.0f} m. Dark green (index above about 0.6) is dense, active vegetation: woods, hedges, parks, growing crops. "
                  "Pale beige (around 0.2) is built-up land, bare soil or harvested fields. Blue (below 0) is usually open water." + (" Grey is cloud, cloud shadow or missing data." if masked or frac < 0.99 else ""),
                  f"On {date}, {shares[2]:.0f} % of the area has an index of {hi:g} or more, {shares[1]:.0f} % lies between {lo:g} and {hi:g}, and {shares[0]:.0f} % is below {lo:g}"
                  + (f", of which {water:.1f} % is negative (water)." if water >= 0.1 else ".")]
    res["trust"] = "The index is a documented standard, applied as published. Reading it as vegetation cover or tree canopy is an interpretation and has not been validated."
    res["steps"] = [
        _step(f"Choose the image: the least cloudy acquisition covering the box between {start} and {end} (less than {max_cloud:.0f} % cloud over the tile). Kept: {date}, {props.get('eo:cloud_cover', 0):.1f} % cloud.",
              "choice", note="A single date, not a seasonal or multi-year average.", by=who("start")),
        _step(f"Read the digital numbers of bands B04 (red) and B08 (near infrared) over the box" + (f", averaged from {meta['native_m']:.0f} m to {meta['pixel_m']:.0f} m because the box is large." if meta["pixel_m"] > meta["native_m"] + 0.5 else f" at their native {meta['native_m']:.0f} m.") + " Zero means no data.",
              "documented" if meta["pixel_m"] <= meta["native_m"] + 0.5 else "choice", ref="esa_l2a"),
        _step("Convert to surface reflectance: (digital number + offset) / 10 000, the offset being −1000 since processing baseline 04.00 (25 January 2022).", "documented", ref="esa_l2a", note=why),
        _step("Compute the index: NDVI = (B08 − B04) / (B08 + B04).", "documented", ref="tucker"),
        _step((f"Mask the pixels that the scene classification of the product flags as cloud or cloud shadow ({cloud_pct:.1f} % of the box)." if masked
               else f"No cloud mask applied: the scene classification of the product flags {cloud_pct:.1f} % of the box as cloud or cloud shadow."), "choice",
              note="The classification comes with the product; using it as a mask above 0.5 % is the tool's rule.", by="the tool's default"),
        _step(f"Colour scale from −0.2 to 0.9 and three classes (below {lo:g}, {lo:g} to {hi:g}, {hi:g} and above).", "choice",
              note="The class limits are round numbers chosen for reading the map, not calibrated thresholds.", by=who("class_limits")),
        _step(f"Reading “{hi:g} and above” as vegetation cover or tree canopy.", "interpretation",
              note="Not validated. Irrigated crops, lawns and trees can all exceed this value: the index measures greenness, not trees.")]
    res["inputs"] = [{"what": "Surface reflectance, red and near-infrared bands (B04, B08), 10 m",
                      "used": f"Sentinel-2 Level-2A, image {f['id']} ({props.get('s2:product_uri', '').replace('.SAFE', '') or 'product name not given'}), read from the public copy on AWS through the Earth Search catalogue.",
                      "lake": "EO.ESA.DAT.SENTINEL-2.MSI.L2A"}]
    need = _need_m(plan.get("need"))
    res["missing"] = ["Trees are not separated from grass and crops. A canopy layer needs height information (airborne LiDAR) or a classification trained on reference data.",
                      "One date only: no check against another season or another year.",
                      "No comparison with ground truth or with a reference product."]
    if need and need * 3 < meta["pixel_m"]:
        res["warnings"].append(f"You asked for a detail of about {_fmt_m(need)}; this prototype resolves {_fmt_m(meta['pixel_m'])}. It shows the principle, not the answer.")
        res["missing"].insert(1, f"The detail you need ({_fmt_m(need)}): a {meta['pixel_m']:.0f} m pixel does not resolve it.")
    if frac < 0.99:
        res["missing"].append(f"Part of the box ({(1 - frac) * 100:.0f} %) lies outside the image used: a second image would be needed to complete it.")
    res["missing"].append("Read from a public copy of the data, not through the DestinE API.")
    res["stats"] = {"date": date, "mean": float(np.nanmean(ndvi)), "shares": shares, "cloud_pct": cloud_pct, "coverage": frac, "pixel_m": meta["pixel_m"], "offset": offset, "red_p1": red_p1}
    return res


# ---------------------------------------------------------------------------------------------- recipe 2
def terrain_slope(plan, backend="public", workdir=".", progress=None):
    import rasterio
    from rasterio.merge import merge
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap

    say = progress or (lambda t: None)
    bbox = _check_bbox(plan["bbox"])
    res = _result("terrain_slope", plan, bbox, backend)
    p = plan.get("params") or {}
    limits = [float(x) for x in p.get("slope_classes", [2, 5, 10, 15])]
    w, s, e, n = bbox
    if (e - w) > 6 or (n - s) > 6:
        raise ValueError("The area is too large for this prototype (more than 6 degrees). Reduce the box.")
    names = []
    for la in range(math.floor(s), math.floor(n - 1e-9) + 1):
        for lo in range(math.floor(w), math.floor(e - 1e-9) + 1):
            t = f"Copernicus_DSM_COG_10_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00_DEM"
            names.append(t)
    say("Reading the elevation model…")
    opened, used = [], []
    with _env():
        for t in names:
            try:
                opened.append(rasterio.open(f"{DEM_BUCKET}/{t}/{t}.tif")); used.append(t)
            except Exception:
                continue                               # no tile: open sea, or a tile not released to the public
        if not opened:
            raise RuntimeError("No Copernicus DEM tile is available for this area (open sea, or tiles not released to the public).")
        native = opened[0].res
        max_px = int(p.get("max_pixels", 2400))
        k = max(1.0, max((e - w) / native[0], (n - s) / native[1]) / max_px)      # large box: average the heights to keep the grid manageable
        if k > 1.0:
            dem, tr = merge(opened, bounds=bbox, nodata=np.nan, dtype="float32", res=(native[0] * k, native[1] * k), resampling=rasterio.enums.Resampling.average)
        else:
            dem, tr = merge(opened, bounds=bbox, nodata=np.nan, dtype="float32")
        for ds in opened:
            ds.close()
    dem = dem[0].astype("float64")
    hole = ~np.isfinite(dem)
    if hole.all():
        raise RuntimeError("The elevation model is empty over this area.")
    dem_f = np.where(hole, np.nanmin(dem), dem)
    lat0 = (s + n) / 2
    dy = abs(tr.e) * 111320.0
    dx = abs(tr.a) * 111320.0 * math.cos(math.radians(lat0))
    slope, aspect = _horn(dem_f, dx, dy)
    slope[hole] = np.nan
    v = slope[np.isfinite(slope)]
    flat = slope < limits[0]
    sloping = np.isfinite(slope) & ~flat
    sect = {"north": (aspect >= 315) | (aspect < 45), "east": (aspect >= 45) & (aspect < 135), "south": (aspect >= 135) & (aspect < 225), "west": (aspect >= 225) & (aspect < 315)}
    asp = {k: float((m & sloping).sum() / max(1, sloping.sum()) * 100) for k, m in sect.items()}
    edges = [0] + limits + [90]
    share = [float(((v >= a) & (v < b)).mean() * 100) for a, b in zip(edges[:-1], edges[1:])]

    say("Drawing the maps…")
    cols = ["#f3f0e6", "#d8e2b8", "#f0c060", "#d9772b", "#8c2d04"][:len(edges) - 1]
    fig, axs = plt.subplots(1, 2, figsize=(9.6, 4.9), dpi=120)
    ext = [w, e, s, n]; ar = 1 / math.cos(math.radians(lat0))
    im0 = axs[0].imshow(dem, cmap="terrain", extent=ext, aspect=ar); axs[0].set_title("Elevation (m)", fontsize=10)
    fig.colorbar(im0, ax=axs[0], fraction=0.046, pad=0.02)
    im1 = axs[1].imshow(slope, cmap=ListedColormap(cols), norm=BoundaryNorm(edges, len(cols)), extent=ext, aspect=ar); axs[1].set_title("Slope (degrees)", fontsize=10)
    fig.colorbar(im1, ax=axs[1], fraction=0.046, pad=0.02, ticks=edges[:-1])
    for ax in axs:
        ax.tick_params(labelsize=7); ax.locator_params(nbins=4)
    fig.tight_layout()
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, "prototype_terrain.png")
    fig.savefig(path, dpi=120); plt.close(fig)

    emin, emax, emed = float(np.nanmin(dem)), float(np.nanmax(dem)), float(np.nanmedian(dem))
    res["image"] = path
    res["figures"] = [["Tiles used", ", ".join(used)], ["Grid cell at this latitude", f"{dx:.1f} m east-west by {dy:.1f} m north-south"],
                      ["Elevation", f"{emin:.0f} to {emax:.0f} m, median {emed:.0f} m"],
                      ["Slope", f"median {float(np.median(v)):.1f}°, 90 % of cells below {float(np.percentile(v, 90)):.1f}°"],
                      ["Share of the box by slope", "; ".join(f"{a:g} to {b:g}°: {x:.1f} %" if b < 90 else f"above {a:g}°: {x:.1f} %" for a, b, x in zip(edges[:-1], edges[1:], share))],
                      [f"Sloping land ({limits[0]:g}° and more) by facing direction", "; ".join(f"{k} {x:.1f} %" for k, x in asp.items())]]
    res["see"] = [f"Left, elevation: from {emin:.0f} m (blue) to {emax:.0f} m (brown to white); half of the box lies below {emed:.0f} m.",
                  f"Right, slope: {share[0]:.0f} % of the box is nearly flat (below {limits[0]:g}°, palest colour); {sum(share[3:]):.1f} % is steeper than {limits[2]:g}° (darkest colours)."
                  + (" Thin dark lines usually follow river banks, terrace edges and hillsides." if share[0] > 30 else ""),
                  "This model describes the surface, buildings and trees included, not the bare ground: in towns, small isolated spots are buildings or embankments."]
    res["trust"] = ("Slope and aspect follow a documented method, re-implemented in this tool and checked on tilted planes of known slope and orientation. "
                    "Reading 30 m terrain as roof tilt or orientation is not valid.")
    res["steps"] = [
        _step(f"Read the heights over the box ({dem.shape[1]} by {dem.shape[0]} cells) from the Copernicus DEM GLO-30. The model is a surface model: it includes buildings, infrastructure and vegetation.", "documented", ref="awsdem"),
        *([_step(f"Average the heights to cells of about {dy:.0f} m, because the box is large.", "choice", note="Slopes computed on averaged heights are gentler than on the native 30 m grid.", by="the tool's default")] if k > 1.0 else []),
        _step(f"Convert the grid spacing from degrees to metres: {dy:.1f} m north-south and {dx:.1f} m east-west at {lat0:.1f}° of latitude (111.32 km per degree of latitude, longitude scaled by the cosine of the latitude).",
              "choice", note="A flat approximation over the box. Reprojecting to a metric grid would be more rigorous.", by="the tool's default"),
        _step("Slope and aspect with Horn's method: weighted differences over the 8 neighbours of each cell.", "documented", ref="horn",
              note="Re-implemented from the published formula and checked on five tilted planes of known slope and orientation: exact. Not cross-checked against GDAL or QGIS."),
        _step("Slope classes at " + ", ".join(f"{x:g}" for x in limits) + "° and the two colour scales.", "choice", by="the plan" if "slope_classes" in p else "the tool's default"),
        _step("Using terrain slope and aspect as a stand-in for roof tilt and orientation.", "interpretation", note="Not valid. A 30 m cell blends several roofs, streets and trees into one height.")]
    res["inputs"] = [{"what": "Height of the surface, 1 arc-second grid (about 30 m)", "used": "Copernicus DEM GLO-30, 2021 release, read from the public copy on AWS Open Data.", "lake": "EO.DEM.DAT.COP-DEM_GLO-30-DGED"}]
    need = _need_m(plan.get("need"))
    res["missing"] = ["The shading itself: sun path through the year and shadows cast by neighbouring buildings and trees are not computed.",
                      "A separation between ground, buildings and vegetation: the model gives one blended surface."]
    if need and need * 3 < dy:
        res["warnings"].append(f"You asked for a detail of about {_fmt_m(need)}; this prototype resolves about {dy:.0f} m. It shows the principle, not the answer.")
        res["missing"].insert(0, f"A surface model at about {_fmt_m(need)}, for instance from an airborne LiDAR survey where one exists.")
    if hole.any():
        res["missing"].append(f"{hole.mean() * 100:.0f} % of the box has no height (sea, or tiles not released).")
    res["missing"].append("Read from a public copy of the data, not through the DestinE API.")
    res["stats"] = {"elev": [emin, emax, emed], "slope_median": float(np.median(v)), "share": share, "aspect": asp, "cell_m": [dx, dy]}
    return res


# ---------------------------------------------------------------------------------------------- recipe 3
def solar_monthly(plan, backend="public", workdir=".", progress=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    say = progress or (lambda t: None)
    bbox = _check_bbox(plan["bbox"])
    res = _result("solar_monthly", plan, bbox, backend)
    lat, lon = round((bbox[1] + bbox[3]) / 2, 4), round((bbox[0] + bbox[2]) / 2, 4)
    say("Asking PVGIS…")
    r = _http("GET", PVGIS, params={"lat": lat, "lon": lon, "horirrad": 1, "outputformat": "json"}, timeout=90)
    if r.status_code != 200:
        try:
            msg = r.json().get("message", "")
        except Exception:
            msg = r.text[:200]
        raise RuntimeError(f"PVGIS has no data for the centre of this area ({lat}, {lon}): {msg or 'request refused'}")
    pv = r.json()
    rows = pv["outputs"]["monthly"]
    years = sorted({x["year"] for x in rows})
    tab = np.array([[next(x["H(h)_m"] for x in rows if x["year"] == y and x["month"] == m) for m in range(1, 13)] for y in years])
    mean, lo_, hi_ = tab.mean(0), tab.min(0), tab.max(0)
    annual = tab.sum(1)
    db = pv["inputs"]["meteo_data"]["radiation_db"]
    M = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=120)
    ax.bar(M, mean, color="#e0a030", yerr=[mean - lo_, hi_ - mean], capsize=3, ecolor="#555", error_kw={"lw": 1})
    ax.set_ylabel("kWh per m² per month"); ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(f"Global irradiation on a horizontal plane, {years[0]} to {years[-1]}: mean, lowest and highest year", fontsize=9)
    fig.tight_layout()
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, "prototype_solar.png")
    fig.savefig(path, dpi=120); plt.close(fig)
    top, low = int(np.argmax(mean)), int(np.argmin(mean))
    url = f"{PVGIS}?lat={lat}&lon={lon}&horirrad=1&outputformat=json"
    res["image"] = path
    res["figures"] = [["Point", f"{lat}° latitude, {lon}° longitude, elevation {pv['inputs']['location']['elevation']:.0f} m (centre of the box)"],
                      ["Radiation database reported by the service", db], ["Years", f"{years[0]} to {years[-1]}"],
                      ["Annual total, horizontal plane", f"{annual.mean():.0f} kWh per m² (lowest year {annual.min():.0f}, highest {annual.max():.0f})"],
                      ["Monthly means (kWh per m²)", "; ".join(f"{m} {x:.0f}" for m, x in zip(M, mean))]]
    res["see"] = [f"Each bar is the energy received in an average month by one horizontal square metre at the centre of the box, over {years[0]} to {years[-1]}. The thin lines show the lowest and the highest year.",
                  f"{M[top]} brings about {mean[top] / max(mean[low], 1e-6):.1f} times the energy of {M[low]} ({mean[top]:.0f} against {mean[low]:.0f} kWh per m²). "
                  f"Over a year the point receives about {annual.mean():.0f} kWh per m², between {annual.min():.0f} and {annual.max():.0f} depending on the year."]
    res["trust"] = ("The values come from an existing public service and are not reprocessed, only averaged. "
                    "Taking one point as the value for a whole area, or for every roof, is a simplification that has not been validated.")
    res["steps"] = [
        _step("Ask the service for the monthly irradiation on a horizontal plane at the point, for every year available.", "service", ref={"t": "The request sent to PVGIS", "u": url}),
        _step(f"Average the {len(years)} yearly values of each month; keep the lowest and the highest year.", "choice", by="the tool's default"),
        _step("Add the twelve months of each year to obtain annual totals.", "choice", by="the tool's default"),
        _step("Taking this single point as the value for the whole area.", "interpretation",
              note="Not valid for a roof-by-roof study: what a roof receives depends on its tilt, its orientation and the shadows of its neighbours.")]
    res["inputs"] = [{"what": "Global irradiation on a horizontal plane, monthly",
                      "used": f"PVGIS 5.3 web service of the European Commission's Joint Research Centre, monthly radiation tool, database {db}"
                              + (", with horizon shading from terrain." if pv["inputs"]["meteo_data"].get("use_horizon") else "."),
                      "lake": "EO.EUM.DAT.MSG.SEVIRI-SARAH-CDR-V003 (SARAH record) or EO.ECMWF.DAT.CAMS_SOLAR_RADIATION_TIMESERIES (CAMS, on demand)",
                      "rel": 1, "note": "Whether the PVGIS database is identical to the record held in the Data Lake was not checked."}]
    res["missing"] = ["A map: this is one point. What each roof or plot receives needs a shading model fed by a fine surface model.",
                      "The conversion into electricity: panel type, losses and usable surface are not considered.",
                      "Obtained from a public service, not through the DestinE API."]
    res["stats"] = {"annual_mean": float(annual.mean()), "monthly_mean": [float(x) for x in mean], "years": [years[0], years[-1]], "db": db, "point": [lat, lon]}
    return res


# ---------------------------------------------------------------------------------------------- recipe 4
def surface_temperature(plan, backend="public", workdir=".", progress=None):
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    say = progress or (lambda t: None)
    bbox = _check_bbox(plan["bbox"])
    res = _result("surface_temperature", plan, bbox, backend)
    p = plan.get("params") or {}
    who = lambda key: "you" if key in (plan.get("set_by_user") or []) else ("the plan" if key in p or key in plan else "the tool's default")
    end = plan.get("end") or dt.date.today().isoformat()
    start = plan.get("start") or (dt.date.fromisoformat(end) - dt.timedelta(days=90)).isoformat()
    max_cloud = float(p.get("max_cloud", 15))
    max_px = int(p.get("max_pixels", 2600))
    say("Searching Landsat images…")
    body = {"collections": ["landsat-c2-l2"], "bbox": list(bbox), "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": 100,
            "query": {"eo:cloud_cover": {"lt": max_cloud}, "platform": {"in": ["landsat-8", "landsat-9"]}}}
    r = _http("POST", f"{PLANETARY}/stac/v1/search", json=body, timeout=90)
    r.raise_for_status()
    feats = [f for f in r.json().get("features", []) if "lwir11" in f.get("assets", {})]
    if not feats:
        raise RuntimeError(f"No Landsat 8 or 9 image with less than {max_cloud:.0f} % cloud between {start} and {end} over this area. Widen the period.")

    def cover(f):
        b = f.get("bbox") or [0, 0, 0, 0]
        iw = max(0, min(b[2], bbox[2]) - max(b[0], bbox[0])); ih = max(0, min(b[3], bbox[3]) - max(b[1], bbox[1]))
        return iw * ih / ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
    best = None
    for f in sorted([f for f in feats if cover(f) >= 0.5] or feats, key=lambda f: f["properties"].get("eo:cloud_cover", 100))[:5]:
        say(f"Reading {f['id']}…")
        sig = _http("GET", f"{PLANETARY}/sas/v1/sign", params={"href": f["assets"]["lwir11"]["href"]}, timeout=60)
        sig.raise_for_status()
        with _env():
            with rasterio.open(sig.json()["href"]) as ds:
                b = transform_bounds("EPSG:4326", ds.crs, *bbox, densify_pts=21)
                win = from_bounds(*b, transform=ds.transform)
                h, w = int(round(win.height)), int(round(win.width))
                k = max(1.0, max(h, w) / max_px)
                if k == 1.0:
                    win = win.round_offsets().round_lengths(); h, w = int(win.height), int(win.width); b = rasterio.windows.bounds(win, ds.transform)
                dn = ds.read(1, window=win, out_shape=(max(1, int(round(h / k))), max(1, int(round(w / k)))), boundless=True, fill_value=0,
                             resampling=rasterio.enums.Resampling.average if k > 1 else rasterio.enums.Resampling.nearest)
                meta = {"bounds": b, "pixel_m": ds.res[0] * k, "native_m": ds.res[0]}
        frac = float((dn > 0).mean())
        if best is None or frac > best[0] + 0.05:
            best = (frac, f, dn, meta)
        if frac >= 0.9:                      # the least cloudy image that covers at least 90 % of the box is kept
            break
    frac, f, dn, meta = best
    if frac < 0.05:
        raise RuntimeError("The images found do not cover this area. Check the box.")
    props = f["properties"]
    date, hour = props["datetime"][:10], props["datetime"][11:16]
    band = (f["assets"]["lwir11"].get("raster:bands") or [{}])[0]
    scale, offset = float(band.get("scale", 0.00341802)), float(band.get("offset", 149.0))
    t = np.where(dn > 0, dn.astype("float64") * scale + offset - 273.15, np.nan)
    v = t[np.isfinite(t)]
    med, p5, p95 = float(np.median(v)), float(np.percentile(v, 5)), float(np.percentile(v, 95))
    d = t - med
    hot = float((v - med >= 5).mean() * 100); cool = float((v - med <= -5).mean() * 100)
    wkm, hkm = (meta["bounds"][2] - meta["bounds"][0]) / 1000, (meta["bounds"][3] - meta["bounds"][1]) / 1000

    say("Drawing the map…")
    b = meta["bounds"]
    fw = 7.2; fh = max(3.5, min(9.0, fw * hkm / max(wkm, 1e-6) * 0.92))
    fig, ax = plt.subplots(figsize=(fw, fh), dpi=120)
    cm = plt.get_cmap("RdYlBu_r").copy(); cm.set_bad("#bbbbbb")
    span = max(4.0, float(np.percentile(np.abs(v - med), 98)))
    im = ax.imshow(d, cmap=cm, vmin=-span, vmax=span, extent=[b[0], b[2], b[1], b[3]], interpolation="nearest")
    L = _nice_km(wkm) * 1000
    x0, y0 = b[0] + (b[2] - b[0]) * 0.04, b[1] + (b[3] - b[1]) * 0.05
    ax.plot([x0, x0 + L], [y0, y0], color="black", lw=3)
    ax.text(x0 + L / 2, y0 + (b[3] - b[1]) * 0.018, f"{L / 1000:g} km", ha="center", fontsize=9, bbox=dict(fc="white", ec="none", alpha=.8, pad=1))
    ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02).set_label(f"Difference from the median of the area ({med:.1f} °C), in °C")
    fig.tight_layout()
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, f"prototype_surface_temperature_{date}.png")
    fig.savefig(path, dpi=120); plt.close(fig)

    res["image"] = path
    res["figures"] = [["Image used", f"{f['id']}, acquired on {date} at {hour} UTC, {props.get('eo:cloud_cover', 0):.1f} % cloud over the scene"],
                      ["Area computed", f"{wkm:.1f} km by {hkm:.1f} km, {t.shape[1]} by {t.shape[0]} pixels of {meta['pixel_m']:.0f} m"],
                      ["Surface temperature", f"median {med:.1f} °C; 90 % of the area between {p5:.1f} and {p95:.1f} °C"],
                      ["At least 5 °C above the median", f"{hot:.1f} % of the area"], ["At least 5 °C below the median", f"{cool:.1f} % of the area"],
                      ["Part of the box covered by the image", f"{frac * 100:.0f} %"]]
    res["see"] = [f"Colours show how much warmer (red) or cooler (blue) each piece of surface is than the median of the area, {med:.1f} °C, on {date} at {hour} UTC. "
                  "It is the temperature of the surface itself (roofs, roads, bare soil, tree tops, water), not of the air.",
                  f"{hot:.1f} % of the area is at least 5 °C above the median and {cool:.1f} % at least 5 °C below. Water and dense vegetation are usually the coolest surfaces; "
                  "large roofs, tarmac and dry bare soil the warmest." + (" Grey is missing data." if frac < 0.99 else "")]
    res["trust"] = ("The temperature is the official Landsat product, only rescaled as documented. "
                    "Reading the hottest surfaces as places where people overheat is an interpretation that has not been validated.")
    res["steps"] = [
        _step(f"Choose the image: the least cloudy Landsat 8 or 9 acquisition covering the box between {start} and {end} (less than {max_cloud:.0f} % cloud over the scene). Kept: {date}, {props.get('eo:cloud_cover', 0):.1f} % cloud.",
              "choice", note="A single date and a single time of day: Landsat passes in the morning.", by=who("start")),
        _step("Read the surface temperature band of the Landsat Collection 2 Level-2 product" + (f", averaged from {meta['native_m']:.0f} m to {meta['pixel_m']:.0f} m because the box is large." if meta["pixel_m"] > meta["native_m"] + 0.5 else f" on its {meta['native_m']:.0f} m grid.") + " Zero means no data.",
              "documented", ref="usgs_st", note="The product is delivered on a 30 m grid; the thermal sensor itself is coarser than that grid, so neighbouring pixels are not independent."),
        _step(f"Convert to temperature: digital number × {scale:g} + {offset:g} gives kelvins; subtract 273.15 for degrees Celsius.", "documented", ref="usgs_st",
              note="Scale and offset are also stated in the catalogue record of the image."),
        _step("No pixel-level cloud mask applied; only the cloud cover of the whole scene was used to choose the image.", "choice",
              note="A cloud or its shadow, if any, shows as a cold patch.", by="the tool's default"),
        _step("Express each pixel as a difference from the median of the area, with a colour scale centred on zero.", "choice", by="the tool's default"),
        _step("Reading the hottest surfaces as places where people overheat.", "interpretation",
              note="Not validated. Air temperature, shade, wind and the time of day matter as much; a morning image says little about the night.")]
    res["inputs"] = [{"what": "Surface temperature, 30 m grid", "used": f"Landsat Collection 2 Level-2, image {f['id']} ({props.get('platform', '')}), read from the public copy on Microsoft Planetary Computer.",
                      "lake": "EO.NASA.DAT.LANDSAT.C2_L2"}]
    need = _need_m(plan.get("need"))
    res["missing"] = ["Air temperature and comfort: this is the temperature of surfaces, seen from above.",
                      "Other times of day and other dates: one morning overpass does not describe a heat wave or the night.",
                      "A cloud mask at pixel level, and a check against ground measurements."]
    if need and need * 3 < meta["pixel_m"]:
        res["warnings"].append(f"You asked for a detail of about {_fmt_m(need)}; this prototype resolves {_fmt_m(meta['pixel_m'])} at best. It shows the principle, not the answer.")
    if frac < 0.99:
        res["missing"].append(f"Part of the box ({(1 - frac) * 100:.0f} %) lies outside the image used.")
    res["missing"].append("Read from a public copy of the data, not through the DestinE API.")
    res["stats"] = {"date": date, "median": med, "p5": p5, "p95": p95, "hot": hot, "cool": cool, "pixel_m": meta["pixel_m"], "scale": scale, "offset": offset}
    return res


RUNNERS = {"vegetation_index": vegetation_index, "terrain_slope": terrain_slope, "surface_temperature": surface_temperature, "solar_monthly": solar_monthly}


def run(plan, backend="public", workdir="prototypes", progress=None):
    """Generates the prototype described by `plan`. Returns the result dictionary; on failure, {"ok": False, "error": ...}."""
    recipe = plan.get("recipe") or recipe_for(plan.get("ingredient", ""), plan.get("variable", ""), plan.get("service", ""))
    if recipe not in RUNNERS:
        return {"ok": False, "error": "No recipe exists yet for this ingredient: nothing was computed.", "recipe": recipe}
    if backend != "public":
        return {"ok": False, "error": "Reading through the DestinE API is not implemented yet. Use the public copies, or run the DestinE check and send its report.", "recipe": recipe}
    try:
        return RUNNERS[recipe](plan, backend=backend, workdir=workdir, progress=progress)
    except Exception as ex:                                   # a prototype must fail with a readable reason
        return {"ok": False, "error": str(ex), "recipe": recipe, "kind": type(ex).__name__}


def probe_destine(token, bbox, start, end):
    """Looks at what the DestinE API returns for the collections the recipes need, WITHOUT downloading any data.
    The report (asset names, properties, order parameters) is what is needed to write the DestinE reading code."""
    H = {"Authorization": f"Bearer {token}"}
    rep = {"when": dt.datetime.now(dt.timezone.utc).isoformat(), "bbox": list(bbox), "checks": []}
    for cid in ("EO.ESA.DAT.SENTINEL-2.MSI.L2A", "EO.DEM.DAT.COP-DEM_GLO-30-DGED", "EO.EUM.DAT.MSG.SEVIRI-SARAH-CDR-V003"):
        c = {"collection": cid}
        try:
            r = requests.post(f"{HDA_STAC}/search", headers=H, timeout=120,
                              json={"collections": [cid], "bbox": list(bbox), "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": 2})
            c["status"] = r.status_code
            if r.ok:
                fs = r.json().get("features", [])
                c["items"] = len(fs)
                if fs:
                    f = fs[0]
                    c["id"] = f.get("id"); c["property_names"] = sorted(f.get("properties", {}))[:60]
                    c["assets"] = {k: {x: str(a.get(x))[:120] for x in ("type", "title", "roles", "href") if a.get(x)} for k, a in list(f.get("assets", {}).items())[:12]}
            else:
                c["body"] = r.text[:300]
        except Exception as ex:
            c["error"] = str(ex)
        rep["checks"].append(c)
    try:
        q = requests.get(f"{HDA_STAC}/collections/EO.ECMWF.DAT.CAMS_SOLAR_RADIATION_TIMESERIES/queryables", timeout=120).json()
        rep["cams_solar_order"] = {"required": q.get("required", []), "parameters": {k: (v.get("enum") or v.get("type")) for k, v in list(q.get("properties", {}).items())[:20]}}
    except Exception as ex:
        rep["cams_solar_order"] = {"error": str(ex)}
    return rep


if __name__ == "__main__":
    import sys
    plan = json.load(open(sys.argv[1], encoding="utf-8")) if len(sys.argv) > 1 else {
        "ingredient": "tree canopy", "bbox": [1.30, 43.50, 1.55, 43.70], "start": "2024-07-01", "end": "2024-07-10"}
    out = run(plan, progress=print)
    print(json.dumps({k: v for k, v in out.items() if k not in ("stats",)}, indent=1, ensure_ascii=False)[:3000])
