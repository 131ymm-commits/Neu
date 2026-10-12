#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_sealed2: драйвер голов «claude -p» по решению совета, заседание 29 (шаг 0, пункт (А)).

Спецификация: docs/council/2026-10-09_V24-V26_session29.md, раздел «1. Решение», пункт «(А)»,
а также голоса (раздел «votes») и «4. Что проверить первым», пункт 1.

КАК ЗАПУСКАТЬ (из корня репозитория):
  python3 tools/run_sealed2.py probe --out tools/fixtures/run_sealed2_probe.jsonl [--dry-run]
      Единственный пробный вызов закреплённым бинарём (модель claude-haiku-5-5, --tools "", промпт «Ответь одним словом: да»).
      Повторный запуск запрещён маркером .cache/claude-cli/probe_done.json. --dry-run только печатает команду и
      имена переменных среды, модель не вызывает.
  python3 tools/run_sealed2.py run --jobs JOBS.jsonl --seed ЗЕРНО --journal ЖУРНАЛ --streams ПОТОКИ
          [--config CFG.json] [--parallel 1] [--max-calls N]
      Прогон голов. JOBS.jsonl: строка на вызов {"task", "id", "arm"(необязательно), "prompt", "schema"}.
      Продолжение с места: итоговые вызовы из журнала не запрашиваются заново. Конфигурация и jobs сверяются
      с ЖУРНАЛ/run_config.json; при расхождении драйвер останавливается.
      --task-from-id: задания в формате run_sealed v1 ({id, prompt, schema}), задача и рука берутся из id «задача|рука|i».
  python3 tools/run_sealed2.py summary --journal ЖУРНАЛ
      Сводка по рукам: годные, потерянные, попытки «нет ответа», ожидания, повторы, api_retry, подмены модели,
      многоходовые ответы, вызовы без записи (по run_log.jsonl), число вариантов init.
  python3 tools/run_sealed2.py export --journal ЖУРНАЛ --out run/<этап>_out.jsonl
      Итоги в формате run_sealed v1 для harness.py SELECT-01 (годный → result; потерян → error).

