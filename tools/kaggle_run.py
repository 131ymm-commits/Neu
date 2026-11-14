#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Запуск опытов Neu на машинах Kaggle через официальный API (kagglesdk).

Ключ API Kaggle хранится в секретах среды; сетевой прокси подставляет его в заголовок Authorization запросов
к api.kaggle.com. В коде и в репозитории ключа нет — клиенту передаётся заглушка 'proxy-injected'.
Имя пользователя Kaggle в репозиторий не пишется: оно берётся из ответа API во время работы.

  python3 tools/kaggle_run.py quota                                   квоты ускорителей
  python3 tools/kaggle_run.py push SCRIPT.py --slug neu-x [--gpu] [--internet] [--timeout-s N]
  python3 tools/kaggle_run.py wait --slug neu-x [--every 30] [--limit-s 7200]
  python3 tools/kaggle_run.py output --slug neu-x --to DIR             скачать вывод последней версии
Ноутбуки создаются закрытыми (is_private), тип — скрипт Python.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from kagglesdk import kaggle_client
from kagglesdk.kernels.types import kernels_api_service as S
from kagglesdk.kernels.types.kernels_enums import KernelsListViewType

TOKEN = 'proxy-injected'          # настоящий ключ подставляет прокси


def client():
    return kaggle_client.KaggleClient(api_token=TOKEN)


def whoami(k):
    """Имя пользователя — по своему ноутбуку (без вывода в журнал)."""
    req = S.ApiListKernelsRequest()
    req.group = KernelsListViewType.PROFILE
    req.page_size = 1
    ks = k.kernels.kernels_api_client.list_kernels(req).kernels or []
    if not ks:
        sys.exit('нет ни одного своего ноутбука — имя пользователя не определить; создайте любой ноутбук на Kaggle')
    return ks[0].ref.split('/')[0]


def cmd_quota(a):
    with client() as k:
        r = k.kernels.kernels_api_client.get_accelerator_quota_statistics(S.ApiGetAcceleratorQuotaStatisticsRequest())
        print(json.dumps(r.to_dict() if hasattr(r, 'to_dict') else str(r), ensure_ascii=False, indent=1))


def cmd_push(a):
    text = open(a.script, encoding='utf-8').read()
    with client() as k:
        user = whoami(k)
        req = S.ApiSaveKernelRequest()
        req.slug = f'{user}/{a.slug}'
        req.new_title = a.slug
        req.text = text
        req.language = 'python'
        req.kernel_type = 'script'
        req.is_private = True
        req.enable_gpu = bool(a.gpu)
        req.enable_internet = bool(a.internet)
        if a.timeout_s:
            req.session_timeout_seconds = a.timeout_s
        r = k.kernels.kernels_api_client.save_kernel(req)
        d = r.to_dict() if hasattr(r, 'to_dict') else {}
        print('отправлено:', a.slug, '| версия', d.get('versionNumber'), '| ошибка' if d.get('error') else '', d.get('error') or '')


def status(k, user, slug):
    req = S.ApiGetKernelSessionStatusRequest()
    req.user_name, req.kernel_slug = user, slug
    r = k.kernels.kernels_api_client.get_kernel_session_status(req)
    d = r.to_dict() if hasattr(r, 'to_dict') else {}
    return str(d.get('status', '')).lower(), d.get('failureMessage')


def cmd_wait(a):
    t0 = time.time()
    with client() as k:
        user = whoami(k)
        while True:
            st, fail = status(k, user, a.slug)
            print(f'{int(time.time() - t0):5d} с  {st}', fail or '', flush=True)
            if any(w in st for w in ('complete', 'error', 'cancel')):
                sys.exit(0 if 'complete' in st else 1)
            if time.time() - t0 > a.limit_s:
                sys.exit('ожидание превысило предел')
            time.sleep(a.every)


def cmd_output(a):
    os.makedirs(a.to, exist_ok=True)
    with client() as k:
        user = whoami(k)
        req = S.ApiListKernelSessionOutputRequest()
        req.user_name, req.kernel_slug = user, a.slug
        r = k.kernels.kernels_api_client.list_kernel_session_output(req)
        d = r.to_dict() if hasattr(r, 'to_dict') else {}
        files = d.get('files') or []
        log = d.get('log')
        if log:
            open(os.path.join(a.to, 'kaggle_log.json'), 'w', encoding='utf-8').write(log)
        got, failed = 0, {}
        for f in files:
            name, url = f.get('fileName'), f.get('url')
            if not (name and url):
                continue
            try:
                urllib.request.urlretrieve(url, os.path.join(a.to, os.path.basename(name)))
                got += 1
            except Exception as e:                       # хост хранилища может быть закрыт сетью среды
                failed[urllib.parse.urlsplit(url).netloc] = type(e).__name__
        print('файлов в выводе:', len(files), '| скачано:', got, '| журнал:', 'есть' if log else 'нет', '→', a.to,
              '| не скачаны (хост → ошибка):' if failed else '', failed or '')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('quota')
    p = sub.add_parser('push'); p.add_argument('script'); p.add_argument('--slug', required=True)
    p.add_argument('--gpu', action='store_true'); p.add_argument('--internet', action='store_true')
    p.add_argument('--timeout-s', type=int, default=0)
    w = sub.add_parser('wait'); w.add_argument('--slug', required=True); w.add_argument('--every', type=int, default=30)
    w.add_argument('--limit-s', type=int, default=7200)
    o = sub.add_parser('output'); o.add_argument('--slug', required=True); o.add_argument('--to', required=True)
    a = ap.parse_args()
    {'quota': cmd_quota, 'push': cmd_push, 'wait': cmd_wait, 'output': cmd_output}[a.cmd](a)


if __name__ == '__main__':
    main()
