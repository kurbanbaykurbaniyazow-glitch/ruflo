#!/usr/bin/env python3
"""SMC Sequential CHoCH (5m->15m) — backtest harness, порт ядра Pine v6."""
import json
from datetime import datetime, timezone

BARS5 = json.load(open("/tmp/okx_5m.json"))

def resample_15m(b5):
    groups = {}
    for b in b5:
        key = b["t"] // (15*60*1000)
        groups.setdefault(key, []).append(b)
    out = []
    for key in sorted(groups):
        g = sorted(groups[key], key=lambda x: x["t"])
        out.append({"t": key*15*60*1000, "o": g[0]["o"],
                    "h": max(x["h"] for x in g), "l": min(x["l"] for x in g),
                    "c": g[-1]["c"]})
    return out

def market_structure(bars, L):
    """per-bar (chochUp, chochDown, lastPH, lastPL, trend) — строгие пивоты."""
    out = []; lastPH = lastPL = None; trend = 0
    n = len(bars)
    for j in range(n):
        ci = j - L
        if ci - L >= 0 and ci + L < n:
            c = bars[ci]; w = bars[ci-L:ci] + bars[ci+1:ci+1+L]
            if all(c["h"] > x["h"] for x in w): lastPH = c["h"]
            if all(c["l"] < x["l"] for x in w): lastPL = c["l"]
        cl = bars[j]["c"]; up = dn = False; old = trend
        if lastPH is not None and cl > lastPH and trend <= 0:
            up = (old == -1); trend = 1
        if lastPL is not None and cl < lastPL and trend >= 0 and not up:
            dn = (old == 1); trend = -1
        out.append((up, dn, lastPH, lastPL, trend))
    return out

def atr_series(bars, n=14):
    out = []; trs = []; prev = None
    for b in bars:
        tr = b["h"] - b["l"]
        if prev is not None:
            tr = max(tr, abs(b["h"]-prev), abs(b["l"]-prev))
        trs.append(tr); prev = b["c"]
        out.append(sum(trs[-n:]) / min(len(trs), n))
    return out

