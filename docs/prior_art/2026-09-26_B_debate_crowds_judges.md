# Предшественники: взаимная критика и дебаты, одинаковость ответов моделей, LLM-судьи, юмор
Отчёт агента-исследователя, 26.09.2026. Статусы: «snippet» — подтверждено поисковой выдачей в этой сессии (WebFetch недоступен для всех доменов), «memory» — не подтверждено. Числа — только из сниппетов.

## 1. Дебаты и взаимная критика
- «The Cost of Consensus: Isolated Self-Correction Prevails Over Unguided Homogeneous Multi-Agent Debate» (2026, авторы — не уверен): команды из 10 одинаковых агентов (модели 7–8B), конформизм до 85,5 %, хрупкость до 70,0 %, «коллапс консенсуса» — разрыв с оракулом до 32,3 п.п.; дебаты в 2,1–3,4 раза дороже самокоррекции при равной или худшей точности — snippet. https://arxiv.org/abs/2605.00914
- Zhang et al. 2025, «Stop Overvaluing Multi-Agent Debate»: 5 методов, 9 бенчмарков, 4 модели; дебаты часто не лучше CoT и self-consistency; разнородные агенты помогают (Heter-SoM +6,4 %, Heter-EoT +8,2 %) — snippet. https://arxiv.org/abs/2502.08788
- Choi, Zhu, Li 2025, «Debate or Vote» (NeurIPS 2025): дебаты лучше одного агента, но не надёжно лучше голосования большинством — snippet (привязка к статье «вероятно»). https://arxiv.org/abs/2508.17536
- Huang et al. 2023, «LLMs Cannot Self-Correct Reasoning Yet»: при равном числе ответов дебаты уступают self-consistency — snippet. https://arxiv.org/abs/2310.01798
- «When Two LLMs Debate, Both Think They'll Win» (2025): уверенность 72,9 % → 83 %; в 61,7 % дебатов обе стороны заявили больше 75 %; против своей копии 64,1 % → 75,2 % — snippet. https://arxiv.org/abs/2505.19184
- Liang et al., MAD (EMNLP 2024): «вырождение мысли» — snippet. https://aclanthology.org/2024.emnlp-main.992/
- Du et al. 2023 (ICML 2024): дебаты копий повышают точность — memory; критика: нет сравнения при равном бюджете — snippet (блог). https://arxiv.org/abs/2305.14325
- Только memory: ChatEval; Smit et al. «Should we be going MAD?»; Wang et al. ACL 2024; Estornell & Liu NeurIPS 2024 (эхо-камера); ReConcile; «More Agents Is All You Need»; «Rethinking Mixture-of-Agents».

## 2. Однородность и коррелированные ошибки
- Kim, Garg et al., «Correlated Errors in Large Language Models» (ICML 2025): >350 моделей; когда обе ошибаются, ответы совпадают в 60 % случаев; корреляция растёт с точностью — snippet. https://arxiv.org/abs/2506.07962
- Goel et al. 2025, «Great Models Think Alike and this Undermines AI Oversight» — snippet. https://arxiv.org/abs/2502.04313
- Jiang et al., «Artificial Hivemind» (NeurIPS 2025): для 79 % запросов средняя схожесть 50 ответов одной модели > 0,8 — snippet. https://arxiv.org/abs/2510.22954
- Kleinberg & Raghavan 2021 (PNAS), алгоритмическая монокультура — memory.

## 3. Прогнозы
- Schoenegger et al. 2024, «Wisdom of the Silicon Crowd» (Science Advances): толпа из 12 разных LLM статистически не отличается от человеческой толпы — snippet. https://www.science.org/doi/10.1126/sciadv.adp1528

## 4. LLM-судьи
- Zheng et al. 2023 (MT-Bench): согласие GPT-4 с людьми > 80 %; смещения по позиции, многословию, в пользу своих ответов — snippet. https://arxiv.org/abs/2306.05685
- «Self-Preference Bias in LLM-as-a-Judge» (2024): предпочтение «знакомого» (низкой перплексии) — snippet. https://arxiv.org/abs/2410.21819
- Только memory: Panickssery et al. 2024; Verga et al. 2024; Laurito et al. 2025.

## 5. Юмор
- Jentzsch & Kersting 2023: больше 90 % из 1008 шуток — одни и те же 25 — snippet. https://arxiv.org/abs/2306.04563
- Огири (2025): корреляция LLM-судей с людьми ρ = 0,266 (Claude Sonnet 4), 0,224 (GPT-4.1), 0,169 (Gemini 2.5 Pro) — snippet. https://arxiv.org/abs/2511.09133
- Mirowski et al. 2024 (воркшопы с комиками) — snippet/memory. https://arxiv.org/abs/2405.20956

## 6. Персоны
- Zheng M. et al. 2024 (EMNLP Findings): 162 роли, персоны не повышают точность — snippet. https://aclanthology.org/2024.findings-emnlp.888/

## Что из наших выводов повторяет известное
- Одинаковые головы — одна голова (PRED-01): известно (Hivemind, коррелированные ошибки, монокультура; толпа работает у разных моделей).
- Судьи юмора (HUMOR-01): высокое согласие судей и отказ человека согласуются с известными смещениями; но предпочтение КОРОТКИХ шуток противоположно известному смещению в пользу многословия — это не повтор.
- Дебаты при равном бюджете обычно не лучше голосования; одинаковые команды склонны к конформизму; уверенность в спорах растёт.

## Не нашёл
Толпу из идентичных копий фронтирной модели на числовых задачах с кодовой истиной с замером совпадения цифра в цифру; влияние взаимной критики на калибровку по кодовой истине; смещение судей юмора в пользу краткости; сравнение агрегатора-«мозолистого тела» с медианой при равном бюджете с учётом калибровки.
