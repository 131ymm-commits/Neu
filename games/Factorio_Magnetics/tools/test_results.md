# Magnetics: результаты автотестов

Запуск 2026-10-01T08:32:03, 147.1 с; Factorio 2.0.77; коммит `1331e10` (с незакоммиченными правками); модули ячеек: smoke, static, production, logistics, power, quality, combat; отдельный прогон катушки: mend; бенчмарк до записи результатов: {'base': 'done at tick 36602', 'bq': 'done at tick 18001', 'be': 'done at tick 1201', 'sa': 'done at tick 36602'}.

Виды записей: **mod** — проверка мода (только они в счёте «прошло / не прошло»); **harness** — самопроверка стенда (разбор спецификации, сканер, наличие прогонов и выгрузок, манифест; провал тоже валит прогон); **info** — справочная запись без проверки (перечислены отдельно в конце).

## Итог по конфигурациям

| | base | bq | be | sa | files |
|---|---|---|---|---|---|
| проверки мода: прошло / не прошло | 3219 / 0 | 2845 / 0 | 2781 / 0 | 3391 / 0 | 724 / 0 |
| из них независимых (ожидание из FINAL_SPEC вручную, из ванили или замер в игре) | 2163 | 1789 | 1725 | 2335 | 724 |
| из них согласованность S4 с expected.lua (тот же файл spec.py, что данные мода) | 1056 | 1056 | 1056 | 1056 | 0 |
| самопроверки стенда: прошло / не прошло | 25 / 0 | 15 / 0 | 15 / 0 | 20 / 0 | 3 / 0 |
| справочные записи | 8 | 3 | 3 | 8 | 0 |

Согласованность с expected.lua ловит расхождение мода с его же сгенерированными данными, но не ошибку в spec.py; те же поля S4 проверяются ещё и независимо (записи «doc …» ячейки и «dump …» / «doc §…» Python), поэтому одно поле может входить в счёт до четырёх раз.

## По тестам

Клетка: проверки мода прошло/не прошло; «ст.» — самопроверки стенда, «спр.» — справочные. `files` — проверки файлов, не зависящие от конфигурации.

