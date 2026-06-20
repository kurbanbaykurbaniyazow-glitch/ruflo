#!/usr/bin/env python3
"""Top-down v3: входы как в v2 (1H + 15m-конф), но TP = ГРАНИЦА зоны ликвидности.
TP1 = ближняя 1H OB/FVG зона, TP2 = глобальная 4H зона интереса. Только границы зон."""
import json
from bt import atr_series, market_structure
from topdown import resample, ema, extract_zones

def backtest(b5, p, fee_pct=0.05):
    e1 = resample(b5, 60); e15 = resample(b5, 15)
    d1 = resample(b5, 1440); h4 = resample(b5, 240)
    atr1 = atr_series(e1, 14)
    ms1 = market_structure(e1, p["swing1h"]); ms15 = market_structure(e15, p["swing15"])
    dC = [b["c"] for b in d1]; dE = ema(dC, p["d_ema"]); spanD = 1440*60*1000
    trendD = {d1[k]["t"]//spanD: (1 if dC[k-1] > dE[k-1] else -1) for k in range(1, len(d1))}

    conf = []
    for i in range(len(e15)):
        lastPH = ms15[i][2]; lastPL = ms15[i][3]
        conf.append((e15[i]["t"], lastPH is not None and e15[i]["c"] > lastPH,
                     lastPL is not None and e15[i]["c"] < lastPL))

    z1 = extract_zones(e1, 60, p["disp"])     # зоны 1H (ближние цели)
    z4 = extract_zones(h4, 240, p["disp"])    # зоны 4H (глобальные цели)
    zones_setup = sorted(z1 + z4)             # для входа (POI любой ТФ)
    zi = 0; active = []

    def nearest_border(zlist, ts, price, side, direction, min_dist):
        """граница ближайшей зоны нужной стороны, но не ближе min_dist (фильтр качества R:R)."""
        best = None
        for vf, lo, hi, sd in zlist:
            if vf > ts or sd != side: continue
            border = lo if direction == 1 else hi   # near edge со стороны подхода цены
            if direction == 1 and border-price >= min_dist:
                if best is None or border < best: best = border
            elif direction == -1 and price-border >= min_dist:
                if best is None or border > best: best = border
        return best

    eq = 500.0; START = eq; pos = None; trades = []; eqc = [eq]; fee = fee_pct/100
    span1 = 60*60*1000; cwin = p["conf_win"]*15*60*1000; ci = 0
    tp_hit_zone = 0; tp_fallback = 0

    for i in range(2, len(e1)):
        bar = e1[i]; t = bar["t"]; tend = t+span1
        while zi < len(zones_setup) and zones_setup[zi][0] <= t:
            active.append(list(zones_setup[zi])); zi += 1
        active = [z for z in active if (t-z[0]) < p["zone_life"]*span1]

        if pos is not None:
            h, l = bar["h"], bar["l"]; s = pos["s"]; closed = False
            # стоп
            if (l <= pos["sl"]) if s == 1 else (h >= pos["sl"]):
                px = pos["sl"]; eq += (px-pos["e"])*pos["qr"]*s - pos["qr"]*px*fee
                pos["real"] += (px-pos["e"])*pos["qr"]*s; trades.append(pos["real"]); pos = None; closed = True
            # TP1 (1H зона) — частичная фиксация 50% + БУ
            if not closed and not pos["tp1d"] and pos["tp1"] is not None:
                if (h >= pos["tp1"]) if s == 1 else (l <= pos["tp1"]):
                    half = pos["q"]*0.5; eq += (pos["tp1"]-pos["e"])*half*s - half*pos["tp1"]*fee
                    pos["real"] += (pos["tp1"]-pos["e"])*half*s; pos["qr"] -= half
                    pos["tp1d"] = True; pos["sl"] = pos["e"]
            # остаток: финальная цель = глобальный 4H уровень (tp2), активна если use_tp2
            if not closed and p.get("use_tp2", True):
                if (h >= pos["tp2"]) if s == 1 else (l <= pos["tp2"]):
                    px = pos["tp2"]; eq += (px-pos["e"])*pos["qr"]*s - pos["qr"]*px*fee
                    pos["real"] += (px-pos["e"])*pos["qr"]*s; trades.append(pos["real"]); pos = None; closed = True
            # после TP1: двигаем стоп ПО СТРУКТУРЕ — за каждый новый откат (swing low/high 1H)
            if not closed and p.get("struct_trail") and pos["tp1d"]:
                lpl = ms1[i][3]; lph = ms1[i][2]
                if s == 1 and lpl is not None:
                    ns = lpl - p["sl_buf"]*atr1[i]
                    if ns > pos["sl"]: pos["sl"] = ns
                elif s == -1 and lph is not None:
                    ns = lph + p["sl_buf"]*atr1[i]
                    if ns < pos["sl"]: pos["sl"] = ns
            # (опц.) ATR-трейлинг — выключен по умолчанию
            if not closed and p.get("runner_trail") and pos["tp1d"]:
                tr = p["runner_trail"]*atr1[i]
                pos["sl"] = max(pos["sl"], bar["c"]-tr) if s == 1 else min(pos["sl"], bar["c"]+tr)

        if pos is None and atr1[i] > 0:
            td = trendD.get(t//spanD, 0)
            lastPH = ms1[i][2]; lastPL = ms1[i][3]
            brkUp = lastPH is not None and bar["c"] > lastPH
            brkDn = lastPL is not None and bar["c"] < lastPL
            cu = cd = False
            while ci < len(conf) and conf[ci][0] <= tend: ci += 1
            for k in range(ci-1, -1, -1):
                if conf[k][0] < tend-cwin: break
                if conf[k][1]: cu = True
                if conf[k][2]: cd = True
            sig = 0; zlo = zhi = None
            if td == 1 and brkUp and cu:
                for z in active:
                    if z[3] == "demand" and bar["l"] <= z[2] and bar["l"] >= z[1]*(1-p["tag_tol"]):
                        sig = 1; zlo, zhi = z[1], z[2]; break
            elif td == -1 and brkDn and cd:
                for z in active:
                    if z[3] == "supply" and bar["h"] >= z[1] and bar["h"] <= z[2]*(1+p["tag_tol"]):
                        sig = -1; zlo, zhi = z[1], z[2]; break
            if sig != 0:
                e = bar["c"]; sl = zlo-p["sl_buf"]*atr1[i] if sig == 1 else zhi+p["sl_buf"]*atr1[i]
                dist = abs(e-sl)
                opp = "supply" if sig == 1 else "demand"
                mind = dist*p["min_tp_rr"]                  # зона должна давать >= min_tp_rr R
                tp1 = nearest_border(z1, t, e, opp, sig, mind)              # ближняя 1H зона
                tp2 = nearest_border(z4, t, e, opp, sig, dist*p["min_tp2_rr"])  # глобальная 4H зона
                # TP1: 1H зона; если нет — берём 4H. TP2: 4H зона; если нет — дальняя 1H.
                if tp1 is None: tp1 = tp2
                if tp2 is None and tp1 is not None:
                    tp2 = nearest_border(z1, t, (tp1+sig*dist), opp, sig, dist*p["min_tp2_rr"]) or tp1
                # вход ТОЛЬКО если есть валидная зональная цель (без RR-fallback)
                if tp1 is not None and tp2 is not None:
                    if sig == 1 and tp2 < tp1: tp1, tp2 = tp2, tp1
                    if sig == -1 and tp2 > tp1: tp1, tp2 = tp2, tp1
                    if dist > 0 and ((tp1-e)*sig > 0):
                        tp_hit_zone += 1
                        q = min(eq*0.03/dist, eq*5.0/e); eq -= q*e*fee
                        pos = {"s": sig, "e": e, "sl": sl, "tp1": tp1, "tp2": tp2,
                               "q": q, "qr": q, "real": 0.0, "tp1d": False}
        eqc.append(eq)

    gp = sum(x for x in trades if x > 0); gl = -sum(x for x in trades if x < 0)
    pf = gp/gl if gl > 0 else (99 if gp > 0 else 0)
    wins = sum(1 for x in trades if x > 0)
    peak = -1e9; mdd = 0
    for e in eqc: peak = max(peak, e); mdd = max(mdd, (peak-e)/peak*100 if peak > 0 else 0)
    return {"trd": len(trades), "pf": pf, "wr": (wins/len(trades)*100 if trades else 0),
            "eq": eq, "roi": (eq/START-1)*100, "mdd": mdd, "zone%": (100*tp_hit_zone/max(tp_hit_zone+tp_fallback,1))}

if __name__ == "__main__":
    D = {k: json.load(open(f"/tmp/v_{k.lower()}.json")) for k in ["BTC", "ETH", "SOL"]}
    def split(b): s = int(len(b)*0.6); return b[:s], b[s:]
    P = dict(swing1h=4, swing15=4, d_ema=20, disp=1.0, zone_life=120, tag_tol=0.003,
             sl_buf=0.5, conf_win=8, min_gap=0.001, fallback_rr=3.0)
    print("Зональный TP (1H ближняя / 4H глобальная зона) | вход 1H+15m | $500/5x/3% | изд.0.05%")
    print(f"{'актив/фолд':12} {'roi':>7} {'pf':>5} {'wr':>4} {'trd':>4} {'DD%':>5} {'зон.TP%':>7}")
    for k, b in D.items():
        n = len(b); t = n//3
        for lbl, seg in [("весь", b)] + [(f"ф{i+1}", b[i*t:(i+1)*t]) for i in range(3)]:
            r = backtest(seg, P)
            print(f"{k+' '+lbl:12} {r['roi']:+6.0f}% {r['pf']:5.2f} {r['wr']:4.0f} {r['trd']:4d} {r['mdd']:4.0f}% {r['zone%']:6.0f}%")
