#!/usr/bin/env python3
"""Analysis for "The Industry Mix Channel".

Shift-share design: state AI exposure = sum over 2-digit sectors of
(state employment share in 2019) x (sector AI exposure score from AIIE).

Writes analysis/stats.json and figures/fig1..fig3.svg.

Run: python3 analysis/analyze.py  (pandas + numpy)
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "analysis", "stats.json")
FIGS = os.path.join(ROOT, "figures")

SECTORS = ["11", "21", "22", "23", "31-33", "42", "44-45", "48-49", "51", "52",
           "53", "54", "55", "56", "61", "62", "71", "72", "81", "99"]
STATE_NAMES = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY",
}


def cluster_ols(y, X, groups):
    """OLS with cluster-robust (CR1) standard errors by group."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    mask = np.isfinite(y) & np.isfinite(X).all(axis=1)
    X, y, groups = X[mask], y[mask], np.asarray(groups)[mask]
    n, k = X.shape
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    XtX_inv = np.linalg.pinv(X.T @ X)
    meat = np.zeros((k, k))
    for g in np.unique(groups):
        m = groups == g
        Xg = X[m]
        eg = resid[m]
        s = Xg.T @ eg
        meat += np.outer(s, s)
    G = len(np.unique(groups))
    scale = (G / max(G - 1, 1)) * ((n - 1) / max(n - k, 1))
    cov = XtX_inv @ meat @ XtX_inv * scale
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = 1 - (resid ** 2).sum() / ss_tot if ss_tot > 0 else np.nan
    return beta, se, n, r2


def svg_bar(path, title, labels, values, ylabel, colour="#1F4E79", width=900, height=380):
    pad_l, pad_r, pad_t, pad_b = 60, 190, 36, 60
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    vmin, vmax = min(0, min(values)), max(0, max(values))
    span = (vmax - vmin) or 1

    def Y(v):
        return pad_t + ih - (v - vmin) / span * ih

    bw = iw / max(len(labels), 1)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
         f'font-family="Helvetica,Arial,sans-serif">',
         f'<rect width="{width}" height="{height}" fill="#fff"/>',
         f'<text x="{pad_l}" y="22" font-size="14" font-weight="700">{title}</text>',
         f'<line x1="{pad_l}" y1="{Y(0):.1f}" x2="{pad_l+iw}" y2="{Y(0):.1f}" stroke="#999"/>']
    for i, (lab, v) in enumerate(zip(labels, values)):
        x = pad_l + i * bw + bw * 0.15
        y = min(Y(v), Y(0))
        h = abs(Y(v) - Y(0))
        o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw*0.7:.1f}" height="{h:.1f}" fill="{colour}"/>')
        o.append(f'<text x="{x+bw*0.35:.1f}" y="{pad_t+ih+14}" font-size="8" fill="#555" '
                 f'text-anchor="middle">{lab}</text>')
    o.append(f'<text x="{pad_l}" y="{height-8}" font-size="9" fill="#666">{ylabel}</text>')
    o.append("</svg>")
    open(path, "w").write("\n".join(o))


def svg_event(path, title, years, coefs, ses, width=900, height=380):
    pad_l, pad_r, pad_t, pad_b = 60, 190, 36, 60
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    lo = min(c - 1.96 * s for c, s in zip(coefs, ses))
    hi = max(c + 1.96 * s for c, s in zip(coefs, ses))
    span = (hi - lo) or 1
    lo -= span * 0.1
    hi += span * 0.1

    def X(i):
        return pad_l + (i / max(len(years) - 1, 1)) * iw

    def Y(v):
        return pad_t + ih - (v - lo) / (hi - lo) * ih

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
         f'font-family="Helvetica,Arial,sans-serif">',
         f'<rect width="{width}" height="{height}" fill="#fff"/>',
         f'<text x="{pad_l}" y="22" font-size="14" font-weight="700">{title}</text>',
         f'<line x1="{pad_l}" y1="{Y(0):.1f}" x2="{pad_l+iw}" y2="{Y(0):.1f}" stroke="#999" stroke-dasharray="3,3"/>']
    pts = " ".join(f"{'M' if i == 0 else 'L'}{X(i):.1f},{Y(c):.1f}" for i, c in enumerate(coefs))
    o.append(f'<path d="{pts}" fill="none" stroke="#1F4E79" stroke-width="2"/>')
    for i, (c, s) in enumerate(zip(coefs, ses)):
        o.append(f'<line x1="{X(i):.1f}" y1="{Y(c-1.96*s):.1f}" x2="{X(i):.1f}" y2="{Y(c+1.96*s):.1f}" stroke="#1F4E79" stroke-width="1"/>')
        o.append(f'<circle cx="{X(i):.1f}" cy="{Y(c):.1f}" r="2.5" fill="#1F4E79"/>')
        o.append(f'<text x="{X(i):.1f}" y="{pad_t+ih+16}" font-size="9" fill="#555" text-anchor="middle">{years[i]}</text>')
    o.append(f'<text x="{pad_l}" y="{height-8}" font-size="9" fill="#666">Coefficient on exposure x year, 2019 omitted. Bars: 95% CI, clustered by state.</text>')
    o.append("</svg>")
    open(path, "w").write("\n".join(o))