ЧТО ПИШЕТСЯ:
  ЖУРНАЛ/<задача>.jsonl (в git): по записи на каждый вызов. Поля: outcome (годный / нет ответа / сбой ответа),
    final (годный / потерян; у «нет ответа» пусто), reason, flags (api_retry до и после начала ответа, оборванный
    ход), cli_init_version (claude_code_version из события init), binary_sha256, model_target, model_usage_keys
    (модели по modelUsage), effort, thinking_budget, thinking_tokens, env_config (значения переменных из списка
    конфигурации), env_access_names (только имена переменных доступа), usage (inp, out, cost_usd), answer,
    waits (число ожиданий сброса лимита), retries (число повторов), stream (sha256 сырого потока и поток без
    content_block_delta), config_sha256, init_sha256. В потоке журнала подписи размышлений заменены длиной и
    sha256, события thinking_tokens сведены в одно, init — короткая форма (полная — ЖУРНАЛ/init_<sha12>.json).
  ЖУРНАЛ/run_config.json: конфигурация прогона; ЖУРНАЛ/run_log.jsonl: старты, начало каждого вызова, остановки.
  ПОТОКИ/<задача>/*.jsonl.gz: полный поток stream-json (gzip, вне git), *.err.gz: stderr.

КЛАССЫ ИСХОДА:
  годный: итоговое событие без ошибок, есть structured_output, usage > 0, modelUsage только у целевой модели,
    нет api_retry после начала ответа и нет оборванного хода.
  нет ответа: не голос и не ошибка, попытка не тратится. Два случая: (а) итог с usage, где inp = out = cost = 0;
    (б) таймаут или гибель процесса при записанном потоке без message_start. Лимит с временем сброса драйвер
    ждёт и повторяет вызов; без времени сброса и при таймауте до начала ответа повторов ограниченное число.
  сбой ответа: всё остальное (отказ, неразборный вывод, нет structured_output, таймаут после начала ответа,
    api_retry после начала, оборванный ход, ответ не целевой модели, запись без usage). Повтора нет, вызов
    записывается как «потерян». Повтор для вторичного анализа (параметр secondary_retry) пишется только в журнал.

ОСТАНОВКИ (записи не меняются, продолжение — тем же запуском): процесс головы не запустился (записи нет);
  «потерян» при пустом потоке (запись есть); max_consecutive_lost «потерян» подряд; исчерпаны повторы «нет ответа»;
  ожидание сброса дольше max_single_wait_s; смена конфигурации, бинаря или версии CLI; claude_code_version_too_old.
ВРЕМЯ СБРОСА ЛИМИТА: из rate_limit_event со статусом отказа (поле resetsAt), иначе из текста итога «resets …».

Стандартная библиотека, Python 3.11. Версии и sha256 закреплены ниже; при расхождении бинарь перекачивается с PyPI.
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import urllib.request
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / '.cache' / 'claude-cli'          # закреплённый бинарь и рабочие каталоги; в git не кладётся

# Закреплённый бинарь: CLI 2.1.294 из колеса claude-agent-sdk==0.2.165 (файл claude_agent_sdk/_bundled/claude).
PINNED_VERSION = '2.1.294'
PINNED_BIN_SHA256 = '27122ca7b624f537546fbef35b80c66370d974ff258f3d9b10ac50bb8771f262'
WHEEL_NAME = 'claude_agent_sdk-0.2.165-py3-none-manylinux_2_17_x86_64.whl'
WHEEL_SHA256 = '9dbee4bfc69f0bb27ee455afdc19d78f958540a99217d2e28831fb9b7d496f08'
WHEEL_MEMBER = 'claude_agent_sdk/_bundled/claude'
PYPI_JSON_URL = 'https://pypi.org/pypi/claude-agent-sdk/0.2.165/json'

OK, NA, FAIL = 'годный', 'нет ответа', 'сбой ответа'   # классы исхода (в журнале — как есть)
PROBE_MODEL = 'claude-haiku-5-5'
PROBE_PROMPT = 'Ответь одним словом: да'
PROBE_SCHEMA = {'type': 'object', 'properties': {'answer': {'type': 'string'}},
                'required': ['answer'], 'additionalProperties': False}


def default_config():
    """Явная конфигурация головы. Всё, что здесь, пишется в run_config.json и сверяется при продолжении.

    Значения по умолчанию взяты из спецификации или из того, что v1 получала из среды оркестратора
    (MAX_THINKING_TOKENS=31999). Выбранные здесь значения, которых нет в спецификации, помечены в отчёте.
    """
    return {
        'cli': {'bin': str(CACHE / PINNED_VERSION / 'claude'), 'version': PINNED_VERSION,
                'sha256': PINNED_BIN_SHA256, 'wheel': WHEEL_NAME, 'wheel_sha256': WHEEL_SHA256},
        'model': 'claude-opus-5-5',          # модель голов SELECT-01 (как в v1)
        'effort': 'high',                    # один на все руки; значение API по умолчанию, см. отчёт
        'env_explicit': {                    # переменные, которые задаются явно
            'MAX_THINKING_TOKENS': '31999',
            'CLAUDE_CODE_MAX_RETRIES': '0',  # повторяет только драйвер
            'API_TIMEOUT_MS': '1200000',
            'CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS': '180000',
            'CLAUDE_BYTE_STREAM_IDLE_TIMEOUT_MS': '180000',
            'CLAUDE_STREAM_IDLE_TIMEOUT_MS': '180000',
            'CLAUDE_ENABLE_STREAM_WATCHDOG': '1',
            'CLAUDE_ENABLE_BYTE_WATCHDOG': '1',
            'DISABLE_GROWTHBOOK': '1',
            'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
            'DISABLE_AUTOUPDATER': '1',
        },
        'env_removed': ['CLAUDE_CODE_EFFORT_LEVEL', 'CLAUDE_CODE_MAX_OUTPUT_TOKENS'],
        # Среда головы собирается с нуля по белому списку. Из оркестратора берутся только эти имена.
        'env_system': ['PATH', 'LANG', 'LC_ALL'],
        'env_access': ['HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy', 'NO_PROXY', 'no_proxy',
                       'NODE_EXTRA_CA_CERTS', 'SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE',
                       'ANTHROPIC_BASE_URL', 'CLAUDE_SESSION_INGRESS_TOKEN_FILE', 'CLAUDE_CODE_PROXY_RESOLVES_HOSTS'],
        'home': str(CACHE / 'home'),         # свой HOME, без кеша оркестратора
        'work_dir': str(CACHE / 'work'),     # пустая рабочая папка на каждый вызов
        'call_timeout_s': 1800,              # таймаут драйвера, один для всех рук
        'zero_retry_limit': 3,               # повторы при нуле токенов без времени сброса
        'start_timeout_retry_limit': 3,      # повторы при таймауте до message_start
        'backoff_base_s': 300,
        'backoff_cap_s': 3600,
        'limit_margin_s': 120,               # запас после времени сброса
        'max_single_wait_s': 26 * 3600,      # дольше ждать одним ожиданием нельзя
        'max_limit_waits_per_job': 30,
        'max_consecutive_lost': 3,           # столько «потерян» подряд (по времени записи) — остановка для разбора
        'secondary_retry': False,            # повтор после «сбоя ответа» только в журнал (вторичный анализ)
    }


def config_diff(old, new, prefix=''):
    """Список расхождений двух конфигураций (по путям ключей)."""
    diffs = []
    for k in sorted(set(old) | set(new), key=str):
        a, b = old.get(k, '<нет>'), new.get(k, '<нет>')
        p = f'{prefix}{k}'
        if isinstance(a, dict) and isinstance(b, dict):
            diffs += config_diff(a, b, p + '.')
        elif a != b:
            diffs.append(f'{p}: было {a!r}, стало {b!r}')
    return diffs


def load_config(path=None):
    cfg = default_config()
    if path:
        user = json.loads(Path(path).read_text(encoding='utf-8'))
        for k, v in user.items():
            if k not in cfg:
                raise SystemExit(f'неизвестный ключ конфигурации: {k}')
            cfg[k] = v
    return cfg


class RunStop(Exception):
    """Остановка прогона. Текст — причина, она уходит в run_log.jsonl и пользователю."""


class _Stopped(Exception):
    """Внутренний сигнал: прогон остановила другая рука."""


# ---------- утилиты ----------

def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return None if dt is None else dt.astimezone(timezone.utc).isoformat(timespec='seconds')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def safe(name):
    """Имя файла из id: только ASCII, без путей."""
    s = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(name)).strip('_')[:80]
    return s or 'x'


def sha8(text):
    return hashlib.sha256(str(text).encode('utf-8')).hexdigest()[:8]


def order_jobs(jobs, seed, task):
    """Порядок рук одной задачи «вперемешку в порядке от зерна».

    Перестановка Фишера — Йетса: на шаге i индекс j берётся из sha256(зерно|задача|i). Вход сортируется по id,
    поэтому порядок зависит только от зерна, задачи и набора id, и повторяется при любом перезапуске.
    """
    items = sorted(jobs, key=lambda j: j['id'])
    for i in range(len(items) - 1, 0, -1):
        h = hashlib.sha256(f'{seed}|{task}|{i}'.encode('utf-8')).digest()
        j = int.from_bytes(h[:8], 'big') % (i + 1)
        items[i], items[j] = items[j], items[i]
    return items


def build_env(cfg):
    """Среда головы: белый список из оркестратора, затем явная конфигурация. Лишнее не передаётся."""
    env = {}
    for name in list(cfg['env_system']) + list(cfg['env_access']):
        if name in os.environ:
            env[name] = os.environ[name]
    for name in cfg['env_removed']:
        env.pop(name, None)
    env.update(cfg['env_explicit'])
    env['HOME'] = cfg['home']
    return env


def access_names_passed(cfg):
    """Имена переменных, которые реально переданы (значения в журнал не пишутся)."""
    return sorted(n for n in list(cfg['env_system']) + list(cfg['env_access']) if n in os.environ)


def build_cmd(cfg, job):
    return [cfg['cli']['bin'], '-p', job['prompt'],
            '--tools', '', '--setting-sources', '', '--strict-mcp-config', '--no-session-persistence',
            '--model', cfg['model'], '--effort', cfg['effort'],
            '--output-format', 'stream-json', '--verbose', '--include-partial-messages',
            '--json-schema', json.dumps(job['schema'], ensure_ascii=False)]


# ---------- закреплённый бинарь ----------

def extract_member(wheel, member, dest, expected_sha256, wheel_sha256=None):
    """Достаёт файл из колеса, проверяет sha256 и кладёт в dest. Несовпадение — RunStop, dest не создаётся."""
    wheel, dest = Path(wheel), Path(dest)
    if wheel_sha256 and sha256_file(wheel) != wheel_sha256:
        raise RunStop(f'sha256 колеса {wheel.name} не совпал с закреплённым')
    with zipfile.ZipFile(wheel) as z:
        data = z.read(member)
    if sha256_bytes(data) != expected_sha256:
        raise RunStop(f'sha256 файла {member} из колеса не совпал с закреплённым')
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.tmp')
    tmp.write_bytes(data)
    os.chmod(tmp, 0o755)
    os.replace(tmp, dest)


def download_pinned(cfg):
    """Перекачивает закреплённое колесо с PyPI, проверяет sha256 колеса и бинаря, кладёт бинарь на место."""
    c = cfg['cli']
    work = CACHE / 'download' / uuid.uuid4().hex
    work.mkdir(parents=True, exist_ok=False)
    try:
        with urllib.request.urlopen(PYPI_JSON_URL, timeout=120) as r:
            meta = json.load(r)
        ent = [u for u in meta.get('urls', []) if u.get('filename') == c['wheel']]
        if not ent:
            raise RunStop(f'на PyPI нет колеса {c["wheel"]}')
        if ent[0].get('digests', {}).get('sha256') != c['wheel_sha256']:
            raise RunStop('sha256 колеса на PyPI не совпал с закреплённым: остановка')
        whl = work / c['wheel']
        with urllib.request.urlopen(ent[0]['url'], timeout=600) as r, open(whl, 'wb') as fh:
            shutil.copyfileobj(r, fh)
        extract_member(whl, WHEEL_MEMBER, Path(c['bin']), c['sha256'], wheel_sha256=c['wheel_sha256'])
    finally:
        shutil.rmtree(work, ignore_errors=True)


class BinaryGuard:
    """Проверка sha256 бинаря: при старте и затем при каждом вызове, если файл изменился (размер, mtime)."""

    def __init__(self, cfg, log=None):
        self.cfg = cfg
        self.sig = None
        self.sha = None
        self.log = log or (lambda msg: None)

    def check(self):
        p = Path(self.cfg['cli']['bin'])
        exp = self.cfg['cli']['sha256']
        st = p.stat() if p.exists() else None
        sig = (st.st_size, st.st_mtime_ns) if st else None
        if sig is not None and sig == self.sig:
            return self.sha
        sha = sha256_file(p) if st else None
        if sha != exp:
            self.log('бинарь не совпал с закреплённым sha256: перекачиваю колесо с PyPI')
            download_pinned(self.cfg)
            st = p.stat()
            sha = sha256_file(p)
            if sha != exp:
                raise RunStop('бинарь не совпал с закреплённым sha256 даже после загрузки с PyPI')
        self.sig = (st.st_size, st.st_mtime_ns)
        self.sha = sha
        return sha


# ---------- поток и итог ----------

@dataclass
class Final:
    """Итоговое событие result в нормальном виде. None в поле — значение не записано (не подставляется нулём)."""
    inp: int | None
    out: int | None
    cost: float | None
    thinking: int | None
    model_usage: dict | None
    structured: object
    is_error: bool
    subtype: str | None
    text: str
    perm: int | None


@dataclass
class Verdict:
    outcome: str
    reason: str
    flags: dict = field(default_factory=dict)
    limit_text: str | None = None   # текст итога, где может быть время сброса
    kind: str | None = None         # для «нет ответа»: 'zero' (нулевой usage) или 'start' (таймаут до старта)


@dataclass
class CallResult:
    events: list
    lines: list = field(default_factory=list)       # сырые строки stdout (байты), для пробного образца
    unparsable: int = 0
    timed_out: bool = False
    returncode: int | None = None
    stream_path: Path | None = None
    stream_sha256: str | None = None                # sha256 сырого потока stdout (байты как пришли, до gzip)
    stream_bytes: int = 0
    stderr_bytes: int = 0
    stderr_sha256: str | None = None
    started: datetime | None = None
    finished: datetime | None = None
    spawn_error: str | None = None
    too_old: bool = False

    @property
    def init_version(self):
        for e in self.events:
            if e.get('type') == 'system' and e.get('subtype') == 'init':
                return e.get('claude_code_version')
        return None

    @property
    def results(self):
        return [e for e in self.events if e.get('type') == 'result']

    @property
    def results_count(self):
        return len(self.results)

    @property
    def last_result(self):
        r = self.results
        return r[-1] if r else None


def is_delta(e):
    return e.get('type') == 'stream_event' and (e.get('event') or {}).get('type') == 'content_block_delta'


SECRET_KEY_RE = re.compile(r'(?i)(email|secret|password|api[_-]?key|authorization|cookie|'
                           r'access[_-]?token|refresh[_-]?token|session[_-]?token|bearer)')
EMAIL_RE = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
TOKEN_RES = [re.compile(r'sk-ant-[A-Za-z0-9_\-]{8,}'),
             re.compile(r'eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}'),
             re.compile(r'(?i)bearer\s+[A-Za-z0-9._\-]{8,}')]
PATH_RE = re.compile(r'/(?:home|root|tmp|opt|run|var|etc)/[^\s"\\]*')


def scrub_text(s, paths=False):
    s = EMAIL_RE.sub('<почта>', s)
    for rx in TOKEN_RES:
        s = rx.sub('<секрет>', s)
    if paths:
        s = PATH_RE.sub('<путь>', s)
    return s


def redact(obj, paths=False):
    if isinstance(obj, dict):
        return {k: redact(v, paths) for k, v in obj.items() if not SECRET_KEY_RE.search(str(k))}
    if isinstance(obj, list):
        return [redact(v, paths) for v in obj]
    if isinstance(obj, str):
        return scrub_text(obj, paths)
    return obj


INIT_KEEP = ('type', 'subtype', 'model', 'tools', 'mcp_servers', 'permissionMode', 'claude_code_version',
             'output_style')
INIT_VOLATILE = ('session_id', 'uuid', 'cwd', 'memory_paths', 'messaging_socket_path')


def find_init(events):
    return next((e for e in events or [] if e.get('type') == 'system' and e.get('subtype') == 'init'), None)


def init_full(e):
    """Событие init без изменчивых полей (id сессии, пути) и без секретов — то, что сверяется между вызовами."""
    return redact({k: v for k, v in e.items() if k not in INIT_VOLATILE}, paths=True)


def init_sha(e):
    return sha256_bytes(canonical(init_full(e)).encode('utf-8'))


EVENT_DROP = ('uuid', 'session_id')    # повторяются в каждом событии; session_id пишется в запись один раз


def _slim(obj, top=True):
    """Подпись размышлений (signature) — непрозрачный блок, растёт с длиной размышлений: в журнал — длина и sha256.
    У событий верхнего уровня убираются uuid и session_id."""
    if isinstance(obj, dict):
        return {k: ({'длина': len(v), 'sha256': sha256_bytes(v.encode('utf-8'))}
                    if k == 'signature' and isinstance(v, str) and v else _slim(v, False))
                for k, v in obj.items() if not (top and k in EVENT_DROP)}
    if isinstance(obj, list):
        return [_slim(v, False) for v in obj]
    return obj


def journal_events(events):
    """Поток для журнала (git): без content_block_delta, с вычищенными секретами и адресами e-mail.

    Чтобы журнал тысяч вызовов помещался в git: подпись размышлений → длина и sha256; события
    system/thinking_tokens → одно сводное в конце (число событий, последняя оценка); init → короткая форма и
    sha256 полной (полная пишется один раз в ЖУРНАЛ/init_<sha12>.json). Полный поток — gzip вне git.
    """
    out, think_n, think_last = [], 0, None
    for e in events:
        if is_delta(e):
            continue
        if e.get('type') == 'system' and e.get('subtype') == 'thinking_tokens':
            think_n += 1
            think_last = e.get('estimated_tokens', think_last)
            continue
        if e.get('type') == 'system' and e.get('subtype') == 'init':
            full = init_full(e)
            slim = {k: full[k] for k in INIT_KEEP if k in full}
            slim['init_sha256'] = init_sha(e)
            out.append(slim)
            continue
        out.append(_slim(redact(e)))
    if think_n:
        out.append({'type': 'system', 'subtype': 'thinking_tokens_сводка', 'событий': think_n,
                    'последняя_оценка': think_last})
    return out


def summarize(events):
    """Разбор потока: начат ли ответ, оборванные ходы, api_retry до и после начала, причины остановки хода."""
    s = {'started': False, 'open': False, 'aborted': False, 'retry_before': 0, 'retry_after': 0,
         'stop_reasons': [], 'message_starts': 0}
    for e in events:
        t = e.get('type')
        if t == 'system' and e.get('subtype') == 'api_retry':
            if s['open']:
                s['retry_after'] += 1
            else:
                s['retry_before'] += 1
            continue
        inner = e.get('event') if t == 'stream_event' else None
        if not isinstance(inner, dict):
            continue
        it = inner.get('type')
        if it == 'message_start':
            if s['open']:
                s['aborted'] = True          # предыдущий ход не закрыт message_stop
            s['open'] = True
            s['started'] = True
            s['message_starts'] += 1
        elif it == 'message_stop':
            s['open'] = False
        elif it == 'message_delta':
            sr = (inner.get('delta') or {}).get('stop_reason')
            if sr:
                s['stop_reasons'].append(sr)
    if s['open']:
        s['aborted'] = True                  # поток кончился внутри хода
    return s


def normalize_final(ev):
    """Итоговое событие → Final. Недостающие поля остаются None: нулём их не заменяем."""
    if ev is None:
        return None
    u = ev.get('usage')
    inp = out = thinking = None
    if isinstance(u, dict):
        keys = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')
        if all(isinstance(u.get(k), int) for k in keys):
            inp = u['input_tokens'] + u['cache_creation_input_tokens'] + u['cache_read_input_tokens']
            out = u['output_tokens']
        det = u.get('output_tokens_details')
        if isinstance(det, dict) and isinstance(det.get('thinking_tokens'), int):
            thinking = det['thinking_tokens']
    cost = ev.get('total_cost_usd')
    cost = cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None
    mu = ev.get('modelUsage')
    perm = ev.get('permission_denials')
    perm_n = len(perm) if isinstance(perm, list) else (perm if isinstance(perm, int) else None)
    return Final(inp=inp, out=out, cost=cost, thinking=thinking,
                 model_usage=mu if isinstance(mu, dict) else None,
                 structured=ev.get('structured_output'), is_error=bool(ev.get('is_error')),
                 subtype=ev.get('subtype'), text=str(ev.get('result') or ''), perm=perm_n)


def is_target_model(key, target):
    """Совпадение с целевой моделью: точное имя или снимок с датой (-YYYYMMDD)."""
    return key == target or re.fullmatch(re.escape(target) + r'-\d{8}', key) is not None


def classify(final, *, events, unparsable=0, timed_out=False, returncode=None, target_model,
             legacy=False, results_count=1):
    """Класс исхода одного вызова. Порядок проверок важен: сначала «нет ответа», потом всё остальное."""
    s = summarize(events) if events is not None else None
    flags = {}
    if s is not None:
        flags = {'api_retry_до_начала': s['retry_before'], 'api_retry_после_начала': s['retry_after'],
                 'оборванный_ход': s['aborted'], 'message_start': s['message_starts']}
    # 1. итог с usage, где inp = out = cost = 0: лимит аккаунта или иной отказ без токенов
    if final is not None and final.inp == 0 and final.out == 0 and final.cost == 0:
        return Verdict(NA, 'итог с usage, inp = out = cost = 0', flags, limit_text=final.text, kind='zero')
    # 2. таймаут или гибель процесса без итога
    if final is None and (timed_out or returncode not in (0, None)):
        if events and not s['started']:
            return Verdict(NA, 'таймаут или гибель до message_start (поток записан, message_start нет)',
                           flags, kind='start')
        return Verdict(FAIL, 'таймаут или гибель после начала ответа либо без записанного потока', flags)
    # 3. всё остальное
    if events is None and not legacy:
        return Verdict(FAIL, 'потока нет', flags)
    if unparsable:
        return Verdict(FAIL, f'неразборный вывод: строк {unparsable}', flags)
    if s is not None:
        if 'refusal' in s['stop_reasons']:
            return Verdict(FAIL, 'отказ модели (stop_reason = refusal)', flags)
        if 'max_tokens' in s['stop_reasons']:
            return Verdict(FAIL, 'ответ обрезан по max_tokens', flags)
    if timed_out:
        return Verdict(FAIL, 'таймаут при записанном итоге', flags)
    if returncode not in (0, None):
        return Verdict(FAIL, f'ненулевой код выхода {returncode}', flags)
    if results_count > 1:
        return Verdict(FAIL, f'несколько итоговых событий: {results_count}', flags)
    if final is None:
        return Verdict(FAIL, 'нет итогового события result', flags)
    if final.is_error:
        return Verdict(FAIL, 'ошибка ответа: ' + final.text[:200], flags)
    if final.subtype not in (None, 'success'):
        return Verdict(FAIL, f'итог не success: {final.subtype}', flags)
    if final.inp is None or final.out is None:
        return Verdict(FAIL, 'usage отсутствует или неполный', flags)
    if final.cost is None:
        return Verdict(FAIL, 'стоимость не записана', flags)
    if final.inp + final.out <= 0:
        return Verdict(FAIL, 'токенов нет при непустом итоге', flags)
    if final.structured is None:
        return Verdict(FAIL, 'нет structured_output (отказ или неразборный ответ)', flags)
    if final.perm:
        return Verdict(FAIL, f'попытки вызова инструментов: {final.perm}', flags)
    if not final.model_usage:
        return Verdict(FAIL, 'нет modelUsage', flags)
    foreign = sorted(k for k in final.model_usage if not is_target_model(k, target_model))
    if foreign:
        return Verdict(FAIL, 'ответ не целевой модели: ' + ', '.join(foreign), flags)
    if s is not None:
        if s['aborted']:
            return Verdict(FAIL, 'оборванный ход: message_start без message_stop', flags)
        if s['retry_after']:
            return Verdict(FAIL, 'api_retry после начала ответа', flags)
    return Verdict(OK, 'годный', flags)


def verdict_for(res, cfg):
    return classify(normalize_final(res.last_result), events=res.events, unparsable=res.unparsable,
                    timed_out=res.timed_out, returncode=res.returncode, target_model=cfg['model'],
                    results_count=res.results_count)


MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
RESET_RE = re.compile(r'resets\s+(?:(' + '|'.join(MONTHS) + r')[a-z]*\.?\s+(\d{1,2}),?\s+(?:at\s+)?)?'
                      r'(\d{1,2})(?::(\d{2}))?\s*([ap]m)\s*\(UTC\)', re.IGNORECASE)


def next_reset(text, now):
    """Время сброса из текста вида «resets 7:30pm (UTC)» или «resets Oct 14, 7pm (UTC)».

    Без даты: если время уже прошло недавно (до 10 минут) — сразу, иначе завтра. С датой: этот год, а если дата
    прошла больше чем на 10 минут — следующий. Запасной путь: основной — reset_from_events.
    """
    m = RESET_RE.search(text or '')
    if not m:
        return None
    hour = int(m.group(3)) % 12 + (12 if m.group(5).lower() == 'pm' else 0)
    minute = int(m.group(4) or 0)
    now = now.astimezone(timezone.utc)
    if m.group(1):
        month, day = MONTHS.index(m.group(1)[:3].lower()) + 1, int(m.group(2))
        try:
            cand = datetime(now.year, month, day, hour, minute, tzinfo=timezone.utc)
            if now - cand > timedelta(minutes=10):
                cand = cand.replace(year=now.year + 1)
        except ValueError:
            return None
        return max(cand, now)
    cand = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cand <= now:
        cand = now if (now - cand) <= timedelta(minutes=10) else cand + timedelta(days=1)
    return cand


LIMIT_OK_STATUSES = ('allowed', 'allowed_warning')


def reset_from_events(events):
    """Время сброса из последнего rate_limit_event со статусом отказа (не allowed / allowed_warning).

    Поле rate_limit_info.resetsAt — секунды unix (в образце пробного вызова: 1791821400); число больше 1e12
    считается миллисекундами. Нет такого события — None (тогда время ищется в тексте итога).
    """
    best = None
    for e in events or []:
        if e.get('type') != 'rate_limit_event':
            continue
        info = e.get('rate_limit_info') or {}
        if info.get('status') in LIMIT_OK_STATUSES:
            continue
        ts = info.get('resetsAt')
        if isinstance(ts, (int, float)) and not isinstance(ts, bool) and ts > 0:
            best = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts, timezone.utc)
    return best


def legacy_final(rec):
    """Старая запись пилота 2 SELECT-01 (итоговый JSON без потока) → Final. Поля берутся как записаны."""
    err = rec.get('error')
    text = err or ''
    prefix = 'нет structured_output: '
    if err and text.startswith(prefix):
        text = text[len(prefix):]
    models = rec.get('models')
    return Final(inp=rec.get('inp'), out=rec.get('out'), cost=rec.get('cost_usd'), thinking=rec.get('thinking'),
                 model_usage=({m: {'outputTokens': v} for m, v in models.items()} if isinstance(models, dict) else None),
                 structured=rec.get('result'), is_error=bool(err), subtype='success', text=text,
                 perm=rec.get('permission_denials'))


# ---------- вызов головы ----------

def real_call(cfg, job, gz_path):
    """Один вызов claude -p. Пишет полный поток в gzip (вне git) и разбирает его построчно."""
    gz_path = Path(gz_path)
    gz_path.parent.mkdir(parents=True, exist_ok=True)
    err_path = gz_path.with_name(gz_path.name[:-len('.jsonl.gz')] + '.err.gz')
    work = Path(cfg['work_dir']) / uuid.uuid4().hex
    work.mkdir(parents=True, exist_ok=False)
    Path(cfg['home']).mkdir(parents=True, exist_ok=True)
    res = CallResult(events=[], stream_path=gz_path, started=utcnow())
    err_chunks = []
    counters = {'unparsable': 0}
    raw_hash = hashlib.sha256()
    try:
        with open(gz_path, 'wb') as raw_fh, gzip.GzipFile(filename='', mode='wb', fileobj=raw_fh, mtime=0) as gz:
            proc = None
            try:
                proc = subprocess.Popen(build_cmd(cfg, job), cwd=str(work), env=build_env(cfg),
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=True)
            except OSError as e:
                res.spawn_error = f'{type(e).__name__}: {e}'
            if proc is not None:
                def read_out():
                    for line in proc.stdout:
                        gz.write(line)
                        raw_hash.update(line)
                        res.stream_bytes += len(line)
                        res.lines.append(line)
                        s = line.strip()
                        if not s:
                            continue
                        try:
                            obj = json.loads(s.decode('utf-8'))
                        except (UnicodeDecodeError, ValueError):
                            counters['unparsable'] += 1
                            continue
                        if isinstance(obj, dict):
                            res.events.append(obj)
                        else:
                            counters['unparsable'] += 1

                def read_err():
                    for chunk in iter(lambda: proc.stderr.read(65536), b''):
                        err_chunks.append(chunk)

                t_out = threading.Thread(target=read_out, daemon=True)
                t_err = threading.Thread(target=read_err, daemon=True)
                t_out.start()
                t_err.start()
                try:
                    res.returncode = proc.wait(timeout=cfg['call_timeout_s'])
                except subprocess.TimeoutExpired:
                    res.timed_out = True
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    res.returncode = proc.wait()
                t_out.join(120)
                t_err.join(120)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    res.stream_sha256 = raw_hash.hexdigest()
    err_bytes = b''.join(err_chunks)
    with open(err_path, 'wb') as err_fh, gzip.GzipFile(filename='', mode='wb', fileobj=err_fh, mtime=0) as eg:
        eg.write(err_bytes)
    res.stderr_bytes = len(err_bytes)
    res.stderr_sha256 = sha256_bytes(err_bytes)
    res.unparsable = counters['unparsable']
    res.too_old = any(b'claude_code_version_too_old' in ln for ln in res.lines) or \
        b'claude_code_version_too_old' in err_bytes
    res.finished = utcnow()
    return res


# ---------- журнал, состояние заданий, драйвер ----------

@dataclass
class JobState:
    attempts: int = 0
    waits: int = 0
    retries: int = 0
    streak: int = 0
    final: str | None = None
    pause: datetime | None = None


def parse_iso(text):
    return datetime.fromisoformat(text) if text else None


def states_from_records(recs):
    states = {}
    for r in recs:
        st = states.setdefault(r['job'], JobState())
        st.attempts += 1
        if r.get('role') == 'основной':
            st.waits = r.get('waits', 0)
            st.retries = r.get('retries', 0)
            st.streak = r.get('streak', 0)
            st.pause = parse_iso(r.get('limit_reset_at'))
            if r.get('final'):
                st.final = r['final']
    return states


class Driver:
    def __init__(self, cfg, *, seed, jobs_sha256, journal_dir, streams_dir, parallel=1, max_calls=None,
                 call_fn=None, pre_call_check=None, now_fn=None, sleep_fn=None, log=None):
        self.cfg = cfg
        self.seed = seed
        self.jobs_sha256 = jobs_sha256
        self.journal_dir = Path(journal_dir)
        self.streams_dir = Path(streams_dir)
        self.parallel = max(1, int(parallel))
        self.max_calls = max_calls
        self.call_fn = call_fn or real_call
        self.log = log or (lambda msg: print(msg, file=sys.stderr, flush=True))
        if pre_call_check is None:
            self.guard = BinaryGuard(cfg, log=self.log)
            pre_call_check = self.guard.check
        self.pre_call_check = pre_call_check
        self.now_fn = now_fn or utcnow
        self.sleep_fn = sleep_fn
        self.lock = threading.Lock()
        self.file_locks = {}
        self.stop = threading.Event()
        self.pause_until = None
        self.calls = 0
        self.lost_streak = 0
        self.config_sha = None
        self.run_cfg = None
        self.bin_sha = None

    # журнал
    def _journal_path(self, task):
        return self.journal_dir / f'{safe(task)}.jsonl'

    def _file_lock(self, path):
        with self.lock:
            return self.file_locks.setdefault(str(path), threading.Lock())

    def _append(self, task, rec):
        path = self._journal_path(task)
        with self._file_lock(path):
            with open(path, 'a', encoding='utf-8') as fh:     # без sort_keys: ответ головы хранится в порядке ключей потока
                fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
                fh.flush()
                os.fsync(fh.fileno())

    def _read_journal(self, task):
        path = self._journal_path(task)
        recs = []
        if path.exists():
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    if not line.strip():
                        continue
                    try:
                        recs.append(json.loads(line))
                    except ValueError as e:
                        raise RunStop(f'журнал повреждён: {path.name}, строка {n}: {e}')
        return recs

    def _save_init(self, events):
        """Полное событие init (без изменчивых полей) — один раз на вариант в ЖУРНАЛ/init_<sha12>.json; вернуть sha256."""
        e = find_init(events)
        if e is None:
            return None
        sha = init_sha(e)
        path = self.journal_dir / f'init_{sha[:12]}.json'
        with self._file_lock(path):
            if not path.exists():
                path.write_text(json.dumps(init_full(e), ensure_ascii=False, indent=1, sort_keys=True) + '\n',
                                encoding='utf-8')
        return sha

    def _log_run(self, event, data):
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        rec = {'at': iso(self.now_fn()), 'event': event, **data}
        with self._file_lock(self.journal_dir / 'run_log.jsonl'):
            with open(self.journal_dir / 'run_log.jsonl', 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n')

    # конфигурация и старт
    def start(self):
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.streams_dir.mkdir(parents=True, exist_ok=True)
        run_cfg = dict(self.cfg, seed=self.seed, jobs_sha256=self.jobs_sha256)
        path = self.journal_dir / 'run_config.json'
        if path.exists():
            old = json.loads(path.read_text(encoding='utf-8'))
            diffs = config_diff(old, run_cfg)
            if diffs:
                raise RunStop('конфигурация отличается от записанной в run_config.json: ' + '; '.join(diffs))
        else:
            path.write_text(json.dumps(run_cfg, ensure_ascii=False, indent=1, sort_keys=True) + '\n',
                            encoding='utf-8')
        self.run_cfg = run_cfg
        self.config_sha = sha256_bytes(canonical(run_cfg).encode('utf-8'))
        self.bin_sha = self.pre_call_check() or self.bin_sha
        self._log_run('старт', {'config_sha256': self.config_sha, 'binary_sha256': self.bin_sha})

    def _set_pause(self, until):
        with self.lock:
            if self.pause_until is None or until > self.pause_until:
                self.pause_until = until

    def _sleep(self, seconds):
        if self.sleep_fn is not None:
            self.sleep_fn(seconds)
            return
        if self.stop.wait(seconds):
            raise _Stopped()

    def _gate(self):
        while True:
            if self.stop.is_set():
                raise _Stopped()
            with self.lock:
                until = self.pause_until
            if until is None:
                return
            left = (until - self.now_fn()).total_seconds()
            if left <= 0:
                return
            self._sleep(min(left, 30))

    def _one_call(self, job, attempt, role):
        with self.lock:
            if self.max_calls is not None and self.calls >= self.max_calls:
                raise RunStop(f'потолок вызовов {self.max_calls} исчерпан')
            self.calls += 1
        self.bin_sha = self.pre_call_check() or self.bin_sha
        tag = 'osn' if role == 'основной' else 'vtor'
        base = self.streams_dir / safe(job['task']) / f"{safe(job['id'])}-{sha8(job['id'])}.a{attempt:03d}.{tag}"
        gz = base.with_name(base.name + '.jsonl.gz')
        n = 1
        while gz.exists():                     # вызов, оборванный гибелью драйвера: его поток не перезаписывается
            n += 1
            gz = base.with_name(f'{base.name}.r{n}.jsonl.gz')
        self._log_run('вызов', {'task': job['task'], 'job': job['id'], 'arm': job.get('arm'), 'attempt': attempt,
                                'role': role, 'поток': gz.name})
        res = self.call_fn(self.cfg, job, gz)
        if res.spawn_error:
            raise RunStop(f'процесс головы не запустился ({res.spawn_error}): модель вход не видела, '
                          'запись не делается')
        if res.too_old:
            raise RunStop('отказ API: claude_code_version_too_old. Стоп без повтора и без записи «потерян»; '
                          'затем запасное правило версий из PREREG (с записанным отклонением)')
        if res.init_version is not None and res.init_version != PINNED_VERSION:
            raise RunStop(f'версия CLI в событии init: {res.init_version}, закреплена {PINNED_VERSION}')
        return res

    def _record(self, job, attempt, role, res, v, st):
        final = normalize_final(res.last_result)
        cfg = self.cfg
        return {
            'task': job['task'], 'job': job['id'], 'arm': job.get('arm'), 'attempt': attempt, 'role': role,
            'outcome': v.outcome, 'reason': v.reason, 'final': None,
            'waits': st.waits, 'retries': st.retries, 'streak': st.streak, 'flags': v.flags,
            'started': iso(res.started), 'finished': iso(res.finished),
            'config_sha256': self.config_sha, 'binary_sha256': self.bin_sha,
            'cli_init_version': res.init_version, 'cli_pinned_version': PINNED_VERSION,
            'model_target': cfg['model'],
            'model_usage_keys': sorted(final.model_usage) if final and final.model_usage else [],
            'model_usage_out': ({k: (v or {}).get('outputTokens') for k, v in sorted(final.model_usage.items())}
                                if final and final.model_usage else {}),
            'init_sha256': self._save_init(res.events),
            'session_id': (find_init(res.events) or {}).get('session_id'),
            'effort': cfg['effort'], 'thinking_budget': cfg['env_explicit']['MAX_THINKING_TOKENS'],
            'thinking_tokens': final.thinking if final else None,
            'env_config': {k: cfg['env_explicit'][k] for k in sorted(cfg['env_explicit'])},
            'env_access_names': access_names_passed(cfg),
            'usage': {'inp': final.inp if final else None, 'out': final.out if final else None,
                      'cost_usd': final.cost if final else None},
            'answer': final.structured if final else None,
            'exit': {'returncode': res.returncode, 'timed_out': res.timed_out,
                     'stderr_bytes': res.stderr_bytes, 'stderr_sha256': res.stderr_sha256,
                     'spawn_error': res.spawn_error},
            'stream': {'file': res.stream_path.name if res.stream_path else None,
                       'sha256': res.stream_sha256, 'bytes': res.stream_bytes, 'lines': len(res.lines),
                       'events_no_deltas': journal_events(res.events)},
        }

    def _run_job(self, job, st):
        task = job['task']
        while True:
            self._gate()
            st.attempts += 1
            res = self._one_call(job, st.attempts, 'основной')
            v = verdict_for(res, self.cfg)
            now = self.now_fn()
            if v.outcome == NA:
                reset, source = reset_from_events(res.events), 'rate_limit_event'
                if reset is None and v.limit_text:
                    reset, source = next_reset(v.limit_text, now), 'текст итога'
                if reset is not None:                       # лимит аккаунта со временем сброса: ждём и повторяем
                    reset = max(reset, now)
                    st.waits += 1
                    st.streak = 0
                    until = reset + timedelta(seconds=self.cfg['limit_margin_s'])
                    wait_s = (until - now).total_seconds()
                    rec = self._record(job, st.attempts, 'основной', res, v, st)
                    rec['limit_reset_at'] = iso(until)
                    rec['reset_source'] = source
                    rec['wait_s'] = round(wait_s)
                    self._append(task, rec)
                    if st.waits > self.cfg['max_limit_waits_per_job']:
                        raise RunStop(f'задача {job["id"]}: ожиданий сброса {st.waits} больше допустимого')
                    if wait_s > self.cfg['max_single_wait_s']:
                        raise RunStop(f'задача {job["id"]}: ожидание сброса {round(wait_s)} с слишком долгое')
                    self.log(f'{job["id"]}: лимит аккаунта, жду сброса до {iso(until)}')
                    self._set_pause(until)
                    continue
                # нулевой usage без времени сброса или таймаут до message_start: ограниченные повторы
                st.retries += 1
                st.streak += 1
                limit = self.cfg['zero_retry_limit'] if v.kind == 'zero' else self.cfg['start_timeout_retry_limit']
                rec = self._record(job, st.attempts, 'основной', res, v, st)
                self._append(task, rec)
                if st.streak > limit:
                    raise RunStop(f'задача {job["id"]}: {v.reason}; повторы исчерпаны ({limit})')
                self._sleep(min(self.cfg['backoff_cap_s'], self.cfg['backoff_base_s'] * 2 ** (st.streak - 1)))
                continue
            if v.outcome == OK:
                st.final = 'годный'
                st.streak = 0
                with self.lock:
                    self.lost_streak = 0
                rec = self._record(job, st.attempts, 'основной', res, v, st)
                rec['final'] = 'годный'
                self._append(task, rec)
                return
            # сбой ответа: повтора нет, вызов потерян
            st.final = 'потерян'
            st.streak = 0
            rec = self._record(job, st.attempts, 'основной', res, v, st)
            rec['final'] = 'потерян'
            self._append(task, rec)
            with self.lock:
                self.lost_streak += 1
                streak = self.lost_streak
            if not res.events:
                raise RunStop(f'задача {job["id"]}: поток пуст ({v.reason}) — CLI не дошёл до init; '
                              'запись «потерян» сделана, прогон остановлен для разбора')
            if streak >= self.cfg['max_consecutive_lost']:
                raise RunStop(f'«потерян» {streak} раз подряд (последний: {job["id"]}, {v.reason}) — '
                              'остановка для разбора; записи не меняются')
            if self.cfg['secondary_retry']:
                st.attempts += 1
                res2 = self._one_call(job, st.attempts, 'вторичный повтор')
                v2 = verdict_for(res2, self.cfg)
                rec2 = self._record(job, st.attempts, 'вторичный повтор', res2, v2, st)
                self._append(task, rec2)               # только в журнал, на итог задачи не влияет
            return

    def _run_job_safe(self, job, st):
        try:
            self._run_job(job, st)
        except _Stopped:
            return
        except RunStop as e:
            self.stop.set()
            self._log_run('стоп', {'task': job['task'], 'job': job['id'], 'reason': str(e)})
            raise
        except Exception as e:
            self.stop.set()
            self._log_run('ошибка', {'task': job['task'], 'job': job['id'], 'reason': repr(e)})
            raise

    def run(self, jobs):
        order, by_task = [], {}
        for j in jobs:
            if j['task'] not in by_task:
                by_task[j['task']] = []
                order.append(j['task'])
            by_task[j['task']].append(j)
        names = {}
        for t in order:
            if safe(t) in names and names[safe(t)] != t:
                raise RunStop(f'имена задач {names[safe(t)]!r} и {t!r} совпадают в файле журнала')
            names[safe(t)] = t
        pending = []
        for t in order:
            states = states_from_records(self._read_journal(t))
            for j in order_jobs(by_task[t], self.seed, t):
                st = states.get(j['id'], JobState())
                if st.final:
                    continue                          # итог уже записан: вызов не запрашивается заново
                if st.pause is not None:
                    self._set_pause(st.pause)
                pending.append((j, st))
        self._log_run('план', {'заданий_в_плане': len(pending), 'задач': len(order)})
        errors = []
        with ThreadPoolExecutor(max_workers=self.parallel) as ex:
            futs = [ex.submit(self._run_job_safe, j, st) for j, st in pending]
            for f in as_completed(futs):
                exc = f.exception()
                if exc is not None:
                    errors.append(exc)
        if errors:
            first = next((e for e in errors if isinstance(e, RunStop)), errors[0])
            raise first
        self._log_run('готово', {'заданий_в_плане': len(pending)})


# ---------- пробный вызов ----------

def probe_job():
    return {'task': 'probe', 'id': 'probe-da', 'prompt': PROBE_PROMPT, 'schema': PROBE_SCHEMA}


def describe_call(cfg, job):
    env = build_env(cfg)
    lines = [' '.join(repr(x) if ' ' in x or x == '' else x for x in build_cmd(cfg, job)), '',
             'переменные среды (значения только у конфигурации):']
    for k in sorted(env):
        if k in cfg['env_explicit'] or k == 'HOME':
            lines.append(f'  {k}={env[k]}')
        else:
            lines.append(f'  {k} (значение передаётся, в журнал не пишется)')
    lines.append('удаляются: ' + ', '.join(cfg['env_removed']))
    return '\n'.join(lines)


LEAK_RES = [re.compile(r'sk-ant-'), re.compile(r'eyJ[A-Za-z0-9_\-]{8,}\.'), re.compile(r'(?i)bearer\s+[A-Za-z0-9]'),
            re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}'), PATH_RE]


def leak_scan(text):
    """Что осталось похоже на секрет, e-mail или адрес машины (пустой список — чисто)."""
    hits = []
    for rx in LEAK_RES:
        hits += [m.group(0) for m in rx.finditer(text)]
    return hits


def sanitize_fixture(lines):
    out = []
    for raw in lines:
        text = raw.decode('utf-8', 'replace').rstrip('\n')
        try:
            obj = json.loads(text)
        except ValueError:
            out.append(scrub_text(text, paths=True))
            continue
        obj = _scrub_obj(obj)
        out.append(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))
    return out


def _scrub_obj(obj):
    if isinstance(obj, dict):
        return {k: _scrub_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_obj(v) for v in obj]
    if isinstance(obj, str):
        return scrub_text(obj, paths=True)
    return obj


def cmd_probe(args):
    cfg = default_config()
    cfg['model'] = args.model
    job = probe_job()
    if args.dry_run:
        print(describe_call(cfg, job))
        return 0
    marker = CACHE / 'probe_done.json'
    if marker.exists():
        print(f'пробный вызов уже был ({marker}); повтор запрещён правилом «один пробный вызов»', file=sys.stderr)
        return 4
    CACHE.mkdir(parents=True, exist_ok=True)
    guard = BinaryGuard(cfg, log=print)
    sha = guard.check()
    marker.write_text(json.dumps({'started': iso(utcnow()), 'model': cfg['model'], 'binary_sha256': sha},
                                 ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    res = real_call(cfg, job, CACHE / 'probe' / 'probe.a001.jsonl.gz')
    v = verdict_for(res, cfg)
    fin = normalize_final(res.last_result)
    report = {'исход': v.outcome, 'причина': v.reason, 'флаги': v.flags, 'cli_init_version': res.init_version,
              'cli_pinned_version': PINNED_VERSION, 'binary_sha256': sha, 'model_target': cfg['model'],
              'model_usage_keys': sorted(fin.model_usage) if fin and fin.model_usage else None,
              'usage': {'inp': fin.inp, 'out': fin.out, 'cost_usd': fin.cost, 'thinking': fin.thinking}
              if fin else None,
              'returncode': res.returncode, 'timed_out': res.timed_out, 'spawn_error': res.spawn_error,
              'строк_потока': len(res.lines), 'unparsable': res.unparsable, 'results': res.results_count,
              'stderr_bytes': res.stderr_bytes, 'поток_gz': str(res.stream_path)}
    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        clean = sanitize_fixture(res.lines)
        hits = leak_scan('\n'.join(clean))
        if hits:
            print('образец не записан: остались похожие на секрет фрагменты (' + str(len(hits)) + ')', file=sys.stderr)
            return 5
        out.write_text('\n'.join(clean) + '\n', encoding='utf-8')
        print(f'образец записан: {out} ({len(clean)} строк)')
    return 0 if v.outcome == OK else 2


def load_jobs(path, task_from_id=False):
    """Задания. task_from_id: формат run_sealed v1 ({id, prompt, schema}, id = «задача|рука|i»): задача и рука из id."""
    jobs, seen = [], set()
    for n, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        j = json.loads(line)
        if task_from_id and 'task' not in j and 'id' in j:
            parts = str(j['id']).split('|')
            j['task'] = parts[0]
            j.setdefault('arm', parts[1] if len(parts) > 1 else None)
        for k in ('task', 'id', 'prompt', 'schema'):
            if k not in j:
                raise SystemExit(f'{path}:{n}: нет поля {k}')
        if (j['task'], j['id']) in seen:
            raise SystemExit(f'{path}:{n}: повтор id {j["id"]} в задаче {j["task"]}')
        seen.add((j['task'], j['id']))
        jobs.append(j)
    return jobs


def cmd_run(args):
    cfg = load_config(args.config)
    jobs = load_jobs(args.jobs, task_from_id=args.task_from_id)
    drv = Driver(cfg, seed=args.seed, jobs_sha256=sha256_file(args.jobs), journal_dir=args.journal,
                 streams_dir=args.streams, parallel=args.parallel, max_calls=args.max_calls)
    drv.start()
    drv.run(jobs)
    print(f'прогон завершён: заданий {len(jobs)}, журнал {args.journal}')
    return 0


def journal_records(journal):
    """Все записи вызовов журнала (кроме run_log.jsonl), по файлам задач."""
    for path in sorted(Path(journal).glob('*.jsonl')):
        if path.name == 'run_log.jsonl':
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                yield json.loads(line)


def cmd_summary(args):
    """Сводка по рукам. Голосом считаются только итоговые записи (final = годный / потерян).

    без_записи — вызовы, начатые по run_log.jsonl, но без записи в журнале (гибель драйвера, остановка после
    вызова); многоходовых — годные и потерянные с больше чем одним message_start; init — число вариантов init.
    """
    rows, inits, recorded = {}, {}, set()
    new = lambda: dict(годных=0, потеряно=0, попыток_нет_ответа=0, сбоев=0, ожиданий=0, повторов=0,
                       api_retry_до=0, api_retry_после=0, подмен=0, вторичных=0, многоходовых=0, без_usage=0,
                       без_записи=0)
    for r in journal_records(args.journal):
        c = rows.setdefault((r['task'], r.get('arm') or '-'), new())
        recorded.add((r['task'], r['job'], r['attempt'], r.get('role')))
        inits.setdefault((r['task'], r.get('arm') or '-'), set()).add(r.get('init_sha256'))
        if r.get('role') != 'основной':
            c['вторичных'] += 1
            continue
        if r.get('final') == 'годный':
            c['годных'] += 1
        elif r.get('final') == 'потерян':
            c['потеряно'] += 1
        if r['outcome'] == NA:
            c['попыток_нет_ответа'] += 1
            if 'wait_s' in r:
                c['ожиданий'] += 1
            else:
                c['повторов'] += 1
        if r['outcome'] == FAIL:
            c['сбоев'] += 1
        flags = r.get('flags') or {}
        c['api_retry_до'] += flags.get('api_retry_до_начала', 0)
        c['api_retry_после'] += flags.get('api_retry_после_начала', 0)
        if 'ответ не целевой модели' in r.get('reason', ''):
            c['подмен'] += 1
        if r.get('final') and (flags.get('message_start') or 0) > 1:
            c['многоходовых'] += 1
        if r.get('final') and (r.get('usage') or {}).get('out') is None:
            c['без_usage'] += 1
    log = Path(args.journal) / 'run_log.jsonl'
    if log.exists():
        for line in log.read_text(encoding='utf-8').splitlines():
            e = json.loads(line) if line.strip() else {}
            if e.get('event') == 'вызов' and (e['task'], e['job'], e['attempt'], e.get('role')) not in recorded:
                rows.setdefault((e['task'], e.get('arm') or '-'), new())['без_записи'] += 1
    cols = list(new())
    print('задача\tрука\t' + '\t'.join(cols) + '\tinit')
    for (task, arm), c in sorted(rows.items()):
        print(task + '\t' + arm + '\t' + '\t'.join(str(c[k]) for k in cols) + '\t' +
              str(len(inits.get((task, arm), set()) - {None})))
    return 0


def cmd_export(args):
    """Итоговые записи журнала → формат run_sealed v1 (run/<этап>_out.jsonl в SELECT-01, читает harness.py).

    годный — result = ответ, токены из usage; потерян — result = None, error = «потерян: причина». Задания без итога
    (только «нет ответа») не выгружаются. Токены, которых нет в записи (сбой без итога), пишутся 0 с пометкой
    usage_unknown = true: harness складывает их числами.
    """
    out = []
    for r in journal_records(args.journal):
        if r.get('role') != 'основной' or r.get('final') not in ('годный', 'потерян'):
            continue
        u = r.get('usage') or {}
        rec = {'id': r['job'], 'result': r.get('answer') if r['final'] == 'годный' else None,
               'inp': u.get('inp') or 0, 'out': u.get('out') or 0, 'thinking': r.get('thinking_tokens'),
               'models': r.get('model_usage_out') or {}, 'permission_denials': 0, 'cost_usd': u.get('cost_usd'),
               'attempt': r['attempt'], 'waits': r.get('waits', 0), 'retries': r.get('retries', 0)}
        if u.get('inp') is None or u.get('out') is None:
            rec['usage_unknown'] = True
        if r['final'] == 'потерян':
            rec['error'] = 'потерян: ' + r.get('reason', '')
        out.append(rec)
    ids = [x['id'] for x in out]
    if len(ids) != len(set(ids)):
        raise SystemExit('в журнале два итога у одного задания: выгрузка остановлена')
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as fh:
        for x in sorted(out, key=lambda x: x['id']):
            fh.write(json.dumps(x, ensure_ascii=False) + '\n')
    print(f'выгружено {len(out)} итоговых записей в {args.out}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='run_sealed2: драйвер голов claude -p (решение совета 29, пункт (А)).')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('probe', help='один пробный вызов закреплённым бинарём')
    p.add_argument('--out', help='куда записать очищенный поток (jsonl)')
    p.add_argument('--model', default=PROBE_MODEL)
    p.add_argument('--dry-run', action='store_true', help='только печатать команду и среду, без вызова')
    p.set_defaults(func=cmd_probe)
    p = sub.add_parser('run', help='прогон голов по файлу заданий')
    p.add_argument('--jobs', required=True)
    p.add_argument('--seed', required=True)
    p.add_argument('--journal', required=True)
    p.add_argument('--streams', required=True, help='каталог полных потоков (gzip), вне git')
    p.add_argument('--config', help='JSON с отличиями от конфигурации по умолчанию')
    p.add_argument('--parallel', type=int, default=1)
    p.add_argument('--max-calls', type=int, default=None)
    p.add_argument('--task-from-id', action='store_true', help='задания в формате v1: задача и рука из id «задача|рука|i»')
    p.set_defaults(func=cmd_run)
    p = sub.add_parser('summary', help='сводка журнала по рукам')
    p.add_argument('--journal', required=True)
    p.set_defaults(func=cmd_summary)
    p = sub.add_parser('export', help='итоги журнала в формат run_sealed v1 (для harness.py SELECT-01)')
    p.add_argument('--journal', required=True)
    p.add_argument('--out', required=True)
    p.set_defaults(func=cmd_export)
    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except RunStop as e:
        print(f'ОСТАНОВКА: {e}', file=sys.stderr)
        return 3


if __name__ == '__main__':
    sys.exit(main())
