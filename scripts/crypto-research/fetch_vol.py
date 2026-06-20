import json, urllib.request, time
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
            time.sleep(1); continue
        data=d.get("data",[])
        if not data:
            empties+=1
            if empties>=3: break
            time.sleep(0.5); continue
        empties=0
        for r in data: rows[int(r[0])]=r
        after=data[-1][0]; time.sleep(0.08)
        if i%100==0: print(f"  {inst}: page {i}, {len(rows)}",flush=True)
    out=[{"t":int(rows[t][0]),"o":float(rows[t][1]),"h":float(rows[t][2]),
          "l":float(rows[t][3]),"c":float(rows[t][4]),"v":float(rows[t][5])} for t in sorted(rows)]
    return out
for inst,fn in [("BTC-USDT","v_btc.json"),("ETH-USDT","v_eth.json"),("SOL-USDT","v_sol.json")]:
    o=fetch(inst); json.dump(o,open(fn,"w")); print(f"{inst}: {len(o)} баров с объёмом",flush=True)
print("DONE-VOL",flush=True)
