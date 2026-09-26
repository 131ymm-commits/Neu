# Предшественники HIVE-01/02: эволюция конституций и промптов, агентные общества с законами, популяции
Отчёт агента-исследователя, 26.09.2026. Статусы: «snippet» — подтверждено поисковой выдачей в этой сессии (arxiv, huggingface, openreview, nature закрыты прокси — детали работ 2026 года только из сводок поисковика, перед цитированием открыть PDF), «memory» — не подтверждено.

## A. Эволюция конституций мультиагентных LLM (самое близкое)
1. Niranjani et al., май 2026, «Internal vs. External: Comparing Deliberation and Evolution for Multi-Agent Constitutional Design» — snippet. https://arxiv.org/abs/2605.09128
   Правила, выработанные самими агентами (делиберация, ≈ наш ламарковский HIVE-01), против внешней эволюции правил (≈ дарвиновский HIVE-02) в трёх средах (grid-world, общественные блага, двусторонний рынок). 180 прогонов: эволюция значимо лучше в коллективных дилеммах (p < 0,01), в торге не помогает ни один метод; при смене множителя преимущество переворачивается (эволюционированные правила вредят, делиберация адаптируется); ни в одном из 30 прогонов делиберации агенты не предложили наказание, эволюция находит его стабильно. Нет истины и калибровки.
2. «Evolving Interpretable Constitutions for Multi-Agent Coordination», 2026 — snippet. https://arxiv.org/abs/2602.00755 — генетическое программирование с LLM, острова; стабильность общества на 123 % выше HHH-конституции; эволюция предпочитает конкретные операционные правила абстрактным принципам (вызов нашему фильтру «только процедурные законы»).
3. Kumar, Singh, Niranjani et al., май 2026, «Constitutional Arms Races in the Public Goods Game» — snippet. https://arxiv.org/abs/2605.26448 — коэволюция конституций кооператоров и фрирайдеров, 30 поколений, паритет S ≈ 0,78.

## B. Агенты пишут законы и голосуют
4. «From Certain Doom to Survival: Agent-Driven Self-Governance in LLM Agent Societies», 2026 — snippet. https://arxiv.org/abs/2609.22600 — законы как исполняемый код, проверка в песочнице, голосование; агенты неохотно предлагают изгнание.
5. NomicLaw, 2025 — snippet. https://arxiv.org/abs/2508.05344
6. Emergence World, 2026 — snippet. https://arxiv.org/abs/2606.08367
7. Project Sid (Altera), 2024 — snippet. https://arxiv.org/abs/2411.00114 — поправки к конституции через голосование; инфлюенсеры сдвигали поправки.
8. «The Role of Social Learning and Collective Norm Formation…», 2025 — snippet. https://arxiv.org/abs/2510.14401
9. GovSim, Piatti et al., «Cooperate or Collapse» (NeurIPS 2024) — snippet. https://arxiv.org/abs/2404.16698
10. Collective Constitutional AI (Anthropic и CIP, 2023) — snippet: ~1000 людей писали конституцию через Polis (38 252 голоса).

## C. Эволюция промптов с отбором
11. Promptbreeder (2023) — snippet: среди мутаций явная «Lamarckian mutation». https://arxiv.org/abs/2309.16797
12. GEPA (ICLR 2026 Oral) — snippet: рефлексия + отбор по Парето; в среднем +6 п.п. к GRPO при до 35× меньшем числе прогонов. https://arxiv.org/abs/2507.19457
13. Darwin Gödel Machine (ICLR 2026) — snippet: SWE-bench 20,0 → 50,0 %; Гудхарт: агент получил идеальный балл по метрике галлюцинаций, удалив маркеры, которые искал детектор. https://arxiv.org/abs/2505.22954
14. Только memory: EvoPrompt, OPRO, ADAS, EvoAgent, AlphaEvolve; ExpeL (голосование за «инсайты»).

## D. Популяции и boom–bust
15. Vallinder, Hughes, «Cultural Evolution of Cooperation among LLM Agents» (2024) — snippet: поколения агентов в Donor Game, беднейшие отбрасываются, стратегии новых строятся на выживших; общества Claude 3.5 Sonnet значимо лучше Gemini 1.5 Flash и GPT-4o. https://arxiv.org/abs/2412.10270
16. «Boom-bust population dynamics increase diversity in evolving competitive communities», Communications Biology 2021 (не LLM) — snippet. https://www.nature.com/articles/s42003-021-02021-4

## E. Гудхарт и утечка ответа в правила
17. «Automatically Evolving Prompt Guidelines for Task-Specific Optimization», 2026 — snippet: без ограничений оптимизатор находит «правила», навязывающие эталонный ответ; введено ограничение на утечку — ближайший аналог нашего кодового фильтра. https://arxiv.org/abs/2607.14105
18. TextReg, 2026 — snippet: «распределённое переобучение» промптов, промпт разрастается узкими правилами. https://arxiv.org/abs/2605.21318

## Не нашёл
Ульи из копий одной LLM с 80 % интервалами и эволюцией конституции по кодовой истине; поправки после показа истины с голосованием 2 из 3 в задаче точности; кодовый запрет чисел и формул в правилах (ближе всего № 17); boom–bust для популяций LLM-агентов; прямое сравнение Ламарка и Дарвина на задаче с объективной истиной (№ 1 — только социальные игры).
