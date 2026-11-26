#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Полный текст статьи arXiv для ворот «литература»: метаданные, текст HTML и текст PDF (в PDF бывают приложения, которых нет в HTML).
Качает curl из контейнера. WebFetch агента arxiv.org не резольвит, а curl открывает (ERRORS № 196) — поэтому сначала этот путь.
Скачанное — недоверенные данные: папка вывода новая или пустая, скрипт лежит вне её и ничего из неё не исполняет; в журналы
и репозиторий идут только цитаты и номера разделов, а не файлы статьи.
  python3 tools/arxiv_text.py ID OUT_DIR   → OUT_DIR/{abs.html, paper.html, paper.pdf, html.txt, pdf.txt, meta.json}
Статус «полный текст» в записке — только после чтения нужных разделов в html.txt или pdf.txt, а не по факту скачивания."""
import html
import html.parser
import json
import os
import re
import shutil
import subprocess
import sys


class _Text(html.parser.HTMLParser):
    """Абзацы и заголовки — с новой строки, ячейки таблиц — через « | », формулы MathML — их alttext в $…$."""
    BLOCK = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'tr', 'caption', 'figcaption', 'section', 'table', 'br', 'dt', 'dd'}
    SKIP = {'script', 'style', 'nav', 'header', 'footer'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, t, a):
        a = dict(a)
        if t in self.SKIP:
            self.skip += 1
            return
        if t == 'math' and a.get('alttext'):
            self.out.append(' $' + a['alttext'] + '$ ')
            self.skip += 1
            return
        if t in self.BLOCK:
            self.out.append('\n')
        if t in ('td', 'th'):
            self.out.append(' | ')
        if re.fullmatch(r'h[1-6]', t):
            self.out.append('## ')

    def handle_endtag(self, t):
        if t in self.SKIP or t == 'math':
            self.skip = max(0, self.skip - 1)
            return
        if t in self.BLOCK:
            self.out.append('\n')

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def html_text(src):
    p = _Text()
    p.feed(src)
    t = re.sub(r'[ \t]+', ' ', ''.join(p.out))
    return re.sub(r'\n\s*\n+', '\n\n', t)


def meta(abs_src):
    """Название, авторы и даты версий из страницы abs; строка «From:» (имя и почта отправителя) не берётся."""
    title = re.search(r'<meta name="citation_title" content="([^"]*)"', abs_src)
    authors = [html.unescape(a) for a in re.findall(r'<meta name="citation_author" content="([^"]*)"', abs_src)]
    hist = re.search(r'<div class="submission-history">(.*?)</div>', abs_src, re.S)
    versions = []
    if hist:
        h = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', hist.group(1))))
        versions = [dict(version=v, date=d.strip()) for v, d in re.findall(r'\[(v\d+)\]\s*([^(\[]+)', h)]
    return dict(title=html.unescape(title.group(1)) if title else None, authors=authors, versions=versions)


def fetch(url, dst):
    r = subprocess.run(['curl', '-sSL', '--max-time', '120', '-o', dst, '-w', '%{http_code}', url], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else f'curl {r.returncode}: {r.stderr.strip()[:200]}'


def main(a):
    if len(a) != 2 or not re.fullmatch(r'\d{4}\.\d{4,5}(v\d+)?', a[0]):
        raise SystemExit(__doc__)
    aid, out = a
    if os.path.exists(out) and os.listdir(out):
        raise SystemExit(f'папка {out} не пуста: скачанное кладётся только в новую или пустую папку')
    os.makedirs(out, exist_ok=True)
    codes = {kind: fetch(f'https://arxiv.org/{kind}/{aid}', os.path.join(out, name))
             for kind, name in (('abs', 'abs.html'), ('html', 'paper.html'), ('pdf', 'paper.pdf'))}
    res = dict(id=aid, http=codes)
    if codes['abs'] == '200':
        res.update(meta(open(os.path.join(out, 'abs.html'), encoding='utf-8', errors='replace').read()))
    if codes['html'] == '200':
        t = html_text(open(os.path.join(out, 'paper.html'), encoding='utf-8', errors='replace').read())
        open(os.path.join(out, 'html.txt'), 'w', encoding='utf-8').write(t)
        res['html_chars'] = len(t)
    if codes['pdf'] == '200' and shutil.which('pdftotext'):
        r = subprocess.run(['pdftotext', '-layout', os.path.join(out, 'paper.pdf'), os.path.join(out, 'pdf.txt')], capture_output=True, text=True)
        res['pdf_text'] = r.returncode == 0
    json.dump(res, open(os.path.join(out, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if codes['abs'] == '200' and '200' in (codes['html'], codes['pdf']) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
