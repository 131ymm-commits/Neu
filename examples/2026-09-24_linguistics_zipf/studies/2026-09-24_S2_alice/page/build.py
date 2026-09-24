"""Собирает страницу для публикации из s2_results.json и s2_posthoc.json (числа не переписываются руками).
Запуск: python3 page/build.py -> page/alice.html"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.dirname(HERE)
R = json.load(open(os.path.join(S, 's2_results.json')))
P = json.load(open(os.path.join(S, 's2_posthoc.json')))
NAME = {'fi': 'финский', 'he': 'иврит', 'cs': 'чешский', 'ru': 'русский', 'bg': 'болгарский', 'it': 'итальянский',
        'eo': 'эсперанто', 'de': 'немецкий', 'es': 'испанский', 'en': 'английский', 'fr': 'французский'}
TR = {'en': 'Кэрролл, 1865 (оригинал)', 'de': 'Циммерман, 1869', 'fr_bue': 'Бюэ, 1869', 'fr_papy': 'Папи, 2001',
      'it': 'Пьетрокола-Россетти, 1872', 'es_1': 'перевод 1 (корпус iglika88)', 'es_2': 'перевод 2 (корпус iglika88)',
      'eo': 'Кирни, 1910', 'fi': 'Анни Сван, 1906', 'ru_dem': 'Демурова (изд. 1978)', 'ru_nes': 'Нестеренко, 2000',
      'cs': 'Скоумалы, 1961', 'bg': 'Голдман, 1933', 'he': 'Семятицкий, 1923'}
langs = sorted(R['lang'], key=lambda L: R['lang'][L]['r'])
data = {'N': R['N_ttr'], 'W_en': R['W']['en'], 'langs': []}
for L in langs:
    v = R['lang'][L]
    top = R['E2_top'][v['texts'][0]][0]
    data['langs'].append({
        'code': L, 'name': NAME[L], 'r': v['r'], 'letters': v['letters_rel'], 'ttr': v['ttr_N'],
        'texts': [{'code': c, 'who': TR[c], 'r': R['r'][c], 'W': R['W'][c]} for c in v['texts']],
        'top': {'w': top[0], 'n': top[1], 'share': top[2]},
        'noart': R['P7']['no_art'].get(L)})
data['ref'] = {'ja': R['E2_ref']['ja']['letters_rel_en'], 'zh': R['E2_ref']['zh']['letters_rel_en'], 'zakh': R['E2_ref']['ru_zakh']['r']}
data['P'] = {k: R[k]['verdict'] for k in ('P4', 'P5', 'P6', 'P7', 'P8')}
data['rho4'] = R['P4']['rho']; data['rho6'] = R['P6']['rho']; data['p4'] = P['p_exact']['P4']; data['p6'] = P['p_exact']['P6']
data['max_counts'] = P['summary']['max_counts']; data['combos'] = P['summary']['n']
data['e1'] = {L: max(d.values()) - min(d.values()) for L, d in R['E1'].items()}
data['between'] = R['E1_between']['range']
rv = P['review']
data['groups'] = {'short': ['fi', 'he', 'cs'], 'mid': ['ru', 'bg', 'it', 'eo'], 'talk': ['de', 'es', 'en', 'fr']}
data['rev'] = {'fi_letters_collapsed': rv['letters_doubles_collapsed_rel_en']['fi'], 'fi_doubles': rv['doubled_pairs']['fi'],
               'en_doubles': rv['doubled_pairs']['en'], 'he_alice': rv['he_alice']['with_prefix'],
               'en_alice': rv['en_alice']['alice'] + rv['en_alice']["alice's"], 'he_hi': rv['he_alice']['hi'], 'en_she': rv['en_alice']['she'],
               'pair_median': rv['E1_pairwise_lang']['median'], 'max_over_min': rv['E1_max_over_min_lang'],
               'e1_rel': rv['E1_relative'], 'gap': rv['gap_short_vs_talkative'], 'fr_e3': rv['E3_symmetric_fr_median'],
               'it_noart': R['P7']['no_art']['it'], 'ru_nes': R['r']['ru_nes'], 'spread': max(max(d.values()) - min(d.values()) for d in R['E1'].values())}
html = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read().replace('__DATA__', json.dumps(data, ensure_ascii=False))
open(os.path.join(HERE, 'alice.html'), 'w', encoding='utf-8').write(html)
print('page/alice.html', len(html), 'байт')
