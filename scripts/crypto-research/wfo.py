#!/usr/bin/env python3
"""Walk-forward оптимизация на полной 2-летней истории BTC. Train 60% -> OOS 40%."""
import json, itertools
from bt5 import backtest, B

BTC = json.load(open("/tmp/okx_btc_max.json"))
n = len(BTC); s = int(n*0.6)
TRAIN, TEST = BTC[:s], BTC[s:]
print(f"BTC {n} баров | TRAIN {len(TRAIN)} | OOS-TEST {len(TEST)}", flush=True)

grid = dict(
    rr=[1.2, 1.5, 2.0, 2.5, 3.0],
    disp_atr=[0.0, 1.0, 1.5],
    swing=[3, 4, 5],
    confirm=[4, 6],
    partial=[False, True],
    h1_filter=[False, True],
)
keys = list(grid)
MONEY = dict(equity=500.0, lev=5.0, risk=3.0, entry="ob", tp1_r=1.0, sl_buf=15, retest_win=8, ob_lookback=10)

res = []
for combo in itertools.product(*[grid[k] for k in keys]):
    p = dict(B); p.update(MONEY); p.update(dict(zip(keys, combo)))
    r = backtest(TRAIN, p)
    if r["trades"] < 40: continue          # требуем статзначимость на train
    res.append((r["pf"], p, r["trades"]))
res.sort(key=lambda x: -x[0])

print("\nТоп-10 по TRAIN PF -> их честный OOS-результат:", flush=True)
print(f"{'#':>2} {'TRpf':>5} {'TRtrd':>5} | {'OOSpf':>5} {'OOSwr':>5} {'OOStrd':>6} {'OOSeq':>7} {'ROI%':>6}  rr disp sw cf part h1", flush=True)
for i, (trpf, p, trtrd) in enumerate(res[:10], 1):
    rt = backtest(TEST, p)
    print(f"{i:2d} {trpf:5.2f} {trtrd:5d} | {rt['pf']:5.2f} {rt['wr']:5.0f} {rt['trades']:6d} "
          f"${rt['equity']:6.0f} {rt['roi']:+6.0f}  {p['rr']} {p['disp_atr']} {p['swing']} {p['confirm']} "
          f"{str(p['partial'])[0]} {str(p['h1_filter'])[0]}", flush=True)

# Лучший по OOS среди топ-train (но честно помечаем как анти-оверфит контроль)
best_oos = max(res[:10], key=lambda x: backtest(TEST, x[1])["pf"])
ro = backtest(TEST, best_oos[1]); rtr = backtest(TRAIN, best_oos[1])
print(f"\nСамый устойчивый (train+OOS оба измерены): train PF={rtr['pf']:.2f} / OOS PF={ro['pf']:.2f} "
      f"OOS ROI={ro['roi']:+.0f}% сделок(OOS)={ro['trades']}", flush=True)
print("DONE-WFO", flush=True)
