#!/usr/bin/env python3
"""Сравнение ВСЕХ вариантов входа по робастному profit factor."""
import json
from bt import market_structure, resample_15m, atr_series

DATA = {k: json.load(open(v)) for k, v in {
    "BTC": "/tmp/okx_5m.json", "ETH": "/tmp/okx_eth_5m.json", "SOL": "/tmp/okx_sol_5m.json"}.items()}

def resample(b5, minutes):
    g = {}
    span = minutes*60*1000
    for b in b5:
        g.setdefault(b["t"]//span, []).append(b)
    out = []
    for k in sorted(g):
        grp = sorted(g[k], key=lambda x: x["t"])
        out.append({"t": k*span, "o": grp[0]["o"], "h": max(x["h"] for x in grp),
                    "l": min(x["l"] for x in grp), "c": grp[-1]["c"]})
    return out

def find_ob(b5, j, side, lookback):
    for k in range(j-1, max(j-1-lookback, 0), -1):
        if side == "L" and b5[k]["c"] < b5[k]["o"]: return b5[k]["h"], b5[k]["l"]
        if side == "S" and b5[k]["c"] > b5[k]["o"]: return b5[k]["l"], b5[k]["h"]
    return None

def backtest(b5, p):
    b15 = resample(b5, 15); b60 = resample(b5, 60)
    ms5 = market_structure(b5, p["swing"]); ms15 = market_structure(b15, p["swing"])
    ms60 = market_structure(b60, p["swing"]); atr5 = atr_series(b5, 14)
    htf_latch = {b15[k]["t"]: (ms15[k-1][0], ms15[k-1][1]) for k in range(1, len(b15))}
    # тренд 1H, латч предыдущего закрытого часа
    span60 = 60*60*1000
    trend60 = {}
    for k in range(1, len(b60)):
        trend60[b60[k]["t"]//span60] = ms60[k-1][4]
    eq = p.get("equity",10000.0); START=eq; fsm = 0; pdir = 0; cnt = 0
    pending = None; pos = None; trades = []; eqc = [eq]
    buf = p["sl_buf"]*0.1
    ruined=False
    market = p.get("entry", "ob") == "market"
    use_h1 = p.get("h1_filter", False)
    disp = p.get("disp_atr", 0.0)

    for j in range(1, len(b5)):
        bar = b5[j]; t = bar["t"]
        ltfUp, ltfDn = ms5[j-1][0], ms5[j-1][1]
        swLow5 = ms5[j][3]; swHigh5 = ms5[j][2]
        isNewHtf = t in htf_latch
        htfUp, htfDn = htf_latch.get(t, (False, False))
        longC = shortC = False
        if fsm == 0 and pos is None and pending is None:
            if ltfUp: fsm, pdir, cnt = 1, 1, 0
            elif ltfDn: fsm, pdir, cnt = 1, -1, 0
        if fsm == 1 and isNewHtf: cnt += 1
        if fsm == 1 and cnt > p["confirm"]: fsm, pdir = 0, 0
        if fsm == 1:
            if pdir == 1 and ltfDn: fsm, pdir = 0, 0
            elif pdir == -1 and ltfUp: fsm, pdir = 0, 0
        if fsm == 1:
            if pdir == 1 and htfUp: fsm = 2; longC = True
            elif pdir == -1 and htfDn: fsm = 2; shortC = True
        if fsm == 2: fsm, pdir = 0, 0

        # фильтры (опц., нарушают правило №2)
        if (longC or shortC):
            if use_h1:
                tr = trend60.get(t//span60, 0)
                if longC and tr < 0: longC = False
                if shortC and tr > 0: shortC = False
            if disp > 0 and atr5[j] > 0 and (bar["h"]-bar["l"]) < disp*atr5[j]:
                longC = shortC = False

        # управление позицией
        if pos is not None:
            h, l = bar["h"], bar["l"]; side = pos["side"]; ra = pos["ra"]; closed = False
            hit_sl = (l <= pos["sl"]) if side == "L" else (h >= pos["sl"])
            if hit_sl:
                px = pos["sl"]; pnl = (px-pos["e"])*pos["qr"]*(1 if side == "L" else -1)
                pos["real"] += pnl; eq += pnl; trades.append({"pnl": pos["real"]}); pos = None; closed = True
                if eq<=START*0.1: ruined=True
            if not closed and p["partial"] and not pos["tp1d"]:
                hit = (h >= pos["tp1"]) if side == "L" else (l <= pos["tp1"])
                if hit:
                    half = pos["q"]*0.5; pnl = (pos["tp1"]-pos["e"])*half*(1 if side == "L" else -1)
                    pos["real"] += pnl; eq += pnl; pos["qr"] -= half; pos["tp1d"] = True; pos["sl"] = pos["e"]
            if not closed:
                hit = (h >= pos["tp"]) if side == "L" else (l <= pos["tp"])
                if hit:
                    px = pos["tp"]; pnl = (px-pos["e"])*pos["qr"]*(1 if side == "L" else -1)
                    pos["real"] += pnl; eq += pnl; trades.append({"pnl": pos["real"]}); pos = None; closed = True

        # вход
        if market and (longC or shortC) and pos is None:
            side = "L" if longC else "S"
            ref = bar["c"]; sl = (swLow5-buf) if side == "L" else (swHigh5+buf)
            if sl is not None and not (sl != sl):
                dist = (ref-sl) if side == "L" else (sl-ref)
                if dist > 0:
                    ra = eq*p["risk"]/100; qty = min(ra/dist, eq*p["lev"]/ref)
                    tp = ref+dist*p["rr"]*(1 if side == "L" else -1)
                    tp1 = ref+dist*p["tp1_r"]*(1 if side == "L" else -1)
                    pos = {"side": side, "e": ref, "sl": sl, "tp": tp, "tp1": tp1, "q": qty,
                           "qr": qty, "ra": ra, "real": 0.0, "tp1d": False}
        elif not market:
            if pending is not None and pos is None:
                pending["age"] += 1; side = pending["side"]
                fill = (bar["l"] <= pending["e"]) if side == "L" else (bar["h"] >= pending["e"])
                if fill:
                    e = pending["e"]; sl = pending["sl"]; dist = (e-sl) if side == "L" else (sl-e)
                    if dist > 0:
                        ra = eq*p["risk"]/100; qty = min(ra/dist, eq*p["lev"]/e)
                        tp = e+dist*p["rr"]*(1 if side == "L" else -1)
                        tp1 = e+dist*p["tp1_r"]*(1 if side == "L" else -1)
                        pos = {"side": side, "e": e, "sl": sl, "tp": tp, "tp1": tp1, "q": qty,
                               "qr": qty, "ra": ra, "real": 0.0, "tp1d": False}
                    pending = None
                elif pending["age"] > p["retest_win"]: pending = None
            if (longC or shortC) and pos is None and pending is None:
                side = "L" if longC else "S"; ob = find_ob(b5, j, side, p["ob_lookback"])
                if ob is not None:
                    e, sr = ob; sl = (sr-buf) if side == "L" else (sr+buf)
                    pending = {"side": side, "e": e, "sl": sl, "age": 0}
        eqc.append(eq)

    gp = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gl = sum(-t["pnl"] for t in trades if t["pnl"] < 0)
    pf = gp/gl if gl > 0 else (99.0 if gp > 0 else 0)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    peak = -1e9; mdd = 0
    for e in eqc: peak = max(peak, e); mdd = max(mdd, peak-e)
    roi=(eq/START-1)*100
    return {"trades": len(trades), "pf": pf, "wr": (wins/len(trades)*100 if trades else 0), "net": eq-START, "equity": eq, "roi": roi, "mdd": mdd, "ruined": ruined}

B = dict(swing=4, confirm=6, rr=4.0, tp1_r=1.0, sl_buf=15, risk=1.0, lev=3.0,
         partial=False, retest_win=8, ob_lookback=10)

VARIANTS = {
    "1. Market-вход (CHoCH сырой)":      dict(B, entry="market"),
    "2. OB-ретест":                      dict(B, entry="ob"),
    "3. OB + фильтр тренда 1H":          dict(B, entry="ob", h1_filter=True),
    "4. OB + фильтр импульса 1.0ATR":    dict(B, entry="ob", disp_atr=1.0),
    "5. OB + 1H + импульс":              dict(B, entry="ob", h1_filter=True, disp_atr=1.0),
    "6. Market + 1H + импульс":          dict(B, entry="market", h1_filter=True, disp_atr=1.0),
}

if __name__ == "__main__":
    print("Робастный замер PF: BTC H1/H2 (walk-forward) + ETH/SOL (кросс-актив OOS)\n")
    rows = []
    for name, p in VARIANTS.items():
        btc = DATA["BTC"]; h = len(btc)//2
        r_h1 = backtest(btc[:h], p); r_h2 = backtest(btc[h:], p)
        r_eth = backtest(DATA["ETH"], p); r_sol = backtest(DATA["SOL"], p)
        pfs = [r_h1["pf"], r_h2["pf"], r_eth["pf"], r_sol["pf"]]
        tot_trd = r_h1["trades"]+r_h2["trades"]+r_eth["trades"]+r_sol["trades"]
        robust = min(pfs)          # худший случай = мера устойчивости
        avg = sum(pfs)/4
        rows.append((robust, avg, name, pfs, tot_trd))
    rows.sort(key=lambda x: -x[0])
    print(f"{'вариант':32} | {'BTCh1':>5} {'BTCh2':>5} {'ETH':>5} {'SOL':>5} | {'min':>4} {'avg':>4} {'trd':>4}")
    print("-"*92)
    for robust, avg, name, pfs, trd in rows:
        print(f"{name:32} | {pfs[0]:5.2f} {pfs[1]:5.2f} {pfs[2]:5.2f} {pfs[3]:5.2f} | {robust:4.2f} {avg:4.2f} {trd:4d}")
    print(f"\nПОБЕДИТЕЛЬ по худшему PF (робастность): {rows[0][2]}")
