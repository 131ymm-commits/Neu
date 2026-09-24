"""Извлекает 12 глав из каждого текста S2. Для каждого кода есть модуль extractors/<код>.py с функцией
chapters(paths: list[str]) -> list[str]: 12 тел глав без заголовков, сносок, лицензий и разметки.
Запуск: python3 extract.py [кэш] [выход] [коды...]. Главы пишутся ВНЕ репозитория (тексты под охраной не публикуются).
В репозиторий идёт extract_check.txt: начало и конец каждой главы (по 60 знаков) для сверки с английским."""
import importlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
EXEMPT = {'ru_zakh'}

def main():
    cache = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/alice_cache')
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser('~/alice_chapters')
    man = json.load(open(os.path.join(HERE, 'manifest.json')))
    codes = sys.argv[3:] or list(man)
    os.makedirs(out, exist_ok=True)
    lines = []
    for code in codes:
        paths = [os.path.join(cache, p['file']) for p in man[code]]
        mod = importlib.import_module(f'extractors.{code}')
        ch = mod.chapters(paths)
        # Заходер (вне зачёта) — пересказ со вставной «Главой никакой», число глав не 12
        assert len(ch) == 12 or code in EXEMPT, f'{code}: глав {len(ch)}, нужно 12'
        assert all(c.strip() for c in ch), f'{code}: пустая глава'
        json.dump(ch, open(os.path.join(out, f'{code}.json'), 'w'), ensure_ascii=False)
        lines.append(f'## {code}')
        for k, c in enumerate(ch, 1):
            c1 = ' '.join(c.split())
            lines.append(f'{k:2d} | {c1[:60]} … {c1[-60:]}')
        lines.append('')
        print(code, 'ok')
    if set(codes) == set(man):
        open(os.path.join(HERE, 'extract_check.txt'), 'w').write('\n'.join(lines))

if __name__ == '__main__':
    main()