| тест | base | bq | be | sa | files |
|---|---|---|---|---|---|
| E1 | 6/0 | — | — | 6/0 | — |
| E2 | 6/0 | — | — | 6/0 | — |
| E3 | 18/0 | — | — | 18/0 | — |
| E4 | 7/0 | — | — | 7/0 | — |
| E5 | 5/0 | — | — | 5/0 | — |
| E6 | 2/0 | 5/0 | — | 7/0 | — |
| E7 | 15/0 | — | — | 15/0 | — |
| E8 | — | — | — | 57/0 · ст. 1/0 | — |
| E9 | — | — | — | 2/0 | — |
| G1 | — | — | — | — | 3/0 |
| G2 | — | — | — | — | 2/0 |
| G3 | 7/0 · спр. 1 | 7/0 · спр. 1 | 7/0 · спр. 1 | 7/0 · спр. 1 | — |
| H0 | ст. 1/0 | ст. 1/0 | ст. 1/0 | ст. 1/0 | — |
| K1 | 12/0 | — | — | 12/0 | — |
| K2 | 6/0 | — | — | 6/0 | — |
| K3 | 4/0 | — | — | 4/0 | — |
| K4 | 4/0 | — | — | 4/0 | — |
| K5 | 7/0 | — | — | 7/0 | — |
| K6 | 19/0 | — | — | 19/0 | — |
| K7 | 7/0 | — | — | 7/0 | — |
| K8 | 2/0 | — | — | 2/0 | — |
| K9 | 9/0 | — | — | 9/0 | — |
| K10 | 4/0 | — | — | 4/0 | — |
| K11 | 14/0 | — | — | 25/0 | — |
| K12 | 4/0 | — | — | 4/0 | — |
| K13 | 3/0 | — | — | 3/0 | — |
| K14 | 8/0 | — | — | 8/0 | — |
| K15 | 6/0 · ст. 3/0 | — | — | 6/0 · ст. 3/0 | — |
| L1 | 2/0 | — | — | 2/0 | — |
| L2 | 4/0 | — | — | 4/0 | — |
| L3 | 4/0 | — | — | 4/0 | — |
| L4 | 5/0 | — | — | 8/0 | — |
| M1 | 3/0 | — | — | 3/0 | — |
| M2 | 2/0 | — | — | 2/0 | — |
| M3 | 2/0 | — | — | 2/0 | — |
| M4 | 1/0 | — | — | 1/0 | — |
| MANIFEST | ст. 1/0 | ст. 1/0 | ст. 1/0 | ст. 1/0 | ст. 1/0 |
| N1 | 1/0 | — | — | 1/0 | — |
| N2 | 1/0 | — | — | 1/0 | — |
| N3 | 1/0 | — | — | 1/0 | — |
| N4 | 2/0 | — | — | 2/0 | — |
| N5 | 1/0 | — | — | 2/0 | — |
| N6 | 2/0 | — | — | 2/0 | — |
| N7 | 1/0 | — | — | 1/0 | — |
| N8 | 1/0 | — | — | 1/0 | — |
| P1 | 5/0 | — | — | 5/0 | — |
| P2 | 4/0 | — | — | 4/0 | — |
| P3 | 2/0 | — | — | 2/0 | — |
| P4 | 2/0 | — | — | 2/0 | — |
| P5 | 7/0 | — | — | 7/0 | — |
| P6 | 4/0 | — | — | 4/0 | — |
| P7 | 5/0 | — | — | 5/0 | — |
| P8 | — | — | — | 4/0 | — |
| P9 | 10/0 | — | — | 10/0 | — |
| P10 | — | — | — | 8/0 | — |
| PILOT-1 | — | — | — | 1/0 | — |
| PILOT-2 | 2/0 | 2/0 | 2/0 | 2/0 | — |
| PILOT-10 | 2/0 | 1/0 | 1/0 | 1/0 | — |
| PILOT-24 | ст. 6/0 | ст. 3/0 | ст. 3/0 | ст. 3/0 | — |
| Q1 | — | 6/0 | — | 6/0 | — |
| Q2 | — | 11/0 | — | 11/0 | — |
| Q3 | — | 9/0 | — | 9/0 | — |
| Q4 | — | 8/0 | — | 8/0 | — |
| Q5 | — | 2/0 | — | 2/0 | — |
| Q6 | — | 8/0 | — | 8/0 | — |
| R1 | 4/0 | 2/0 | 2/0 | 2/0 | — |
| R2 | 2/0 | 1/0 | 1/0 | 1/0 | — |
| R3 | 8/0 | 4/0 | 4/0 | 4/0 | — |
| R4 | 2/0 | 1/0 | 1/0 | 1/0 | — |
| R5 | 6/0 | 3/0 | 3/0 | 3/0 | — |
| R6 | 2/0 | 1/0 | 1/0 | 1/0 | — |
| R7 | 2/0 | 1/0 | 1/0 | 1/0 | — |
| R8 | 16/0 | 8/0 | 8/0 | 8/0 | — |
| R9 | 2/0 | 1/0 | 1/0 | 1/0 | — |
| R10 | 1/0 | — | — | — | — |
| R11 | 8/0 | 4/0 | 4/0 | 4/0 | — |
| RUN | ст. 4/0 | ст. 2/0 | ст. 2/0 | ст. 2/0 | — |
| S1 | 4/0 | 4/0 | 4/0 | 4/0 | — |
| S2 | 19/0 · ст. 1/0 · спр. 1 | 19/0 · ст. 1/0 · спр. 1 | 19/0 · ст. 1/0 · спр. 1 | 19/0 · ст. 1/0 · спр. 1 | — |
| S3 | 1/0 | 1/0 | 1/0 | 1/0 | — |
| S4 | 2107/0 · ст. 5/0 | 2107/0 · ст. 5/0 | 2107/0 · ст. 5/0 | 2107/0 · ст. 5/0 | — |
| S5 | 156/0 | 156/0 | 156/0 | 156/0 | — |
| S6 | 130/0 | 130/0 | 130/0 | 133/0 | — |
| S7 | 3/0 | 3/0 | 3/0 | 4/0 | — |
| S8 | 7/0 | 7/0 | 7/0 | 101/0 | 1/0 · ст. 1/0 |
| S9 | — | 15/0 | — | 15/0 | — |
| S10 | 5/0 | 5/0 | 5/0 | 5/0 | — |
| S11 | — | — | — | — | 718/0 · ст. 1/0 |
| S12 | 157/0 | 157/0 | 157/0 | 156/0 · ст. 1/0 | — |
| S13 | 3/0 · спр. 1 | 3/0 · спр. 1 | 3/0 · спр. 1 | 3/0 · спр. 1 | — |
| S14 | 86/0 | 86/0 | 86/0 | 86/0 | — |
| S15 | 19/0 | 19/0 | 19/0 | 19/0 | — |
| S16 | 2/0 | 2/0 | 2/0 | 2/0 | — |
| T-W | 6/0 · спр. 5 | — | — | 6/0 · спр. 5 | — |
| U1 | 1/0 | — | — | — | — |
| U2 | 1/0 | — | — | — | — |
| W1 | 48/0 | — | — | 48/0 | — |
| W2 | 5/0 | — | — | 5/0 | — |
| W3 | 61/0 | — | — | 61/0 | — |
| W4 | 2/0 | — | — | 2/0 | — |
| mend | 92/0 · ст. 4/0 | 46/0 · ст. 2/0 | 46/0 · ст. 2/0 | 46/0 · ст. 2/0 | — |
| **всего (мод)** | 3219/0 | 2845/0 | 2781/0 | 3391/0 | 724/0 |

