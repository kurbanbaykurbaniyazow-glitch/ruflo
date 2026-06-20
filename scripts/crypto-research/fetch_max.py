import json, urllib.request, time, sys
def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=25) as r: return json.load(r)
def fetch(inst, bar="5m", max_pages=2000):
    rows={}; after=""; empties=0
    for i in range(max_pages):
        url=f"https://www.okx.com/api/v5/market/history-candles?instId={inst}&bar={bar}&limit=100"
        if after: url+=f"&after={after}"
        try: d=get(url)
        except Exception as e:
            print("err",inst,i,e,flush=True); time.sleep(1); continue
        data=d.get("data",[])
        if not data:
            empties+=1
            if empties>=3: break
            time.sleep(0.5); continue
        empties=0
        for r in data: rows[int(r[0])]=r
        after=data[-1][0]; time.sleep(0.08)
        if i%50==0: print(f"  {inst}: page {i}, total {len(rows)}",flush=True)
    out=[{"t":int(rows[t][0]),"o":float(rows[t][1]),"h":float(rows[t][2]),
          "l":float(rows[t][3]),"c":float(rows[t][4])} for t in sorted(rows)]
    return out
from datetime import datetime, timezone
f=lambda ms: datetime.fromtimestamp(ms/1000,timezone.utc).strftime("%Y-%m-%d")
for inst,fn in [("BTC-USDT","okx_btc_max.json"),("ETH-USDT","okx_eth_max.json"),("SOL-USDT","okx_sol_max.json")]:
    o=fetch(inst); json.dump(o,open(fn,"w"))
    print(f"{inst}: {len(o)} баров, {f(o[0]['t'])}..{f(o[-1]['t'])}",flush=True)
print("DONE",flush=True)
