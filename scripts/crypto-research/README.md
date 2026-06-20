# Crypto Volk SMC — Backtest Research Harness

Полный набор движков и данных-фетчеров для исследования SMC/ICT торговых стратегий.
Отчёт с результатами и вердиктом: [`docs/crypto-volk-strategy-research.md`](../../docs/crypto-volk-strategy-research.md).

## Требования
Python 3.11+, без внешних зависимостей (только стандартная библиотека).

## 1. Скачать данные (≈2 года 5m, OKX, публичный API)

```bash
python3 fetch_max.py    # OHLC -> okx_btc_max.json / okx_eth_max.json / okx_sol_max.json
python3 fetch_vol.py    # OHLC + объём -> v_btc.json / v_eth.json / v_sol.json
```
Данные (~100 МБ) намеренно не в репозитории — регенерируются скриптами.
По умолчанию пути в движках указывают на `/tmp/`; при локальном запуске поправьте пути или положите json рядом.

## 2. Движки стратегий

| Файл | Модель |
|---|---|
| `bt.py` | Ядро: детекция структуры (pivots/CHoCH), ATR, ресемпл ТФ |
| `bt5.py` | SMC CHoCH 5m→15m + OB-ретест + фильтры (денежная модель параметризуема) |
| `wfo.py` | Walk-forward оптимизация SMC (train/OOS) |
| `alt.py` | Альт-классы: Donchian breakout, EMA-cross, RSI mean-revert |
| `donch.py`, `donch_htf.py` | Трендследящий Donchian + анализ чувствительности к издержкам |
| `engine_liq.py`, `run_liq.py`, `run_vol.py` | MTF-биас + пулы ликвидности + объём |
| `topdown.py` | Top-down ICT: 1D тренд → OB/FVG (4H/1H) → CHoCH/BOS (15m) |
| `smc_v2_ob.pine` | Pine Script v6 реализация SMC-варианта (для TradingView) |

## 3. Запуск
```bash
python3 wfo.py        # walk-forward на 2 годах BTC
python3 alt.py        # сравнение альт-классов
python3 donch_htf.py  # трендследящий на 4H/1D с издержками
python3 topdown.py    # top-down ICT MTF модель
```

## Денежная модель
Депозит $500, плечо 5x, риск 3%/сделку (компаундинг), издержки 0.05%/сторону.
Все прогоны — с walk-forward (train 60% / OOS 40%) и кросс-актив проверкой.

## Главный вывод
Устойчивого эджа с PF ≥ 2.5 на интрадей-SMC не найдено (7 классов стратегий, 2 года, 3 актива).
Реалистичный потолок робастной системы — PF ~1.2–1.4 (трендследящий, старшие ТФ). Подробности в отчёте.
