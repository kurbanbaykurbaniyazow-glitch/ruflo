#!/usr/bin/env python3
"""Donchian breakout 1H: жёсткая проверка робастности + реальные издержки."""
import json, os
from alt import resample, sig_donchian
from bt import atr_series

def engine(bars, p, fee_pct):
    atr = atr_series(bars, 14); closes = [b["c"] for b in bars]
    ctx = sig_donchian(bars, atr, closes, p)
    eq = 500.0; START = eq; pos = None; trades = []; eqc = [eq]; fee = fee_pct/100
    for i in range(2, len(bars)):
        bar = bars[i]
        if pos is not None:
            h, l = bar["h"], bar["l"]; s = pos["s"]; closed = False
            hit_sl = (l <= pos["sl"]) if s == 1 else (h >= pos["sl"])
            ex = None
            if hit_sl: ex = pos["sl"]
            elif (h >= pos["tp"]) if s == 1 else (l <= pos["tp"]): ex = pos["tp"]
            if ex is not None:
                pnl = (ex-pos["e"])*pos["q"]*s - pos["q"]*ex*fee   # комиссия на выход
                eq += pnl; trades.append(pnl); pos = None; closed = True
            if pos is not None and p.get("trail", 0) > 0:
                if s == 1: pos["sl"] = max(pos["sl"], bar["c"]-p["trail"]*atr[i])
                else: pos["sl"] = min(pos["sl"], bar["c"]+p["trail"]*atr[i])
        if pos is None and atr[i] > 0 and ctx[i] != 0:
            sg = ctx[i]; e = bar["c"]; sl = e - sg*p["sl_atr"]*atr[i]; dist = abs(e-sl)
            if dist > 0:
                q = min(eq*0.03/dist, eq*5.0/e)
                eq -= q*e*fee   # комиссия на вход
                pos = {"s": sg, "e": e, "sl": sl, "tp": e+sg*p["sl_atr"]*p["rr"]*atr[i], "q": q}
        eqc.append(eq)
    wins = [t for t in trades if t > 0]
    gp = sum(t for t in trades if t > 0); gl = -sum(t for t in trades if t < 0)
    pf = gp/gl if gl > 0 else (99 if gp > 0 else 0)
    peak = -1e9; mdd = 0
    for e in eqc: peak = max(peak, e); mdd = max(mdd, (peak-e)/peak*100 if peak > 0 else 0)
    return {"trd": len(trades), "pf": pf, "wr": (len(wins)/len(trades)*100 if trades else 0),
            "eq": eq, "roi": (eq/START-1)*100, "mdd": mdd}

ASSETS = {"BTC": "okx_btc_max.json", "ETH": "okx_eth_max.json", "SOL": "okx_sol_max.json"}
DATA = {k: resample(json.load(open(v)), 60) for k, v in ASSETS.items() if os.path.exists(v)}

CFG = dict(lookback=40, sl_atr=2.0, rr=3.0, trail=3.0)   # фиксированный, НЕ подбираем под фолд
print(f"Donchian 1H, конфиг={CFG} | депо $500 / 5x / риск 3%")
for fee in [0.0, 0.05, 0.10]:
    print(f"\n--- издержки {fee}%/сторону (комиссия+проскальзывание) ---")
    print(f"{'актив':10} {'roi':>7} {'pf':>5} {'wr':>4} {'trd':>4} {'итог$':>7} {'maxDD%':>6}")
    for name, bars in DATA.items():
        n = len(bars); t = n//3
        for lbl, seg in [("весь", bars)] + [(f"ф{i+1}", bars[i*t:(i+1)*t]) for i in range(3)]:
            r = engine(seg, CFG, fee)
            print(f"{name+' '+lbl:10} {r['roi']:+6.0f}% {r['pf']:5.2f} {r['wr']:4.0f} {r['trd']:4d} ${r['eq']:6.0f} {r['mdd']:5.0f}%")