def backtest(p):
    b5 = BARS5
    b15 = resample_15m(b5)
    ms5 = market_structure(b5, p["swing"])
    ms15 = market_structure(b15, p["swing"])
    atr5 = atr_series(b5, 14)
    disp = p.get("disp_atr", 0.0)   # 0 = фильтр выключен (правило №2 соблюдено)

    # карта: открытие 15m бара -> индекс
    t15_idx = {b["t"]: k for k, b in enumerate(b15)}
    # htf латч: на 5m баре с временем = открытие 15m бара (k) латчим raw-событие бара (k-1)
    htf_latch = {}
    for k in range(1, len(b15)):
        htf_latch[b15[k]["t"]] = (ms15[k-1][0], ms15[k-1][1])

    eq = 10000.0
    fsm = 0; pdir = 0; cnt = 0
    pos = None
    trades = []
    eq_curve = [eq]
    TICK = 0.1; buf = p["sl_buf"] * TICK

    for j in range(1, len(b5)):
        bar = b5[j]; t = bar["t"]
        ltfUp, ltfDown = ms5[j-1][0], ms5[j-1][1]
        swLow5 = ms5[j][3]; swHigh5 = ms5[j][2]
        isNewHtf = t in htf_latch
        htfUp, htfDown = htf_latch.get(t, (False, False))

        longC = shortC = False
        # FSM
        if fsm == 0 and pos is None:
            if ltfUp: fsm, pdir, cnt = 1, 1, 0
            elif ltfDown: fsm, pdir, cnt = 1, -1, 0
        if fsm == 1 and isNewHtf: cnt += 1
        if fsm == 1 and cnt > p["confirm"]: fsm, pdir = 0, 0
        if fsm == 1:
            if pdir == 1 and ltfDown: fsm, pdir = 0, 0
            elif pdir == -1 and ltfUp: fsm, pdir = 0, 0
        if fsm == 1:
            if pdir == 1 and htfUp: fsm = 2; longC = True
            elif pdir == -1 and htfDown: fsm = 2; shortC = True
        if fsm == 2: fsm, pdir = 0, 0

        # --- управление открытой позицией (до возможного нового входа) ---
        if pos is not None:
            h, l = bar["h"], bar["l"]; side = pos["side"]
            risk_amt = pos["risk_amt"]
            closed = False
            # обратный CHoCH 15m — приоритетный выход всей позиции
            if p["exit_rev"] and ((side == "L" and htfDown) or (side == "S" and htfUp)):
                px = bar["c"]
                pnl = (px - pos["entry"]) * pos["qty_rem"] * (1 if side == "L" else -1)
                pos["realized"] += pnl; eq += pnl
                trades.append({"R": pos["realized"]/risk_amt, "pnl": pos["realized"], "reason": "revCHoCH"})
                pos = None; closed = True
            if not closed:
                # порядок внутри бара: сначала стоп (пессимистично), потом цели
                hit_sl = (l <= pos["sl"]) if side == "L" else (h >= pos["sl"])
                if hit_sl:
                    px = pos["sl"]
                    pnl = (px - pos["entry"]) * pos["qty_rem"] * (1 if side == "L" else -1)
                    pos["realized"] += pnl; eq += pnl
                    trades.append({"R": pos["realized"]/risk_amt, "pnl": pos["realized"],
                                   "reason": "SL" if not pos["be"] else "BE"})
                    pos = None; closed = True
            if not closed and p["partial"] and not pos["tp1_done"]:
                hit_tp1 = (h >= pos["tp1"]) if side == "L" else (l <= pos["tp1"])
                if hit_tp1:
                    half = pos["qty"] * 0.5
                    pnl = (pos["tp1"] - pos["entry"]) * half * (1 if side == "L" else -1)
                    pos["realized"] += pnl; eq += pnl
                    pos["qty_rem"] -= half; pos["tp1_done"] = True
                    pos["sl"] = pos["entry"]; pos["be"] = True   # перевод остатка в безубыток
            if not closed:
                hit_tp = (h >= pos["tp"]) if side == "L" else (l <= pos["tp"])
                if hit_tp:
                    px = pos["tp"]
                    pnl = (px - pos["entry"]) * pos["qty_rem"] * (1 if side == "L" else -1)
                    pos["realized"] += pnl; eq += pnl
                    trades.append({"R": pos["realized"]/risk_amt, "pnl": pos["realized"], "reason": "TP"})
                    pos = None; closed = True
            # трейлинг по свингам
            if pos is not None and p["trail"]:
                if pos["side"] == "L" and swLow5 is not None:
                    ns = swLow5 - buf
                    if ns > pos["sl"]: pos["sl"] = ns
                else:
                    if swHigh5 is not None:
                        ns = swHigh5 + buf
                        if ns < pos["sl"]: pos["sl"] = ns

        # --- опциональный фильтр импульса (нарушает правило №2; для сравнения) ---
        if disp > 0 and (longC or shortC):
            body = abs(bar["c"] - bar["o"])
            if atr5[j] > 0 and body < disp * atr5[j]:
                longC = shortC = False   # отсев "вялого" слома

        # --- вход ---
        if longC and pos is None and swLow5 is not None:
            ref = bar["c"]; sl = swLow5 - buf; dist = ref - sl
            if dist > 0:
                risk_amt = eq * p["risk"] / 100.0
                qty = min(risk_amt / dist, eq * p["lev"] / ref)
                pos = {"side": "L", "entry": ref, "sl": sl, "tp": ref + dist*p["rr"],
                       "tp1": ref + dist*p["tp1_r"], "qty": qty, "qty_rem": qty,
                       "risk_amt": risk_amt, "realized": 0.0, "tp1_done": False, "be": False}
        elif shortC and pos is None and swHigh5 is not None:
            ref = bar["c"]; sl = swHigh5 + buf; dist = sl - ref
            if dist > 0:
                risk_amt = eq * p["risk"] / 100.0
                qty = min(risk_amt / dist, eq * p["lev"] / ref)
                pos = {"side": "S", "entry": ref, "sl": sl, "tp": ref - dist*p["rr"],
                       "tp1": ref - dist*p["tp1_r"], "qty": qty, "qty_rem": qty,
                       "risk_amt": risk_amt, "realized": 0.0, "tp1_done": False, "be": False}
        eq_curve.append(eq)

    # метрики
    gp = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gl = sum(-t["pnl"] for t in trades if t["pnl"] < 0)
    wins = [t for t in trades if t["pnl"] > 0]
    pf = gp / gl if gl > 0 else float("inf")
    peak = -1e9; maxdd = 0
    for e in eq_curve:
        peak = max(peak, e); maxdd = max(maxdd, peak - e)
    avgR = sum(t["R"] for t in trades) / len(trades) if trades else 0
    return {"trades": len(trades), "pf": pf, "wr": (len(wins)/len(trades)*100 if trades else 0),
            "net": eq-10000, "maxdd": maxdd, "avgR": avgR,
            "reasons": {r: sum(1 for t in trades if t["reason"] == r) for r in set(t["reason"] for t in trades)}}

BASE = dict(swing=5, confirm=4, rr=2.0, tp1_r=1.0, sl_buf=10, risk=1.0, lev=3.0,
            partial=True, trail=False, exit_rev=True)

if __name__ == "__main__":
    r = backtest(BASE)
    print("=== BASELINE (swing=5, confirm=4, RR=2, partial=50%@1R+BE, exit_rev=on) ===")
    print(f"Сделок: {r['trades']}  PF: {r['pf']:.2f}  Winrate: {r['wr']:.0f}%  "
          f"Net: {r['net']:.0f}  MaxDD: {r['maxdd']:.0f}  avgR: {r['avgR']:.2f}")
    print(f"Выходы: {r['reasons']}")
