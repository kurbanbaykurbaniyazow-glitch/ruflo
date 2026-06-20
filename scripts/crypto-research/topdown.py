#!/usr/bin/env python3
"""Top-down ICT: 1D тренд -> POI(OB+FVG) на 4H/1H -> вход по CHoCH/BOS на 15m, в сторону тренда."""
import json
from bt import atr_series, market_structure

def resample(b5, minutes):
    g = {}; span = minutes*60*1000
    for b in b5: g.setdefault(b["t"]//span, []).append(b)
    out = []
    for k in sorted(g):
        gr = sorted(g[k], key=lambda x: x["t"])
        out.append({"t": k*span, "o": gr[0]["o"], "h": max(x["h"] for x in gr),
                    "l": min(x["l"] for x in gr), "c": gr[-1]["c"]})
    return out

def ema(vals, n):
    out = []; k = 2/(n+1); e = vals[0]
    for v in vals: e = v*k+e*(1-k); out.append(e)
    return out

def extract_zones(bars, tf_min, disp_atr):
    """OB + FVG зоны. Возвращает list of (valid_from_ts, lo, hi, side)."""
    atr = atr_series(bars, 14); span = tf_min*60*1000; z = []
    for k in range(2, len(bars)-1):
        # Order Block + displacement
        a, b = bars[k], bars[k+1]
        rng = b["c"]-b["o"]
        if a["c"] < a["o"] and rng > disp_atr*atr[k] and b["c"] > a["h"]:
            z.append((b["t"]+span, a["l"], a["h"], "demand"))
        if a["c"] > a["o"] and -rng > disp_atr*atr[k] and b["c"] < a["l"]:
            z.append((b["t"]+span, a["l"], a["h"], "supply"))
        # FVG (3 свечи k-2,k-1,k)
        c0, c2 = bars[k-2], bars[k]
        if c0["h"] < c2["l"]:
            z.append((c2["t"]+span, c0["h"], c2["l"], "demand"))
        if c0["l"] > c2["h"]:
            z.append((c2["t"]+span, c2["h"], c0["l"], "supply"))
    return z

def backtest(b5, p, fee_pct=0.05):
    e15 = resample(b5, 15); d1 = resample(b5, 1440)
    h4 = resample(b5, 240); h1 = resample(b5, 60)
    atr15 = atr_series(e15, 14)
    ms15 = market_structure(e15, p["swing15"])
    # 1D тренд (EMA, латч пред. закрытого дня)
    dC = [b["c"] for b in d1]; dE = ema(dC, p["d_ema"]); spanD = 1440*60*1000
    trendD = {}
    for k in range(1, len(d1)):
        trendD[d1[k]["t"]//spanD] = 1 if dC[k-1] > dE[k-1] else -1
    # зоны 4H + 1H
    zones = extract_zones(h4, 240, p["disp"]) + extract_zones(h1, 60, p["disp"])
    zones.sort()  # по valid_from
    zi = 0; active = []   # активные зоны: [vf,lo,hi,side]

    eq = 500.0; START = eq; pos = None; trades = []; eqc = [eq]; fee = fee_pct/100
    for i in range(2, len(e15)):
        bar = e15[i]; t = bar["t"]
        while zi < len(zones) and zones[zi][0] <= t:
            active.append(list(zones[zi])); zi += 1
        # чистка: митигированные/старые зоны
        active = [z for z in active if (t-z[0]) < p["zone_life"]*15*60*1000]

        if pos is not None:
            h, l = bar["h"], bar["l"]; s = pos["s"]; ex = None
            if (l <= pos["sl"]) if s == 1 else (h >= pos["sl"]): ex = pos["sl"]
            elif (h >= pos["tp"]) if s == 1 else (l <= pos["tp"]): ex = pos["tp"]
            if ex is not None:
                eq += (ex-pos["e"])*pos["q"]*s - pos["q"]*ex*fee; trades.append(((ex-pos["e"])*s, pos)); pos = None

        if pos is None and atr15[i] > 0:
            td = trendD.get(t//spanD, 0)
            lastPH = ms15[i][2]; lastPL = ms15[i][3]
            brkUp = lastPH is not None and bar["c"] > lastPH
            brkDn = lastPL is not None and bar["c"] < lastPL
            sig = 0; zlo = zhi = None
            if td == 1 and brkUp:
                # цена тегнула demand-зону на этом баре
                for z in active:
                    if z[3] == "demand" and bar["l"] <= z[2] and bar["l"] >= z[1]*(1-p["tag_tol"]):
                        sig = 1; zlo, zhi = z[1], z[2]; break
            elif td == -1 and brkDn:
                for z in active:
                    if z[3] == "supply" and bar["h"] >= z[1] and bar["h"] <= z[2]*(1+p["tag_tol"]):
                        sig = -1; zlo, zhi = z[1], z[2]; break
            if sig != 0:
                e = bar["c"]
                sl = zlo-p["sl_buf"]*atr15[i] if sig == 1 else zhi+p["sl_buf"]*atr15[i]
                dist = abs(e-sl)
                if dist > 0:
                    tp = e+sig*dist*p["rr"]
                    q = min(eq*0.03/dist, eq*5.0/e); eq -= q*e*fee
                    pos = {"s": sig, "e": e, "sl": sl, "tp": tp, "q": q}
        eqc.append(eq)

    pnl = [x[0]*x[1]["q"] for x in trades]
    gp = sum(x for x in pnl if x > 0); gl = -sum(x for x in pnl if x < 0)
    pf = gp/gl if gl > 0 else (99 if gp > 0 else 0)
    wins = sum(1 for x in pnl if x > 0)
    peak = -1e9; mdd = 0
    for e in eqc: peak = max(peak, e); mdd = max(mdd, (peak-e)/peak*100 if peak > 0 else 0)
    return {"trd": len(trades), "pf": pf, "wr": (wins/len(trades)*100 if trades else 0),
            "eq": eq, "roi": (eq/START-1)*100, "mdd": mdd}

if __name__ == "__main__":
    D = {k: json.load(open(f"/tmp/v_{k.lower()}.json")) for k in ["BTC", "ETH", "SOL"]}
    def split(b): s = int(len(b)*0.6); return b[:s], b[s:]
    BASE = dict(swing15=4, d_ema=20, disp=0.5, zone_life=200, tag_tol=0.002,
                sl_buf=0.5, rr=3.0)
    configs = {
        "base rr3 dEMA20": dict(BASE),
        "rr2": dict(BASE, rr=2.0),
        "rr4 disp1.0": dict(BASE, rr=4.0, disp=1.0),
        "dEMA50 rr3": dict(BASE, d_ema=50),
    }
    print(f"{'конфиг':18} | {'BTC train':>13} | {'BTC OOS':>15} | {'ETH all':>12} | {'SOL all':>12}")
    print("-"*80)
    for name, p in configs.items():
        tr, te = split(D["BTC"])
        rtr = backtest(tr, p); rte = backtest(te, p); re = backtest(D["ETH"], p); rs = backtest(D["SOL"], p)
        print(f"{name:18} | {rtr['roi']:+5.0f}% pf{rtr['pf']:.2f} | {rte['roi']:+5.0f}% pf{rte['pf']:.2f} t{rte['trd']:<4}| "
              f"{re['roi']:+5.0f}% pf{re['pf']:.2f} | {rs['roi']:+5.0f}% pf{rs['pf']:.2f}")
