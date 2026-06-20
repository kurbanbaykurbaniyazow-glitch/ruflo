#!/usr/bin/env python3
"""Top-down v2: 1D тренд -> POI(OB+FVG) 4H/1H -> ВХОД на 1H (CHoCH/BOS),
15m = только подтверждение разворота в ту же сторону. Реже сделки -> меньше издержек."""
import json
from bt import atr_series, market_structure
from topdown import resample, ema, extract_zones

def backtest(b5, p, fee_pct=0.05):
    e1 = resample(b5, 60)          # ВХОД на 1H
    e15 = resample(b5, 15)         # подтверждение
    d1 = resample(b5, 1440); h4 = resample(b5, 240)
    atr1 = atr_series(e1, 14)
    ms1 = market_structure(e1, p["swing1h"])
    ms15 = market_structure(e15, p["swing15"])

    # 1D тренд (латч пред. дня)
    dC = [b["c"] for b in d1]; dE = ema(dC, p["d_ema"]); spanD = 1440*60*1000
    trendD = {d1[k]["t"]//spanD: (1 if dC[k-1] > dE[k-1] else -1) for k in range(1, len(d1))}

    # 15m разворотные подтверждения: брейк структуры в каждую сторону
    conf = []   # (t, up, dn)
    for i in range(len(e15)):
        lastPH = ms15[i][2]; lastPL = ms15[i][3]
        up = lastPH is not None and e15[i]["c"] > lastPH
        dn = lastPL is not None and e15[i]["c"] < lastPL
        conf.append((e15[i]["t"], up, dn))

    # зоны 4H + 1H
    zones = extract_zones(h4, 240, p["disp"]) + extract_zones(e1, 60, p["disp"])
    zones.sort(); zi = 0; active = []

    eq = 500.0; START = eq; pos = None; trades = []; eqc = [eq]; fee = fee_pct/100
    span1 = 60*60*1000; cwin = p["conf_win"]*15*60*1000
    ci = 0
    for i in range(2, len(e1)):
        bar = e1[i]; t = bar["t"]; tend = t+span1
        while zi < len(zones) and zones[zi][0] <= t:
            active.append(list(zones[zi])); zi += 1
        active = [z for z in active if (t-z[0]) < p["zone_life"]*span1]

        if pos is not None:
            h, l = bar["h"], bar["l"]; s = pos["s"]; ex = None
            if (l <= pos["sl"]) if s == 1 else (h >= pos["sl"]): ex = pos["sl"]
            elif (h >= pos["tp"]) if s == 1 else (l <= pos["tp"]): ex = pos["tp"]
            if ex is not None:
                eq += (ex-pos["e"])*pos["q"]*s - pos["q"]*ex*fee; trades.append((ex-pos["e"])*s*pos["q"]); pos = None

        if pos is None and atr1[i] > 0:
            td = trendD.get(t//spanD, 0)
            lastPH = ms1[i][2]; lastPL = ms1[i][3]
            brkUp = lastPH is not None and bar["c"] > lastPH     # CHoCH/BOS на 1H
            brkDn = lastPL is not None and bar["c"] < lastPL
            # 15m подтверждение в окне до закрытия 1H-бара
            conf_up = conf_dn = False
            while ci < len(conf) and conf[ci][0] <= tend:
                ci += 1
            for k in range(ci-1, -1, -1):
                if conf[k][0] < tend-cwin: break
                if conf[k][1]: conf_up = True
                if conf[k][2]: conf_dn = True
            sig = 0; zlo = zhi = None
            if td == 1 and brkUp and conf_up:
                for z in active:
                    if z[3] == "demand" and bar["l"] <= z[2] and bar["l"] >= z[1]*(1-p["tag_tol"]):
                        sig = 1; zlo, zhi = z[1], z[2]; break
            elif td == -1 and brkDn and conf_dn:
                for z in active:
                    if z[3] == "supply" and bar["h"] >= z[1] and bar["h"] <= z[2]*(1+p["tag_tol"]):
                        sig = -1; zlo, zhi = z[1], z[2]; break
            if sig != 0:
                e = bar["c"]; sl = zlo-p["sl_buf"]*atr1[i] if sig == 1 else zhi+p["sl_buf"]*atr1[i]
                dist = abs(e-sl)
                if dist > 0:
                    tp = e+sig*dist*p["rr"]; q = min(eq*0.03/dist, eq*5.0/e); eq -= q*e*fee
                    pos = {"s": sig, "e": e, "sl": sl, "tp": tp, "q": q}
        eqc.append(eq)

    gp = sum(x for x in trades if x > 0); gl = -sum(x for x in trades if x < 0)
    pf = gp/gl if gl > 0 else (99 if gp > 0 else 0)
    wins = sum(1 for x in trades if x > 0)
    peak = -1e9; mdd = 0
    for e in eqc: peak = max(peak, e); mdd = max(mdd, (peak-e)/peak*100 if peak > 0 else 0)
    return {"trd": len(trades), "pf": pf, "wr": (wins/len(trades)*100 if trades else 0),
            "eq": eq, "roi": (eq/START-1)*100, "mdd": mdd}

if __name__ == "__main__":
    D = {k: json.load(open(f"/tmp/v_{k.lower()}.json")) for k in ["BTC", "ETH", "SOL"]}
    def split(b): s = int(len(b)*0.6); return b[:s], b[s:]
    BASE = dict(swing1h=4, swing15=4, d_ema=20, disp=0.5, zone_life=120,
                tag_tol=0.003, sl_buf=0.5, rr=3.0, conf_win=8)
    cfgs = {
        "1H-вход rr3 (15m-конф)": dict(BASE),
        "rr4 disp1.0": dict(BASE, rr=4.0, disp=1.0),
        "rr2": dict(BASE, rr=2.0),
        "dEMA50 rr3": dict(BASE, d_ema=50),
    }
    print("Вход 1H + подтверждение разворота 15m | $500/5x/3% | издержки 0.05%")
    print(f"{'конфиг':22} | {'BTC train':>13} | {'BTC OOS':>15} | {'ETH all':>12} | {'SOL all':>12}")
    print("-"*84)
    for name, p in cfgs.items():
        tr, te = split(D["BTC"])
        a = backtest(tr, p); b = backtest(te, p); e = backtest(D["ETH"], p); s = backtest(D["SOL"], p)
        print(f"{name:22} | {a['roi']:+5.0f}% pf{a['pf']:.2f} | {b['roi']:+5.0f}% pf{b['pf']:.2f} t{b['trd']:<4}| "
              f"{e['roi']:+5.0f}% pf{e['pf']:.2f} | {s['roi']:+5.0f}% pf{s['pf']:.2f}")
    # диагностика без издержек для лучшего конфига
    print("\nДиагностика без издержек (rr4 disp1.0):")
    p = dict(BASE, rr=4.0, disp=1.0)
    for k, b in D.items():
        r0 = backtest(b, p, 0.0); r1 = backtest(b, p, 0.05)
        print(f"  {k}: fee0 ROI={r0['roi']:+.0f}% (PF{r0['pf']:.2f}) | fee0.05 ROI={r1['roi']:+.0f}% | сделок={r1['trd']} WR={r1['wr']:.0f}%")
