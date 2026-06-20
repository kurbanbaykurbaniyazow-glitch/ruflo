#!/usr/bin/env python3
"""MTF + Liquidity-pool модель: HTF-биас + снятие пула стопов + продолжение по тренду.
Цель (TP) = следующий пул ликвидности. Объём — опциональное подтверждение."""
from bt import atr_series

def resample(b5, minutes):
    g = {}; span = minutes*60*1000
    for b in b5: g.setdefault(b["t"]//span, []).append(b)
    out = []
    for k in sorted(g):
        gr = sorted(g[k], key=lambda x: x["t"])
        row = {"t": k*span, "o": gr[0]["o"], "h": max(x["h"] for x in gr),
               "l": min(x["l"] for x in gr), "c": gr[-1]["c"]}
        if "v" in gr[0]: row["v"] = sum(x.get("v", 0) for x in gr)
        out.append(row)
    return out

def ema(vals, n):
    out = []; k = 2/(n+1); e = vals[0]
    for v in vals: e = v*k + e*(1-k); out.append(e)
    return out

def pivots(bars, L):
    """возвращает per-bar: (is_pivot_high_confirmed_here, ph_price, is_pl, pl_price) с лагом L."""
    n = len(bars); out = [(False, None, False, None)]*n
    for j in range(n):
        ci = j-L
        if ci-L >= 0 and ci+L < n:
            c = bars[ci]; w = bars[ci-L:ci]+bars[ci+1:ci+1+L]
            ph = all(c["h"] > x["h"] for x in w); pl = all(c["l"] < x["l"] for x in w)
            out[j] = (ph, c["h"] if ph else None, pl, c["l"] if pl else None)
    return out

def backtest(b5, p, fee_pct=0.05):
    etf = resample(b5, p["entry_tf"]); btf = resample(b5, p["bias_tf"])
    atr = atr_series(etf, 14); closes = [b["c"] for b in etf]
    piv = pivots(etf, p["swing"])
    # HTF биас по EMA, латч предыдущего закрытого HTF-бара
    bclose = [b["c"] for b in btf]; bema = ema(bclose, p["bias_ema"])
    span_b = p["bias_tf"]*60*1000
    bias_at = {}
    for k in range(1, len(btf)):
        bias_at[btf[k]["t"]//span_b] = 1 if bclose[k-1] > bema[k-1] else -1
    # объём: средний по entry-TF
    has_v = "v" in etf[0]
    vmean = []
    if has_v:
        acc = []
        for b in etf:
            acc.append(b["v"]); vmean.append(sum(acc[-50:])/min(len(acc), 50))
    vmult = p.get("vol_mult", 0.0)
    tol = p["pool_tol"]

    sell_pools = []  # пулы под лоями (sell-side liq): {price,touches}
    buy_pools = []   # пулы над хаями (buy-side liq)
    eq = 500.0; START = eq; pos = None; trades = []; eqc = [eq]; fee = fee_pct/100

    for i in range(2, len(etf)):
        bar = etf[i]
        # обновление пулов из подтверждённых пивотов
        ph, phv, pl, plv = piv[i]
        if pl and plv is not None:
            m = [x for x in sell_pools if abs(x["price"]-plv)/plv < tol]
            if m: m[0]["touches"] += 1; m[0]["price"] = (m[0]["price"]+plv)/2
            else: sell_pools.append({"price": plv, "touches": 1})
        if ph and phv is not None:
            m = [x for x in buy_pools if abs(x["price"]-phv)/phv < tol]
            if m: m[0]["touches"] += 1; m[0]["price"] = (m[0]["price"]+phv)/2
            else: buy_pools.append({"price": phv, "touches": 1})
        sell_pools = sell_pools[-40:]; buy_pools = buy_pools[-40:]

        # управление позицией
        if pos is not None:
            h, l = bar["h"], bar["l"]; s = pos["s"]; ex = None
            if (l <= pos["sl"]) if s == 1 else (h >= pos["sl"]): ex = pos["sl"]
            elif (h >= pos["tp"]) if s == 1 else (l <= pos["tp"]): ex = pos["tp"]
            if ex is not None:
                pnl = (ex-pos["e"])*pos["q"]*s - pos["q"]*ex*fee - pos["entry_cost"]
                eq += (ex-pos["e"])*pos["q"]*s - pos["q"]*ex*fee
                trades.append(pnl); pos = None

        if pos is None and atr[i] > 0:
            bias = bias_at.get(bar["t"]//span_b, 0)
            volok = (not (vmult > 0)) or (has_v and vmean[i] > 0 and bar["v"] > vmult*vmean[i])
            sig = 0; sl = tp = None
            if bias == 1:
                # ищем sell-side пул ниже, который только что снят и реклеймнут
                below = [x for x in sell_pools if x["price"] < closes[i-1]]
                if below:
                    pool = max(below, key=lambda x: x["price"])  # ближайший снизу
                    if bar["l"] < pool["price"] and bar["c"] > pool["price"] and volok:
                        sig = 1; e = bar["c"]; sl = bar["l"]-p["sl_buf_atr"]*atr[i]
                        above = [x for x in buy_pools if x["price"] > e]
                        tp = min(above, key=lambda x: x["price"])["price"] if above and p["pool_tp"] \
                             else e+(e-sl)*p["rr"]
            elif bias == -1:
                above = [x for x in buy_pools if x["price"] > closes[i-1]]
                if above:
                    pool = min(above, key=lambda x: x["price"])
                    if bar["h"] > pool["price"] and bar["c"] < pool["price"] and volok:
                        sig = -1; e = bar["c"]; sl = bar["h"]+p["sl_buf_atr"]*atr[i]
                        below = [x for x in sell_pools if x["price"] < e]
                        tp = max(below, key=lambda x: x["price"])["price"] if below and p["pool_tp"] \
                             else e-(sl-e)*p["rr"]
            if sig != 0 and tp is not None:
                dist = abs(e-sl)
                if dist > 0 and (sig == 1 and tp > e or sig == -1 and tp < e):
                    if abs(tp-e)/dist >= p.get("min_rr", 1.0):   # минимальный R:R до пула
                        q = min(eq*0.03/dist, eq*5.0/e); ec = q*e*fee; eq -= ec
                        pos = {"s": sig, "e": e, "sl": sl, "tp": tp, "q": q, "entry_cost": ec}
        eqc.append(eq)

    wins = [t for t in trades if t > 0]
    gp = sum(t for t in trades if t > 0); gl = -sum(t for t in trades if t < 0)
    pf = gp/gl if gl > 0 else (99 if gp > 0 else 0)
    peak = -1e9; mdd = 0
    for e in eqc: peak = max(peak, e); mdd = max(mdd, (peak-e)/peak*100 if peak > 0 else 0)
    return {"trd": len(trades), "pf": pf, "wr": (len(wins)/len(trades)*100 if trades else 0),
            "eq": eq, "roi": (eq/START-1)*100, "mdd": mdd}