def svg_hist(path, title, edges, counts, actual, width=900, height=340):
    pad_l, pad_r, pad_t, pad_b = 60, 190, 36, 40
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    hi = max(counts) or 1
    bw = iw / len(counts)
    xmin, xmax = edges[0], edges[-1]

    def X(v):
        return pad_l + (v - xmin) / (xmax - xmin) * iw

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
         f'font-family="Helvetica,Arial,sans-serif">',
         f'<rect width="{width}" height="{height}" fill="#fff"/>',
         f'<text x="{pad_l}" y="22" font-size="14" font-weight="700">{title}</text>']
    for i, c in enumerate(counts):
        h = c / hi * ih
        o.append(f'<rect x="{pad_l+i*bw:.1f}" y="{pad_t+ih-h:.1f}" width="{bw*0.9:.1f}" '
                 f'height="{h:.1f}" fill="#9DB4CC"/>')
    o.append(f'<line x1="{X(actual):.1f}" y1="{pad_t}" x2="{X(actual):.1f}" y2="{pad_t+ih}" '
             f'stroke="#C00000" stroke-width="2"/>')
    o.append(f'<text x="{X(actual)+4:.1f}" y="{pad_t+12}" font-size="9" fill="#C00000">actual</text>')
    o.append(f'<text x="{pad_l}" y="{height-6}" font-size="9" fill="#666">1,000 shuffles of sector exposure. Actual coefficient in red.</text>')
    o.append("</svg>")
    open(path, "w").write("\n".join(o))


