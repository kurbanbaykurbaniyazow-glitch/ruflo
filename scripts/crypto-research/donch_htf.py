#!/usr/bin/env python3
"""Donchian на старших ТФ (4H, 1D) с издержками — снижаем cost-drag реже торгуя."""
import json, os
from alt import resample, sig_donchian
from donch import engine

ASSETS = {"BTC": "okx_btc_max.json", "ETH": "okx_eth_max.json", "SOL": "okx_sol_max.json"}
RAW = {k: json.load(open(v)) for k, v in ASSETS.items() if os.path.exists(v)}
CFG = dict(lookback=20, sl_atr=2.0, rr=3.0, trail=3.0)
FEE = 0.05

for tf_min, tf_name in [(240, "4H"), (1440, "1D")]:
    print(f"\n===== Donchian {tf_name} (lookback=20) | издержки {FEE}%/сторону | $500/5x/3% =====")
    print(f"{'актив':10} {'roi':>7} {'pf':>5} {'wr':>4} {'trd':>4} {'итог$':>7} {'maxDD%':>6}")
    for name, raw in RAW.items():
        bars = resample(raw, tf_min); n = len(bars); t = n//3
        for lbl, seg in [("весь", bars)] + [(f"ф{i+1}", bars[i*t:(i+1)*t]) for i in range(3)]:
            r = engine(seg, CFG, FEE)
            print(f"{name+' '+lbl:10} {r['roi']:+6.0f}% {r['pf']:5.2f} {r['wr']:4.0f} {r['trd']:4d} ${r['eq']:6.0f} {r['mdd']:5.0f}%")