## base: провалы (0)

нет

## bq: провалы (0)

нет

## be: провалы (0)

нет

## sa: провалы (0)

нет

## files: провалы (0)

нет

## Манифест обязательных номеров (§11 с поправками §15)

- base: 79 номеров — E1, E2, E3, E4, E5, E6, E7, G3, K1, K2, K3, K4, K5, K6, K7, K8, K9, K10, K11, K12, K13, K14, K15, L1, L2, L3, L4, M1, M2, M3, M4, N1, N2, N3, N4, N5, N6, N7, N8, P1, P2, P3, P4, P5, P6, P7, P9, R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, S1, S2, S3, S4, S5, S6, S7, S8, S10, S12, S13, S14, S15, S16, T-W, U1, U2, W1, W2, W3, W4
- bq: 23 номеров — E6, G3, Q1, Q2, Q3, Q4, Q5, Q6, S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S12, S13, S14, S15, S16
- be: 15 номеров — G3, S1, S2, S3, S4, S5, S6, S7, S8, S10, S12, S13, S14, S15, S16
- sa: 86 номеров — E1, E2, E3, E4, E5, E6, E7, E8, E9, G3, K1, K2, K3, K4, K5, K6, K7, K8, K9, K10, K11, K12, K13, K14, K15, L1, L2, L3, L4, M1, M2, M3, M4, N1, N2, N3, N4, N5, N6, N7, N8, P1, P2, P3, P4, P5, P6, P7, P8, P9, P10, Q1, Q2, Q3, Q4, Q5, Q6, R1, R2, R3, R4, R5, R6, R7, R8, R11, S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S12, S13, S14, S15, S16, T-W, W1, W2, W3, W4
- files: 4 номеров — G1, G2, S8, S11
- Сужения против §11.1 (функциональные тесты — в B и SA): R10 в sa: повтор прогона катушки (mend_repeat, сравнение sha256) идёт только в base; R9 в sa: половина R9 со сменой версии тестового мода идёт только в base (прогон mend_bump); в sa есть только контроль; U1 в sa: tools/ups.py ставит только базовую игру; U2 в sa: tools/ups.py ставит только базовую игру.

## Справочные записи (info, без проверки; 22)

