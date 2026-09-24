# Сверка с литературой — 2026-09-01

Продолжение PAPERS-CHECK-2026-08 и карт HUB-PRIOR-ART-2 / HUB-UNIFIERS. Вопрос мандата: свежее за ~2 недели + занятость хода «уровни в LLM» перед GROK-аркой.

## 1. Гроккинг-как-фазовый-переход — поле горячее, и это НАМ НА РУКУ

За 2026 год линия оформилась в семью: [«Grokking as a Phase Transition between Competing Basins» (2603.01192)](https://arxiv.org/pdf/2603.01192) — обмен бассейнов запоминание↔обобщение (в нашей грамматике это фолд-семейство: обмен/поворот ветвей); [«Norm-Separation Delay Law» (2603.13331)](https://arxiv.org/html/2603.13331) — первопринципная теория задержки; [«Spectral Entropy Collapse» (2604.13123)](https://arxiv.org/abs/2604.13123) — интервенционная рамка; [«Falsifiable Finite-Size Transition»](https://www.researchgate.net/publication/403194288_Grokking_as_a_Falsifiable_Finite-Size_Transition) — конечноразмерное обострение; [«First-Passage Prediction of Grokking Delay» (2605.18845)](https://arxiv.org/pdf/2605.18845) — закон задержки T_grok − T_mem ≈ (2κηλ)⁻¹·log(V_mem/V*) по НОРМЕ ВЕСОВ (проверено: p ∈ {53…113}, MAPE 17.7%; **кривую val-accuracy трактуют как событие пересечения порога — «plateau length, sharpness, statistical certificates НЕ анализируются» — прямая цитата их ограничений**).

**Предвестники гроккинга уже есть — но все ИЗ ВЕСОВ**: [«Early-Warning Signals of Grokking via Loss-Landscape Geometry» (2602.16967)](https://arxiv.org/html/2602.16967v1) — коммутаторный дефект некоммутирующих апдейтов (упреждение суперлинейно, интервенции ускоряют гроккинг на 32–50%); [«Density Matrices → Spectral Early Warnings» (2603.29805)](https://arxiv.org/html/2603.29805) — спектры слоёв.

**Вердикт занятости для GROK-арки: `занято, но с другой стороны`.** Все они смотрят ВНУТРЬ модели (веса, спектры, коммутаторы). Никто не читает СНАРУЖИ — саму скалярную кривую метрики — замороженными траекторными сертификатами (S-транзиент, ступень/излом, намотка) с предрегистрацией, контроль-армом и убийцами. Наш ход — «чёрный ящик снаружи»: применим и там, где весов не дают.

## 2. Механизм-ландшафты (2606.07563) — без изменений

Продолжений/цитирующей волны не видно (SSRN-зеркало, каталоги); эмпирика по-прежнему один домен. Вердикт HUB-UNIFIERS D3 стоит. Побочная находка в соседнюю клетку: [«Crossing the Functional Desert: Feasibility Transition for the Emergence of Life» (2601.06272)](https://arxiv.org/html/2601.06272v2) — в HUB-ORIGIN-OF-LIFE при следующем заходе.

## 3. EWS/типпинг — ниша не закрыта

Нового претендента на «один замороженный кросс-системный инструмент» не появилось. Поле продолжает рефлексию о неоднозначности предвестников ([Ambiguity of EWS, Nat. Clim. Change](https://www.nature.com/articles/s41558-025-02328-8)) и полезности для решений ([J. R. Soc. Interface 2025](https://royalsocietypublishing.org/rsif/article-abstract/22/225/20240864/235940/)); институционально — [TIPMIP](https://ntrs.nasa.gov/api/citations/20250006500/downloads/ARomanouESDTippingPreprint.pdf) и программа [ARIA Forecasting Tipping Points](https://aria.org.uk/opportunity-spaces/scoping-our-planet/forecasting-tipping-points) (само существование программы = признание пробела). Лентон-2026 gap-лист актуален.

## 4. LLM-эмерджентность

[Phil Trans A «LLMs and emergence: a complex systems perspective» (2025)](https://doi.org/10.1098/rsta.2025.0014) — перспектива без общего инструмента; [«Emergent Causal–Geometric Dynamics Across Depth» (2602.04931)](https://arxiv.org/html/2602.04931v2) — геометрия по ГЛУБИНЕ, не по обучению. ψ′-поперёк-обучения не занято (и для GROK не планируется — нет многомерной микрозаписи без тяжёлой инструментовки; поименовано).

## Следствие для арки

Гроккинг — легитимнейший «уровень в LLM-мире» с горячей теорией фолд-класса (обмен бассейнов, first-passage-ожидание) и БЕЗ трактовки кривой как траектории. Наш эксперимент: собственные прогоны (реплики × армы × ручка wd), батарея на кривой val-accuracy, теоретический якорь — их же first-passage-закон (задержка ∝ 1/λ → наша ручка-предсказание P-G4).
