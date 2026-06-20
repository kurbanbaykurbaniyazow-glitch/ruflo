#!/usr/bin/env python3
"""Поиск эджа: альтернативные классы стратегий на 2-летней истории. $500/5x/3%, walk-forward."""
import json
from bt import resample_15m, atr_series

def resample(b5, minutes):
    g = {}; span = minutes*60*1000
    for b in b5: g.setdefault(b["t"]//span, []).append(b)
    out = []
    for k in sorted(g):
        grp = sorted(g[k], key=lambda x: x["t"])
        out.append({"t": k*span, "o": grp[0]["o"], "h": max(x["h"] for x in grp),
                    "l": min(x["l"] for x in grp), "c": grp[-1]["c"]})
    return out

def ema(vals, n):
    out = []; k = 2/(n+1); e = vals[0]
    for v in vals: e = v*k + e*(1-k); out.append(e)
    return out

def rsi(vals, n=14):
    out = [50.0]*len(vals); g = l = 0.0
    for i in range(1, len(vals)):
        d = vals[i]-vals[i-1]; up = max(d, 0); dn = max(-d, 0)
        if i <= n: g += up; l += dn; out[i] = 50.0
        if i == n: g/=n; l/=n
        if i > n:
            g = (g*(n-1)+up)/n; l = (l*(n-1)+dn)/n
            rs = g/l if l > 0 else 99; out[i] = 100-100/(1+rs)
    return out

def engine(bars, signal_fn, p):
    atr = atr_series(bars, 14)
    closes = [b["c"] for b in bars]
    ctx = signal_fn(bars, atr, closes, p)
    eq = 500.0; START = eq; pos = None; trades = []; eqc = [eq]
    for i in range(2, len(bars)):
        bar = bars[i]
        if pos is not None:
            h, l = bar["h"], bar["l"]; side = pos["s"]; closed = False
            hit_sl = (l <= pos["sl"]) if side == 1 else (h >= pos["sl"])
            if hit_sl:
                px = pos["sl"]; eq += (px-pos["e"])*pos["q"]*side; trades.append((px-pos["e"])*side); pos = None; closed = True
            if not closed:
                hit_tp = (h >= pos["tp"]) if side == 1 else (l <= pos["tp"])
                if hit_tp:
                    px = pos["tp"]; eq += (px-pos["e"])*pos["q"]*side; trades.append((px-pos["e"])*side); pos = None; closed = True
            # ATR-трейлинг (опц.)
            if pos is not None and p.get("trail", 0) > 0:
                if side == 1: pos["sl"] = max(pos["sl"], bar["c"]-p["trail"]*atr[i])
                else: pos["sl"] = min(pos["sl"], bar["c"]+p["trail"]*atr[i])
        if pos is None and atr[i] > 0:
            sig = ctx[i]
            if sig != 0:
                e = bar["c"]; sl = e - sig*p["sl_atr"]*atr[i]; dist = abs(e-sl)
                if dist > 0:
                    q = min(eq*0.03/dist, eq*5.0/e)
                    pos = {"s": sig, "e": e, "sl": sl, "tp": e + sig*p["sl_atr"]*p["rr"]*atr[i], "q": q}
        eqc.append(eq)
    wins = [t for t in trades if t > 0]
    gp = sum(t for t in trades if t > 0); gl = -sum(t for t in trades if t < 0)
    # PnL знак считаем по факту eq; пересчёт PF по реализованным сделкам неточен из-за qty -> используем eq-кривую покотировочно
    pf = gp/gl if gl > 0 else (99 if gp > 0 else 0)
    peak = -1e9; mdd = 0
    for e in eqc: peak = max(peak, e); mdd = max(mdd, (peak-e)/peak*100 if peak > 0 else 0)
    return {"trd": len(trades), "pf": pf, "wr": (len(wins)/len(trades)*100 if trades else 0),
            "eq": eq, "roi": (eq/START-1)*100, "mdd": mdd}

# --- сигнальные функции: возвращают список сигналов по барам ---
def sig_donchian(bars, atr, closes, p):
    n = p["lookback"]; out = [0]*len(bars)
    for i in range(n, len(bars)):
        hh = max(b["h"] for b in bars[i-n:i]); ll = min(b["l"] for b in bars[i-n:i])
        if closes[i] > hh: out[i] = 1
        elif closes[i] < ll: out[i] = -1
    return out

def sig_ema(bars, atr, closes, p):
    fast = ema(closes, p["fast"]); slow = ema(closes, p["slow"]); out = [0]*len(bars)
    for i in range(1, len(bars)):
        if fast[i] > slow[i] and fast[i-1] <= slow[i-1]: out[i] = 1
        elif fast[i] < slow[i] and fast[i-1] >= slow[i-1]: out[i] = -1
    return out

def sig_rsi_revert(bars, atr, closes, p):
    r = rsi(closes, p["rsi_n"]); out = [0]*len(bars)
    for i in range(1, len(bars)):
        if r[i-1] < p["lo"] and r[i] >= p["lo"]: out[i] = 1
        elif r[i-1] > p["hi"] and r[i] <= p["hi"]: out[i] = -1
    return out

if __name__ == "__main__":
    BTC = json.load(open("/tmp/okx_btc_max.json"))
    ETH = json.load(open("/tmp/okx_eth_max.json"))
    def split(b): s = int(len(b)*0.6); return b[:s], b[s:]

    tests = []
    for tf in [60, 240]:
        b = resample(BTC, tf); tr, te = split(b)
        eth = resample(ETH, tf)
        for name, fn, grids in [
            ("Donchian breakout", sig_donchian, [dict(lookback=lb, sl_atr=2, rr=rr, trail=tl)
                for lb in (20, 40, 55) for rr in (2, 3) for tl in (0, 3)]),
            ("EMA cross",         sig_ema,      [dict(fast=f, slow=s, sl_atr=2, rr=rr, trail=tl)
                for (f, s) in ((9, 21), (20, 50), (50, 200)) for rr in (2, 3) for tl in (0, 3)]),
            ("RSI mean-revert",   sig_rsi_revert,[dict(rsi_n=14, lo=lo, hi=100-lo, sl_atr=2, rr=rr, trail=0)
                for lo in (20, 30) for rr in (1, 1.5, 2)]),
        ]:
            best = None
            for g in grids:
                rtr = engine(tr, fn, g)
                if rtr["trd"] < 30: continue
                if best is None or rtr["roi"] > best[0]["roi"]: best = (rtr, g)
            if best:
                rtr, g = best
                rte = engine(te, fn, g); reth = engine(eth, fn, g)
                tests.append((name, tf, g, rtr, rte, reth))

    print(f"{'стратегия':20} {'TF':>4} | {'TRAIN roi/pf':>14} | {'OOS roi/pf/wr':>18} | {'ETH roi/pf':>13}")
    print("-"*78)
    for name, tf, g, rtr, rte, reth in tests:
        print(f"{name:20} {tf:>3}m | {rtr['roi']:+6.0f}% {rtr['pf']:4.2f}    | "
              f"{rte['roi']:+6.0f}% {rte['pf']:4.2f} {rte['wr']:3.0f}%   | {reth['roi']:+6.0f}% {reth['pf']:4.2f}")
