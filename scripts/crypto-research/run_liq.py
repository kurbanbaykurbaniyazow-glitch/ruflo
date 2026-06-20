import json
from engine_liq import backtest
D={k:json.load(open(f"okx_{k.lower()}_max.json")) for k in ["BTC","ETH","SOL"]}
def split(b): s=int(len(b)*0.6); return b[:s],b[s:]
BASE=dict(entry_tf=60,bias_tf=240,swing=5,bias_ema=50,pool_tol=0.0015,
          sl_buf_atr=0.5,rr=2.0,pool_tp=True,min_rr=1.5,vol_mult=0.0)
# мини-перебор bias_tf и entry_tf (без p-hacking: 4 разумных сочетания)
configs={
 "1H/4H pool-TP": dict(BASE),
 "1H/1D pool-TP": dict(BASE,bias_tf=1440),
 "4H/1D pool-TP": dict(BASE,entry_tf=240,bias_tf=1440,swing=4),
 "1H/4H rr2 (без pool-TP)": dict(BASE,pool_tp=False),
}
print(f"{'конфиг':24} | {'BTC train':>11} | {'BTC OOS':>15} | {'ETH all':>12} | {'SOL all':>12}")
print("-"*86)
for name,p in configs.items():
    tr,te=split(D["BTC"])
    rtr=backtest(tr,p); rte=backtest(te,p); re=backtest(D["ETH"],p); rs=backtest(D["SOL"],p)
    print(f"{name:24} | {rtr['roi']:+5.0f}% pf{rtr['pf']:.2f} | {rte['roi']:+5.0f}% pf{rte['pf']:.2f} t{rte['trd']:<3} | "
          f"{re['roi']:+5.0f}% pf{re['pf']:.2f} | {rs['roi']:+5.0f}% pf{rs['pf']:.2f}")
