# Соли THINK-01 (публикуются после итогового отчёта, PREREG §2)
- `rep_salt.txt` — соль повтора (WH 8251–8300), создана заново 25.10.2026 до первого вызова оценщиков (DEVIATIONS.md). sha256(соль) = 9ccf6c2435be4246da3d10778a08bac087704ef43c385a96b013df49974fbb10 — то же, что закоммичено в 3d52bca. Опубликована 26.10.2026 после итогового отчёта и совета 36.
- Соль основной выборки (sha256 ffe2f173…) пропала вместе с контейнером до публикации (ERRORS № 91). Правду основной выборки независимо пересчитать нельзя.
- Пересчёт правды повтора: `mkdir -p /root/think_secret_rep && cp salts/rep_salt.txt /root/think_secret_rep/salt.txt`, затем `python3 harness_think.py truth seeds_rep.json WH` (путь задан в `SECRETS` в `harness_think.py`; другой `THINK_SECRET` для этой выборки код не примет).