- base **S2** recycling recipes count (информация; набор проверяет S9): `0`
- base **S13** referenced __magnetics__ paths (информация): `61`
- base **G3** statuses (справочно): `None` — magnetics-sintering-kiln=working; magnetics-induction-furnace=working; magnetics-coil-winder=working; magnetics-cryo-chamber=working; magnetics-flux-resonator=working; magnetics-magnetic-separator=working; magnetics-magnetic-drill=waiting_for_space_in_destination; magnetics-maglev-transport-belt=wor…
- base **T-W** T-W gun SC-wall share of wall HP lost vs 1/2 of stone-wall share (справочно): `0.019632748715082804` — clear 27.916666666667 s, alive 0, wall HP lost 4711.9 (0 of 160 destroyed), turrets lost 0, energy 0.00 MJ; stone variant lost 27632.800571442 of 56000; absolute ratio SC/stone 0.17051690723269
- base **T-W** T-W coilgun SC-wall share of wall HP lost vs 1/2 of stone-wall share (справочно): `0.00451481221516927` — clear 10.65 s, alive 0, wall HP lost 1083.6 (0 of 160 destroyed), turrets lost 0, energy 9.32 MJ; stone variant lost 2463.2004241943 of 56000; absolute ratio SC/stone 0.4398971845724
- base **T-W** T-W gauss SC-wall share of wall HP lost vs 1/2 of stone-wall share (справочно): `0.0016412567138671874` — clear 8.45 s, alive 0, wall HP lost 393.9 (0 of 160 destroyed), turrets lost 0, energy 24.25 MJ; stone variant lost 652.40008544922 of 56000; absolute ratio SC/stone 0.60377308359317
- base **T-W** T-W laser SC-wall share of wall HP lost vs 1/2 of stone-wall share (справочно): `0.008303796895345052` — clear 13.8 s, alive 0, wall HP lost 1992.9 (0 of 160 destroyed), turrets lost 0, energy 155.53 MJ; stone variant lost 4869.6002311707 of 56000; absolute ratio SC/stone 0.40925561858775
- base **T-W** T-W arc SC-wall share of wall HP lost vs 1/2 of stone-wall share (справочно): `0.0028925140380859373` — clear 9.9666666666667 s, alive 0, wall HP lost 694.2 (0 of 160 destroyed), turrets lost 0, energy 79.92 MJ; stone variant lost 1134.8002090454 of 56000; absolute ratio SC/stone 0.61174060738373
- bq **S2** recycling recipes count (информация; набор проверяет S9): `34`
- bq **S13** referenced __magnetics__ paths (информация): `61`
- bq **G3** statuses (справочно): `None` — magnetics-sintering-kiln=working; magnetics-induction-furnace=working; magnetics-coil-winder=working; magnetics-cryo-chamber=working; magnetics-flux-resonator=working; magnetics-magnetic-separator=working; magnetics-magnetic-drill=waiting_for_space_in_destination; magnetics-maglev-transport-belt=wor…
- be **S2** recycling recipes count (информация; набор проверяет S9): `0`
- be **S13** referenced __magnetics__ paths (информация): `61`
- be **G3** statuses (справочно): `None` — magnetics-sintering-kiln=working; magnetics-induction-furnace=working; magnetics-coil-winder=working; magnetics-cryo-chamber=working; magnetics-flux-resonator=working; magnetics-magnetic-separator=working; magnetics-magnetic-drill=waiting_for_space_in_destination; magnetics-maglev-transport-belt=wor…
- sa **S2** recycling recipes count (информация; набор проверяет S9): `34`
- sa **S13** referenced __magnetics__ paths (информация): `61`
- sa **G3** statuses (справочно): `None` — magnetics-sintering-kiln=working; magnetics-induction-furnace=working; magnetics-coil-winder=working; magnetics-cryo-chamber=working; magnetics-flux-resonator=working; magnetics-magnetic-separator=working; magnetics-magnetic-drill=waiting_for_space_in_destination; magnetics-maglev-transport-belt=wor…
- sa **T-W** T-W gun SC-wall share of wall HP lost vs 1/2 of stone-wall share (справочно): `0.019921714019775386` — clear 27.866666666667 s, alive 0, wall HP lost 4781.2 (1 of 160 destroyed), turrets lost 0, energy 0.00 MJ; stone variant lost 30981.200357437 of 56000; absolute ratio SC/stone 0.15432621427137
- sa **T-W** T-W coilgun SC-wall share of wall HP lost vs 1/2 of stone-wall share (справочно): `0.004869608561197916` — clear 10.966666666667 s, alive 0, wall HP lost 1168.7 (0 of 160 destroyed), turrets lost 0, energy 9.60 MJ; stone variant lost 2202.0003662109 of 56000; absolute ratio SC/stone 0.53074743883832
- sa **T-W** T-W gauss SC-wall share of wall HP lost vs 1/2 of stone-wall share (справочно): `0.0015870890299479166` — clear 7.55 s, alive 0, wall HP lost 380.9 (0 of 160 destroyed), turrets lost 0, energy 22.50 MJ; stone variant lost 530.00006103516 of 56000; absolute ratio SC/stone 0.7186817421182
- sa **T-W** T-W laser SC-wall share of wall HP lost vs 1/2 of stone-wall share (справочно): `0.007450656127929688` — clear 16.55 s, alive 0, wall HP lost 1788.2 (0 of 160 destroyed), turrets lost 0, energy 184.33 MJ; stone variant lost 5161.6000976563 of 56000; absolute ratio SC/stone 0.34643471731084
- sa **T-W** T-W arc SC-wall share of wall HP lost vs 1/2 of stone-wall share (справочно): `0.0030225128173828122` — clear 9.9333333333333 s, alive 0, wall HP lost 725.4 (0 of 160 destroyed), turrets lost 0, energy 77.92 MJ; stone variant lost 1055.6002349854 of 56000; absolute ratio SC/stone 0.68719487939669

