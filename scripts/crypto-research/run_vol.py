import json
from engine_liq import backtest
D={k:json.load(open(f"v_{k.lower()}.json")) for k in ["BTC","ETH","SOL"]}
def split(b): s=int(len(b)*0.6); return b[:s],b[s:]
# лучшие структурные базы из теста без объёма
bases={
 "1H/4H": dict(entry_tf=60,bias_tf=240,swing=5,bias_ema=50,pool_tol=0.0015,sl_buf_atr=0.5,rr=2.0,pool_tp=True,min_rr=1.5),
 "4H/1D": dict(entry_tf=240,bias_tf=1440,swing=4,bias_ema=50,pool_tol=0.0020,sl_buf_atr=0.5,rr=2.0,pool_tp=True,min_rr=1.5),
}
print(f"{'база':6} {'vol×':>5} | {'BTC tr':>9} | {'BTC OOS':>13} | {'ETH all':>11} | {'SOL all':>11}")
print("-"*72)
for bname,base in bases.items():
    for vm in [0.0,1.3,1.7,2.2]:
        p=dict(base,vol_mult=vm)
        tr,te=split(D["BTC"])
        rtr=backtest(tr,p); rte=backtest(te,p); re=backtest(D["ETH"],p); rs=backtest(D["SOL"],p)
        print(f"{bname:6} {vm:>5} | {rtr['roi']:+5.0f}% {rtr['pf']:.2f} | {rte['roi']:+5.0f}% {rte['pf']:.2f} t{rte['trd']:<3} | "
              f"{re['roi']:+5.0f}% {re['pf']:.2f} | {rs['roi']:+5.0f}% {rs['pf']:.2f}")
