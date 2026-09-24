"""Скачивает тексты S2 в каталог ВНЕ репозитория (часть переводов под охраной — в репозиторий идут только адреса, хэши и числа).
Запуск: python3 fetch.py [каталог_кэша]  (по умолчанию ~/alice_cache). Пишет manifest.json рядом с этим файлом."""
import hashlib, json, os, sys, urllib.request, urllib.parse
RAW = 'https://raw.githubusercontent.com/'
IG = 'iglika88/corpus_original_and_abridged_texts/main/'
CS = 'books-are-next/carroll-alenka-v-kraji-divu/main/content/alenka_v_kraji_divu_{}.md'
TEXTS = {
    'en':      [('S-05', 'GITenberg/Alice-s-Adventures-in-Wonderland_11/master/11-0.txt')],
    'de':      [('S-06', 'GITenberg/Alice-s-Abenteuer-im-Wunderland_19778/master/19778-8.txt')],
    'fr_bue':  [('S-07', 'GITenberg/Aventures-d-Alice-au-pays-des-merveilles_55456/master/55456-0.txt')],
    'fr_papy': [('S-08', IG + 'French/Alice in Wonderland/aw fr full 1.txt')],
    'it':      [('S-09', 'GITenberg/Le-avventure-d-Alice-nel-paese-delle-meraviglie_28371/master/28371-8.txt')],
    'es_1':    [('S-10', IG + 'Spanish/Alice in Wonderland/aw sp full 1.txt')],
    'es_2':    [('S-11', IG + 'Spanish/Alice in Wonderland/aw sp full 2.txt')],
    'eo':      [('S-12', 'GITenberg/La-Aventuroj-de-Alicio-en-Mirlando_17482/master/17482-0.txt')],
    'fi':      [('S-13', 'GITenberg/Liisan-seikkailut-ihmemaassa_46569/master/46569-8.txt')],
    'ru_dem':  [('S-14', IG + 'Russian/Alice in Wonderland/aw ru full 1.txt')],
    'ru_nes':  [('S-15', IG + 'Russian/Alice in Wonderland/aw ru full 2.txt')],
    'cs':      [('S-16', CS.format(n)) for n in ('008', '017', '024', '029', '037', '045', '055', '062', '071', '078', '083', '089')],
    'bg':      [('S-17', 'chitanka/content-text/master/02/552')],
    'he':      [('S-18', 'projectbenyehuda/public_domain_dump/master/txt_stripped/p1045/m34262.txt')],
    'ja':      [('S-19', 'P4suta/aozorabunko_text/master/作品/キャロルルイス/アリスはふしぎの国で（57320_ruby_57182）.txt')],
    'zh':      [('S-20', 'haodoo/haodoo-classic/HEAD/html/PDB/H/10P1.epub')],
    'ru_zakh': [('S-21', 'Tviskaron/mipt/HEAD/2019/python/04-sem/alice.txt')],
}

def main():
    cache = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/alice_cache')
    os.makedirs(cache, exist_ok=True)
    man = {}
    for code, parts in TEXTS.items():
        man[code] = []
        for i, (sid, path) in enumerate(parts):
            url = RAW + urllib.parse.quote(path)
            dst = os.path.join(cache, f'{code}_{i:02d}' + os.path.splitext(path)[1].replace('.md', '.md'))
            if not os.path.exists(dst):
                with urllib.request.urlopen(url, timeout=120) as r, open(dst, 'wb') as f:
                    f.write(r.read())
            data = open(dst, 'rb').read()
            man[code].append({'source': sid, 'url': url, 'file': os.path.basename(dst), 'bytes': len(data),
                              'sha256': hashlib.sha256(data).hexdigest()})
        print(code, sum(p['bytes'] for p in man[code]), 'байт')
    json.dump(man, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'manifest.json'), 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