def main():
    os.makedirs(FIGS, exist_ok=True)

    # --- sector exposure from AIIE
    aioe = pd.read_excel(os.path.join(DATA, "aioe_language_modeling.xlsx"), sheet_name="LM AIIE")
    aioe.columns = ["naics", "description", "score"]
    aioe["naics"] = aioe["naics"].astype(str).str.zfill(6)
    aioe["score"] = pd.to_numeric(aioe["score"], errors="coerce")
    aioe = aioe.dropna(subset=["score"])

    def to_sector(code):
        two = code[:2]
        if two in ("31", "32", "33"):
            return "31-33"
        if two in ("44", "45"):
            return "44-45"
        if two in ("48", "49"):
            return "48-49"
        return two

    aioe["sector"] = aioe["naics"].map(to_sector)
    sector_exposure = aioe.groupby("sector")["score"].mean()
    sector_z = (sector_exposure - sector_exposure.mean()) / sector_exposure.std()

    # --- state composition
    q = pd.read_csv(os.path.join(DATA, "qcew_2019_state.csv"), dtype={"state_fips": str})
    q = q[(q["own_code"] == 5) & (q["agglvl_code"] == 54) & q["industry_code"].isin(SECTORS)]
    q["state"] = q["state_fips"].map(STATE_NAMES)
    shares = (q.pivot_table(index="state", columns="industry_code",
                            values="annual_avg_emplvl", aggfunc="sum")
              .reindex(columns=SECTORS).fillna(0))
    shares = shares.div(shares.sum(axis=1), axis=0)

    exposure = shares @ sector_z.reindex(SECTORS).fillna(0)
    exposure = (exposure - exposure.mean()) / exposure.std()
    exposure.name = "exposure"

    top = exposure.sort_values(ascending=False)
    stats = {
        "exposure_sd": round(float(exposure.std()), 3),
        "top_states": [[s, round(float(v), 2)] for s, v in top.head(5).items()],
        "bottom_states": [[s, round(float(v), 2)] for s, v in top.tail(5).items()],
        "sector_exposure": {k: round(float(v), 3) for k, v in sector_z.items()},
    }

    # --- state employment, annual
    emp = pd.read_csv(os.path.join(DATA, "state_employment.csv"), dtype={"state_fips": str})
    emp["state"] = emp["state_fips"].map(STATE_NAMES)
    emp["date"] = pd.to_datetime(emp["date"])
    emp["year"] = emp["date"].dt.year
    annual = emp.groupby(["state", "year"])["employment_thousands"].mean().reset_index()
    annual = annual[annual["year"].between(2016, 2025)]
    annual["log_emp"] = np.log(annual["employment_thousands"])
    annual = annual.merge(exposure.rename("exposure"), left_on="state", right_index=True)

    # --- event study
    years = list(range(2016, 2026))
    states = sorted(annual["state"].unique())
    X, names = [], []
    X.append(np.ones(len(annual))); names.append("const")
    for s in states[1:]:
        X.append((annual["state"] == s).astype(float).to_numpy()); names.append("state:" + s)
    for y in years[1:]:
        X.append((annual["year"] == y).astype(float).to_numpy()); names.append("year:" + str(y))
    for y in years:
        if y == 2019:
            continue
        X.append((annual["exposure"] * (annual["year"] == y)).astype(float).to_numpy())
        names.append(f"exp:{y}")
    X = np.column_stack(X)
    beta, se, n, r2 = cluster_ols(annual["log_emp"], X, annual["state"])
    coef = {nm: (round(float(b), 4), round(float(s), 4)) for nm, b, s in zip(names, beta, se)}
    ev_years = [y for y in years if y != 2019]
    ev = [coef[f"exp:{y}"] for y in ev_years]
    stats["event_study"] = {
        "n": int(n), "r2": round(float(r2), 4),
        "years": ev_years,
        "coef": [c[0] for c in ev],
        "se": [c[1] for c in ev],
        "pre_2016_2018": [coef[f"exp:{y}"][0] for y in (2016, 2017, 2018)],
        "post_2022_2025": [coef[f"exp:{y}"][0] for y in (2022, 2023, 2024, 2025)],
    }

    # --- placebo: 2016-2019 only, baseline 2016, fake treatment at 2018
    pl = annual[annual["year"].between(2016, 2019)].copy()
    pyears = [2016, 2017, 2018, 2019]
    Xp = [np.ones(len(pl))]
    for s in states[1:]:
        Xp.append((pl["state"] == s).astype(float).to_numpy())
    for y in pyears[1:]:
        Xp.append((pl["year"] == y).astype(float).to_numpy())
    for y in pyears[1:]:
        Xp.append((pl["exposure"] * (pl["year"] == y)).astype(float).to_numpy())
    bp, sp, np_, rp = cluster_ols(pl["log_emp"], np.column_stack(Xp), pl["state"])
    stats["placebo"] = {
        "n": int(np_), "r2": round(float(rp), 4),
        "years": pyears[1:],
        "coef": [round(float(v), 4) for v in bp[-3:]],
        "se": [round(float(v), 4) for v in sp[-3:]],
    }

    # --- cross-sectional 2019-2025 change and permutation inference
    wide = annual.pivot(index="state", columns="year", values="log_emp")
    delta = (wide[2025] - wide[2019]).dropna()
    y_delta = delta.values
    x_delta = exposure.reindex(delta.index).values
    Xc = np.column_stack([np.ones(len(delta)), x_delta])
    bc, sc, nc, rc = cluster_ols(y_delta, Xc, delta.index)
    stats["cross_section"] = {"n": int(nc), "coef": round(float(bc[1]), 4),
                              "se": round(float(sc[1]), 4)}

    rng = np.random.default_rng(7)
    sectors = list(sector_z.index)
    actual = bc[1]
    perm = []
    for _ in range(1000):
        shuffled = pd.Series(rng.permutation(sector_z.values), index=sectors)
        e_star = shares @ shuffled.reindex(SECTORS).fillna(0)
        e_star = (e_star - e_star.mean()) / e_star.std()
        xs = e_star.reindex(delta.index).values
        Xs = np.column_stack([np.ones(len(delta)), xs])
        b, *_ = np.linalg.lstsq(Xs, y_delta, rcond=None)
        perm.append(b[1])
    perm = np.array(perm)
    p_rank = float((np.abs(perm) >= abs(actual)).mean())
    hist, edges = np.histogram(perm, bins=25)
    stats["permutation"] = {
        "draws": int(len(perm)),
        "actual_coef": round(float(actual), 4),
        "p_two_sided": round(p_rank, 3),
        "perm_sd": round(float(perm.std()), 4),
        "perm_p05": round(float(np.percentile(perm, 5)), 4),
        "perm_p95": round(float(np.percentile(perm, 95)), 4),
        "hist_counts": hist.tolist(),
        "hist_edges": [round(float(e), 4) for e in edges],
    }

    with open(OUT, "w") as fh:
        json.dump(stats, fh, indent=2, default=str)

    svg_bar(os.path.join(FIGS, "fig1_exposure.svg"),
            "State AI exposure, standardised (2019 industry mix x AIIE)",
            [top.index[i] for i in list(range(5)) + list(range(len(top) - 5, len(top)))],
            [top.values[i] for i in list(range(5)) + list(range(len(top) - 5, len(top)))],
            "Z-score. Top five and bottom five states.")
    svg_hist(os.path.join(FIGS, "fig3_permutation.svg"),
             "Permutation distribution of the exposure coefficient",
             stats["permutation"]["hist_edges"], stats["permutation"]["hist_counts"],
             actual)
    svg_event(os.path.join(FIGS, "fig2_event.svg"),
              "State employment and AI exposure: event-study coefficients",
              ev_years, [c[0] for c in ev], [c[1] for c in ev])

    print(json.dumps(stats, indent=2, default=str))


if __name__ == "__main__":
    main()
