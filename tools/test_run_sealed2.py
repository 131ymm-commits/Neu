#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты run_sealed2 без вызовов модели.

Запуск из корня репозитория:  python3 tools/test_run_sealed2.py

Что проверяется:
  - классы исхода на синтетических потоках (каждый случай — в свой класс);
  - адаптер старых записей пилота 2 SELECT-01 (38 → «нет ответа», 286 → «годный»);
  - драйвер на поддельном вызове: ожидание сброса не тратит попытку, ограниченные повторы, «потерян»,
    продолжение без повторных вызовов, остановка при смене конфигурации;
  - белый список среды, команда, порядок от зерна, извлечение бинаря из колеса по sha256;
  - реальный поток пробного вызова (tools/fixtures/run_sealed2_probe.jsonl) — класс «годный» и отсутствие секретов.
Во время тестов настоящий subprocess.Popen заменён заглушкой: любой случайный запуск головы даст ошибку.
"""

import gzip
import io
import json
import os
import re
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import run_sealed2 as rs  # noqa: E402

TARGET = 'claude-opus-5-5'          # целевая модель синтетических потоков (как голова SELECT-01)
PROBE_TARGET = 'claude-haiku-5-5'   # модель пробного вызова
V1_RUN = REPO / 'experiments' / '2026-10-07_SELECT-01' / 'run' / 'p2_eval_out.jsonl'
FIXTURE = TOOLS / 'fixtures' / 'run_sealed2_probe.jsonl'
T0 = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)
LIMIT_TEXT = "You've hit your session limit · resets 7:30pm (UTC)"


# ---------- синтетические события (форма взята из реального потока пробного вызова) ----------

def ev_init(version='2.1.294'):
    return {'type': 'system', 'subtype': 'init', 'claude_code_version': version, 'model': TARGET}


def ev_start(model=TARGET):
    return {'type': 'stream_event', 'event': {'type': 'message_start',
                                             'message': {'model': model, 'usage': {'input_tokens': 1}}}}


def ev_delta(text='да'):
    return {'type': 'stream_event', 'event': {'type': 'content_block_delta', 'index': 0,
                                             'delta': {'type': 'text_delta', 'text': text}}}


def ev_stop():
    return {'type': 'stream_event', 'event': {'type': 'message_stop'}}


def ev_mdelta(reason='end_turn'):
    return {'type': 'stream_event', 'event': {'type': 'message_delta', 'delta': {'stop_reason': reason}}}


def ev_retry():
    return {'type': 'system', 'subtype': 'api_retry', 'attempt': 1, 'max_retries': 0,
            'error_status': 529, 'error': 'overloaded_error', 'retry_delay_ms': 1000}


def usage(inp=6000, out=50, thinking=0):
    return {'input_tokens': inp, 'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0,
            'output_tokens': out, 'output_tokens_details': {'thinking_tokens': thinking}}


def ev_result(structured=None, inp=6000, out=50, cost=0.01, model=TARGET, is_error=False, text='',
              perm=None, with_usage=True, subtype='success', default_structured=True):
    if structured is None and default_structured:
        structured = {'answer': 'да'}
    e = {'type': 'result', 'subtype': subtype, 'is_error': is_error, 'result': text,
         'structured_output': structured, 'total_cost_usd': cost,
         'modelUsage': ({model: {'outputTokens': out}} if model else {}), 'permission_denials': perm or []}
    if with_usage:
        e['usage'] = usage(inp, out)
    return e


def ev_limit(text=LIMIT_TEXT):
    """Итог лимита аккаунта: токенов нет, cost = 0."""
    return ev_result(structured=None, inp=0, out=0, cost=0, model=None, is_error=True, text=text,
                     default_structured=False)


def good_stream():
    return [ev_init(), ev_start(), ev_delta(), ev_stop(), ev_mdelta(), ev_result()]


def cls(events, **kw):
    """Класс исхода по потоку (как в драйвере: итог — последнее событие result, число итогов передаётся)."""
    results = [e for e in events if e.get('type') == 'result']
    final = rs.normalize_final(results[-1] if results else None)
    args = dict(events=events, target_model=TARGET, results_count=len(results))
    args.update(kw)
    return rs.classify(final, **args)


def call(events=None, **kw):
    """Поддельный результат вызова."""
    return rs.CallResult(events=list(events or []), started=T0, finished=T0, **kw)


class Clock:
    def __init__(self):
        self.t = T0
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += timedelta(seconds=s)


class Script:
    """Последовательность поддельных вызовов. Лишний вызов — ошибка теста."""

    def __init__(self, items):
        self.items = list(items)
        self.calls = []

    def __call__(self, cfg, job, gz):
        self.calls.append(job['id'])
        if not self.items:
            raise AssertionError('лишний вызов головы в тесте')
        return self.items.pop(0)


def make_cfg(**over):
    cfg = rs.default_config()
    cfg.update(over)
    return cfg


def read_journal(journal_dir, task):
    p = Path(journal_dir) / f'{rs.safe(task)}.jsonl'
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]


def setUpModule():
    global _popen_patch
    _popen_patch = mock.patch.object(rs.subprocess, 'Popen',
                                     side_effect=AssertionError('тесты не запускают модель'))
    _popen_patch.start()


def tearDownModule():
    _popen_patch.stop()


# ---------- классы исхода ----------

class ClassifyTests(unittest.TestCase):

    def test_good_stream_is_ok(self):
        v = cls(good_stream())
        self.assertEqual(v.outcome, rs.OK)

    def test_api_retry_before_start_is_ok_and_flagged(self):
        ev = [ev_init(), ev_retry(), ev_retry(), ev_start(), ev_delta(), ev_stop(), ev_mdelta(), ev_result()]
        v = cls(ev)
        self.assertEqual(v.outcome, rs.OK)
        self.assertEqual(v.flags['api_retry_до_начала'], 2)

    def test_api_retry_after_start_is_failure(self):
        ev = [ev_init(), ev_start(), ev_retry(), ev_delta(), ev_stop(), ev_mdelta(), ev_result()]
        v = cls(ev)
        self.assertEqual(v.outcome, rs.FAIL)
        self.assertIn('api_retry после', v.reason)

    def test_aborted_turn_then_full_message_is_failure(self):
        ev = [ev_init(), ev_start(), ev_delta(), ev_start(), ev_delta(), ev_stop(), ev_mdelta(), ev_result()]
        v = cls(ev)
        self.assertEqual(v.outcome, rs.FAIL)
        self.assertIn('оборванный ход', v.reason)

    def test_timeout_before_message_start_is_no_answer(self):
        v = cls([ev_init()], timed_out=True, returncode=-9)
        self.assertEqual((v.outcome, v.kind), (rs.NA, 'start'))

    def test_timeout_after_message_start_is_failure(self):
        v = cls([ev_init(), ev_start(), ev_delta()], timed_out=True, returncode=-9)
        self.assertEqual(v.outcome, rs.FAIL)

    def test_timeout_without_recorded_stream_is_failure(self):
        self.assertEqual(cls([], timed_out=True, returncode=-9).outcome, rs.FAIL)
        self.assertEqual(rs.classify(None, events=None, timed_out=True, returncode=-9,
                                     target_model=TARGET).outcome, rs.FAIL)

    def test_process_death_before_start_is_no_answer(self):
        self.assertEqual(cls([ev_init()], returncode=1).outcome, rs.NA)

    def test_zero_usage_limit_is_no_answer_with_reset_text(self):
        ev = [ev_init(), ev_limit()]
        v = cls(ev)
        self.assertEqual((v.outcome, v.kind), (rs.NA, 'zero'))
        self.assertIn('resets 7:30pm', v.limit_text)

    def test_missing_usage_is_not_no_answer(self):
        v = cls([ev_init(), ev_start(), ev_stop(), ev_result(with_usage=False)])
        self.assertEqual(v.outcome, rs.FAIL)
        self.assertIn('usage', v.reason)

    def test_missing_cost_is_not_no_answer(self):
        v = cls([ev_init(), ev_result(inp=0, out=0, cost=None, model=None, is_error=True, text='x',
                                      default_structured=False)])
        self.assertEqual(v.outcome, rs.FAIL)

    def test_foreign_model_is_failure(self):
        v = cls([ev_init(), ev_start(), ev_stop(), ev_result(model='claude-sonnet-x')])
        self.assertEqual(v.outcome, rs.FAIL)
        self.assertIn('не целевой модели', v.reason)

    def test_dated_snapshot_of_target_is_ok(self):
        v = cls([ev_init(), ev_start(), ev_stop(), ev_result(model=TARGET + '-20260101')])
        self.assertEqual(v.outcome, rs.OK)

    def test_refusal_is_failure(self):
        ev = [ev_init(), ev_start(), ev_mdelta('refusal'), ev_stop(), ev_result(default_structured=False)]
        self.assertEqual(cls(ev).outcome, rs.FAIL)

    def test_no_structured_output_is_failure(self):
        v = cls([ev_init(), ev_start(), ev_stop(), ev_result(default_structured=False)])
        self.assertEqual(v.outcome, rs.FAIL)
        self.assertIn('structured_output', v.reason)

    def test_unparsable_output_is_failure(self):
        v = cls(good_stream(), unparsable=1)
        self.assertEqual(v.outcome, rs.FAIL)
        self.assertIn('неразборный', v.reason)

    def test_nonzero_exit_with_result_is_failure(self):
        self.assertEqual(cls(good_stream(), returncode=1).outcome, rs.FAIL)

    def test_permission_denials_are_failure(self):
        v = cls([ev_init(), ev_start(), ev_stop(), ev_result(perm=[{'tool_name': 'Bash'}])])
        self.assertEqual(v.outcome, rs.FAIL)

    def test_error_result_is_failure(self):
        v = cls([ev_init(), ev_result(is_error=True, text='что-то пошло не так', default_structured=False,
                                      model=None, inp=5, out=0, cost=0.0)])
        self.assertEqual(v.outcome, rs.FAIL)

    def test_no_result_event_is_failure(self):
        self.assertEqual(cls([ev_init(), ev_start(), ev_stop()], returncode=0).outcome, rs.FAIL)

    def test_two_result_events_is_failure(self):
        ev = good_stream() + [ev_result()]
        v = cls(ev)
        self.assertEqual(v.outcome, rs.FAIL)


# ---------- старые записи пилота 2 SELECT-01 ----------

class LegacyTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.recs = [json.loads(x) for x in V1_RUN.read_text(encoding='utf-8').splitlines() if x.strip()]

    def test_file_has_324_records(self):
        self.assertEqual(len(self.recs), 324)

    def test_errors_are_no_answer_and_ok_are_ok(self):
        counts = {rs.NA: 0, rs.OK: 0, rs.FAIL: 0}
        for r in self.recs:
            v = rs.classify(rs.legacy_final(r), events=None, target_model=TARGET, legacy=True)
            counts[v.outcome] += 1
        self.assertEqual(counts[rs.NA], 38)
        self.assertEqual(counts[rs.OK], 286)
        self.assertEqual(counts[rs.FAIL], 0)

    def test_no_answer_records_are_exactly_the_zero_usage_limit_ones(self):
        for r in self.recs:
            zero = r['inp'] == 0 and r['out'] == 0 and r['cost_usd'] == 0 and r['models'] == {}
            is_limit = "You've hit your session limit" in (r.get('error') or '')
            self.assertEqual(zero, is_limit, r['id'])
            if is_limit:
                self.assertIsNotNone(rs.next_reset(rs.legacy_final(r).text, T0))

    def test_ok_records_have_positive_output_and_target_model_only(self):
        for r in self.recs:
            if r.get('error'):
                continue
            self.assertGreater(r['out'], 0)
            self.assertEqual(set(r['models']), {TARGET}, r['id'])
            self.assertEqual(r['permission_denials'], 0)

    def test_legacy_adapter_strips_prefix_from_error_text(self):
        f = rs.legacy_final({'error': 'нет structured_output: ' + LIMIT_TEXT, 'inp': 0, 'out': 0,
                             'cost_usd': 0, 'models': {}, 'result': None})
        self.assertEqual(f.text, LIMIT_TEXT)


# ---------- сброс лимита, порядок, журнал ----------

class ResetAndOrderTests(unittest.TestCase):

    def test_reset_same_day(self):
        now = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)
        self.assertEqual(rs.next_reset('resets 7:30pm (UTC)', now), datetime(2026, 10, 12, 19, 30, tzinfo=timezone.utc))

    def test_reset_tomorrow_when_passed(self):
        now = datetime(2026, 10, 12, 20, 0, tzinfo=timezone.utc)
        self.assertEqual(rs.next_reset('resets 7:30pm (UTC)', now), datetime(2026, 10, 13, 19, 30, tzinfo=timezone.utc))

    def test_reset_just_passed_means_now(self):
        now = datetime(2026, 10, 12, 19, 32, tzinfo=timezone.utc)
        self.assertEqual(rs.next_reset('resets 7:30pm (UTC)', now), now)

    def test_reset_midnight_and_noon_format(self):
        now = datetime(2026, 10, 12, 1, 0, tzinfo=timezone.utc)
        self.assertEqual(rs.next_reset('resets 12:05am (UTC)', now), datetime(2026, 10, 13, 0, 5, tzinfo=timezone.utc))
        self.assertEqual(rs.next_reset('resets 12pm (UTC)', now), datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc))

    def test_no_reset_text(self):
        self.assertIsNone(rs.next_reset('что-то другое', T0))
        self.assertIsNone(rs.next_reset(None, T0))

    def test_order_is_permutation_and_deterministic(self):
        jobs = [{'id': f'j{i}', 'task': 'T', 'arm': 'A' if i % 2 else 'B'} for i in range(8)]
        a = rs.order_jobs(jobs, 'зерно', 'T')
        b = rs.order_jobs(list(reversed(jobs)), 'зерно', 'T')
        self.assertEqual(sorted(j['id'] for j in a), sorted(j['id'] for j in jobs))
        self.assertEqual([j['id'] for j in a], [j['id'] for j in b])

    def test_order_depends_on_seed(self):
        jobs = [{'id': f'j{i}', 'task': 'T'} for i in range(8)]
        orders = {tuple(j['id'] for j in rs.order_jobs(jobs, f'seed{k}', 'T')) for k in range(5)}
        self.assertGreater(len(orders), 1)

    def test_arms_are_mixed_not_grouped(self):
        jobs = [{'id': f'{arm}{i}', 'task': 'T', 'arm': arm} for arm in 'ABC' for i in range(4)]
        arms = [j['arm'] for j in rs.order_jobs(jobs, 'зерно-42', 'T')]
        self.assertNotEqual(arms, sorted(arms))


# ---------- драйвер на поддельном вызове ----------

class DriverTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.journal = self.root / 'journal'
        self.streams = self.root / 'streams'
        self.clock = Clock()

    def tearDown(self):
        self.tmp.cleanup()

    def driver(self, cfg, call_fn, **kw):
        return rs.Driver(cfg, seed='S', jobs_sha256='jobs', journal_dir=self.journal, streams_dir=self.streams,
                         call_fn=call_fn, pre_call_check=lambda: 'bin-sha', now_fn=self.clock.now,
                         sleep_fn=self.clock.sleep, log=lambda m: None, **kw)

    def job(self, jid='j1', task='T1', arm='A'):
        return {'task': task, 'id': jid, 'arm': arm, 'prompt': 'п', 'schema': {'type': 'object'}}

    def test_limit_wait_does_not_spend_attempt_and_resumes(self):
        script = Script([call(events=[ev_init(), ev_limit()]), call(events=good_stream())])
        drv = self.driver(make_cfg(), script)
        drv.start()
        drv.run([self.job()])
        self.assertEqual(len(script.calls), 2)
        self.assertGreaterEqual(self.clock.t, datetime(2026, 10, 12, 19, 32, tzinfo=timezone.utc))
        recs = read_journal(self.journal, 'T1')
        self.assertEqual([r['outcome'] for r in recs], [rs.NA, rs.OK])
        self.assertEqual(recs[0]['waits'], 1)
        self.assertEqual(recs[0]['retries'], 0)
        self.assertIsNone(recs[0]['final'])
        self.assertEqual(recs[1]['final'], 'годный')

    def test_restart_does_not_repeat_recorded_calls(self):
        script = Script([call(events=good_stream())])
        drv = self.driver(make_cfg(), script)
        drv.start()
        drv.run([self.job()])
        again = Script([])                     # любой вызов — ошибка
        drv2 = self.driver(make_cfg(), again)
        drv2.start()
        drv2.run([self.job()])
        self.assertEqual(again.calls, [])

    def test_zero_usage_without_reset_is_bounded(self):
        cfg = make_cfg(zero_retry_limit=2)
        script = Script([call(events=[ev_init(), ev_result(structured=None, inp=0, out=0, cost=0,
                                                              model=None, is_error=True, text='overloaded',
                                                              default_structured=False)]) for _ in range(5)])
        drv = self.driver(cfg, script)
        drv.start()
        with self.assertRaises(rs.RunStop) as cm:
            drv.run([self.job()])
        self.assertIn('повторы исчерпаны', str(cm.exception))
        self.assertEqual(len(script.calls), 3)
        self.assertEqual(self.clock.slept[:2], [300, 600])
        recs = read_journal(self.journal, 'T1')
        self.assertEqual(recs[-1]['retries'], 3)
        self.assertTrue(all(r['outcome'] == rs.NA for r in recs))

    def test_start_timeout_is_bounded(self):
        cfg = make_cfg(start_timeout_retry_limit=1)
        script = Script([call(events=[ev_init()], timed_out=True, returncode=-9) for _ in range(4)])
        drv = self.driver(cfg, script)
        drv.start()
        with self.assertRaises(rs.RunStop):
            drv.run([self.job()])
        self.assertEqual(len(script.calls), 2)

    def test_failure_is_lost_without_retry(self):
        script = Script([call(events=[ev_init(), ev_start(), ev_stop(), ev_result(default_structured=False)])])
        drv = self.driver(make_cfg(), script)
        drv.start()
        drv.run([self.job()])
        self.assertEqual(len(script.calls), 1)
        recs = read_journal(self.journal, 'T1')
        self.assertEqual((recs[0]['outcome'], recs[0]['final']), (rs.FAIL, 'потерян'))

    def test_secondary_retry_is_journal_only(self):
        bad = call(events=[ev_init(), ev_start(), ev_stop(), ev_result(default_structured=False)])
        script = Script([bad, call(events=good_stream())])
        drv = self.driver(make_cfg(secondary_retry=True), script)
        drv.start()
        drv.run([self.job()])
        self.assertEqual(len(script.calls), 2)
        recs = read_journal(self.journal, 'T1')
        self.assertEqual([r['role'] for r in recs], ['основной', 'вторичный повтор'])
        self.assertEqual(recs[0]['final'], 'потерян')
        self.assertIsNone(recs[1]['final'])

    def test_too_old_stops_without_record(self):
        script = Script([call(events=[ev_init()], too_old=True)])
        drv = self.driver(make_cfg(), script)
        drv.start()
        with self.assertRaises(rs.RunStop) as cm:
            drv.run([self.job()])
        self.assertIn('claude_code_version_too_old', str(cm.exception))
        self.assertEqual(read_journal(self.journal, 'T1'), [])

    def test_init_version_mismatch_stops_without_record(self):
        script = Script([call(events=[ev_init('2.1.295')] + good_stream()[1:])])
        drv = self.driver(make_cfg(), script)
        drv.start()
        with self.assertRaises(rs.RunStop) as cm:
            drv.run([self.job()])
        self.assertIn('2.1.295', str(cm.exception))
        self.assertEqual(read_journal(self.journal, 'T1'), [])

    def test_call_budget_stops_run(self):
        script = Script([call(events=good_stream())])
        drv = self.driver(make_cfg(), script, max_calls=1)
        drv.start()
        with self.assertRaises(rs.RunStop) as cm:
            drv.run([self.job('j1'), self.job('j2')])
        self.assertIn('потолок', str(cm.exception))
        self.assertEqual(len(script.calls), 1)

    def test_call_budget_is_cumulative_across_restarts(self):
        drv = self.driver(make_cfg(), Script([call(events=good_stream())]), max_calls=2)
        drv.start()
        drv.run([self.job('j1')])
        drv2 = self.driver(make_cfg(), Script([call(events=good_stream())]), max_calls=2)
        drv2.start()
        self.assertEqual(drv2.calls, 1)
        drv2.run([self.job('j1'), self.job('j2')])           # j1 уже с итогом; j2 — второй вызов журнала
        drv3 = self.driver(make_cfg(), Script([]), max_calls=2)
        drv3.start()
        with self.assertRaises(rs.RunStop) as cm:
            drv3.run([self.job('j1'), self.job('j2'), self.job('j3')])
        self.assertIn('потолок', str(cm.exception))

    def test_config_change_on_resume_stops(self):
        drv = self.driver(make_cfg(), Script([]))
        drv.start()
        drv2 = self.driver(make_cfg(model='claude-other-1'), Script([]))
        with self.assertRaises(rs.RunStop) as cm:
            drv2.start()
        self.assertIn('model', str(cm.exception))

    def test_corrupted_journal_stops(self):
        self.journal.mkdir(parents=True)
        (self.journal / 'T1.jsonl').write_text('{не json\n', encoding='utf-8')
        drv = self.driver(make_cfg(), Script([]))
        drv.start()
        with self.assertRaises(rs.RunStop):
            drv.run([self.job()])

    def test_record_contains_required_fields(self):
        script = Script([call(events=good_stream(), lines=[b'x'])])
        drv = self.driver(make_cfg(), script)
        drv.start()
        drv.run([self.job()])
        r = read_journal(self.journal, 'T1')[0]
        for key in ('cli_init_version', 'binary_sha256', 'model_usage_keys', 'effort', 'thinking_budget',
                    'env_config', 'env_access_names', 'usage', 'waits', 'retries', 'stream', 'config_sha256'):
            self.assertIn(key, r)
        self.assertEqual(r['cli_init_version'], '2.1.294')
        self.assertEqual(r['env_config']['MAX_THINKING_TOKENS'], '31999')
        self.assertEqual(r['model_usage_keys'], [TARGET])
        self.assertNotIn('content_block_delta', json.dumps(r['stream']['events_no_deltas']))


# ---------- среда, команда, конфигурация, бинарь ----------

class ConfigEnvTests(unittest.TestCase):

    REQUIRED_EXPLICIT = ['MAX_THINKING_TOKENS', 'CLAUDE_CODE_MAX_RETRIES', 'API_TIMEOUT_MS',
                         'CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS', 'CLAUDE_BYTE_STREAM_IDLE_TIMEOUT_MS',
                         'CLAUDE_STREAM_IDLE_TIMEOUT_MS', 'CLAUDE_ENABLE_STREAM_WATCHDOG',
                         'CLAUDE_ENABLE_BYTE_WATCHDOG', 'DISABLE_GROWTHBOOK',
                         'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC']

    def test_required_variables_are_explicit(self):
        cfg = rs.default_config()
        for name in self.REQUIRED_EXPLICIT:
            self.assertIn(name, cfg['env_explicit'])
        self.assertEqual(cfg['env_explicit']['CLAUDE_CODE_MAX_RETRIES'], '0')
        self.assertEqual(set(cfg['env_removed']), {'CLAUDE_CODE_EFFORT_LEVEL', 'CLAUDE_CODE_MAX_OUTPUT_TOKENS'})

    def test_env_is_whitelisted_and_explicit_values_win(self):
        inherited = {'MAX_THINKING_TOKENS': '1', 'CLAUDE_CODE_EFFORT_LEVEL': 'low',
                     'CLAUDE_CODE_MAX_OUTPUT_TOKENS': '5', 'NODE_OPTIONS': '--require x',
                     'CLAUDECODE': '1', 'CLAUDE_CODE_DEBUG': 'true', 'HTTPS_PROXY': 'http://127.0.0.1:9',
                     'PATH': '/usr/bin'}
        with mock.patch.dict(os.environ, inherited, clear=False):
            cfg = rs.default_config()
            env = rs.build_env(cfg)
            names = rs.access_names_passed(cfg)
        self.assertEqual(env['MAX_THINKING_TOKENS'], '31999')
        for bad in ('CLAUDE_CODE_EFFORT_LEVEL', 'CLAUDE_CODE_MAX_OUTPUT_TOKENS', 'NODE_OPTIONS', 'CLAUDECODE',
                    'CLAUDE_CODE_DEBUG'):
            self.assertNotIn(bad, env)
        self.assertEqual(env['HTTPS_PROXY'], 'http://127.0.0.1:9')
        self.assertEqual(env['HOME'], cfg['home'])
        self.assertIn('HTTPS_PROXY', names)
        self.assertNotIn('NODE_OPTIONS', names)

    def test_command_has_required_flags_and_no_fallback(self):
        cfg = rs.default_config()
        job = {'task': 'T', 'id': 'j', 'prompt': 'Ответь одним словом: да', 'schema': {'type': 'object'}}
        cmd = rs.build_cmd(cfg, job)
        i = cmd.index('--tools')
        self.assertEqual(cmd[i + 1], '')
        for flag in ('--setting-sources', '--strict-mcp-config', '--no-session-persistence', '--verbose',
                     '--include-partial-messages', '--json-schema', '--effort'):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index('--output-format') + 1], 'stream-json')
        self.assertNotIn('--fallback-model', cmd)
        self.assertEqual(cmd[cmd.index('--effort') + 1], cfg['effort'])

    def test_config_diff_lists_changes(self):
        d = rs.config_diff({'a': 1, 'b': {'c': 2}}, {'a': 2, 'b': {'c': 3}})
        self.assertEqual(len(d), 2)
        self.assertTrue(any('a' in x for x in d))

    def test_extract_member_checks_sha(self):
        data = b'binary-bytes'
        with tempfile.TemporaryDirectory() as td:
            whl = Path(td) / 'x.whl'
            with zipfile.ZipFile(whl, 'w') as z:
                z.writestr(rs.WHEEL_MEMBER, data)
            good = Path(td) / 'ok' / 'claude'
            rs.extract_member(whl, rs.WHEEL_MEMBER, good, rs.sha256_bytes(data))
            self.assertEqual(good.read_bytes(), data)
            self.assertTrue(os.access(good, os.X_OK))
            bad = Path(td) / 'bad' / 'claude'
            with self.assertRaises(rs.RunStop):
                rs.extract_member(whl, rs.WHEEL_MEMBER, bad, '0' * 64)
            self.assertFalse(bad.exists())

    def test_pinned_binary_matches_if_present(self):
        p = Path(rs.default_config()['cli']['bin'])
        if not p.exists():
            self.skipTest('закреплённый бинарь ещё не распакован (.cache/claude-cli/2.1.294/claude)')
        self.assertEqual(rs.sha256_file(p), rs.PINNED_BIN_SHA256)

    def test_pinned_version_constants(self):
        self.assertEqual(rs.PINNED_VERSION, '2.1.294')
        self.assertEqual(len(rs.PINNED_BIN_SHA256), 64)
        self.assertEqual(len(rs.WHEEL_SHA256), 64)


# ---------- очистка, журнал, образец ----------

class SanitizeTests(unittest.TestCase):

    def test_scrub_replaces_email_token_and_paths(self):
        raw = b'{"a":"mail someone@example.com path /home/user/x key sk-ant-abcdefghijkl","b":"/root/y"}'
        out = rs.sanitize_fixture([raw])[0]
        self.assertEqual(rs.leak_scan(out), [])
        self.assertIn('<почта>', out)

    def test_journal_events_drop_deltas_and_secret_keys(self):
        ev = [ev_init(), ev_delta(), {'type': 'result', 'api_key_source': 'x', 'usage': usage(), 'email': 'a@b.cc'}]
        out = rs.journal_events(ev)
        self.assertEqual(len(out), 2)
        self.assertNotIn('email', out[1])
        self.assertIn('input_tokens', out[1]['usage'])   # usage не теряется: это не секрет

    def test_fixture_leak_scan_flags_real_secret_shapes(self):
        self.assertTrue(rs.leak_scan('sk-ant-XXXXXXXXXXXX'))
        self.assertTrue(rs.leak_scan('see /home/user/neu/x'))
        self.assertEqual(rs.leak_scan('{"type":"result"}'), [])


# ---------- правки проверки Opus (12.10.2026) ----------

def ev_rate(status='rejected', resets_at=1791821400, kind='five_hour'):
    return {'type': 'rate_limit_event', 'rate_limit_info': {'status': status, 'resetsAt': resets_at,
                                                            'rateLimitType': kind}}


class OpusReviewTests(unittest.TestCase):
    """Время сброса из события, остановки, журнал для git, выгрузка в формат v1."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.journal = self.root / 'journal'
        self.streams = self.root / 'streams'
        self.clock = Clock()

    def tearDown(self):
        self.tmp.cleanup()

    def driver(self, cfg, call_fn, **kw):
        return rs.Driver(cfg, seed='S', jobs_sha256='jobs', journal_dir=self.journal, streams_dir=self.streams,
                         call_fn=call_fn, pre_call_check=lambda: 'bin-sha', now_fn=self.clock.now,
                         sleep_fn=self.clock.sleep, log=lambda m: None, **kw)

    def job(self, jid='j1', task='T1', arm='A'):
        return {'task': task, 'id': jid, 'arm': arm, 'prompt': 'п', 'schema': {'type': 'object'}}

    def lost(self):
        return call(events=[ev_init(), ev_start(), ev_stop(), ev_result(default_structured=False)])

    # время сброса
    def test_reset_from_rejected_event(self):
        self.assertEqual(rs.reset_from_events([ev_init(), ev_rate()]),
                         datetime.fromtimestamp(1791821400, timezone.utc))

    def test_reset_from_event_ignores_allowed_and_reads_ms(self):
        self.assertIsNone(rs.reset_from_events([ev_rate('allowed'), ev_rate('allowed_warning')]))
        self.assertEqual(rs.reset_from_events([ev_rate(resets_at=1791821400000)]),
                         datetime.fromtimestamp(1791821400, timezone.utc))
        self.assertIsNone(rs.reset_from_events([ev_rate(resets_at=None)]))

    def test_probe_resets_at_is_unix_seconds(self):
        events = [json.loads(x) for x in FIXTURE.read_text(encoding='utf-8').splitlines() if x.strip()]
        info = next(e for e in events if e.get('type') == 'rate_limit_event')['rate_limit_info']
        t = datetime.fromtimestamp(info['resetsAt'], timezone.utc)
        self.assertEqual((t.year, t.month, t.day), (2026, 10, 12))   # день пробного вызова
        self.assertIsNone(rs.reset_from_events(events))               # статус allowed — не лимит

    def test_reset_text_with_date(self):
        now = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)
        self.assertEqual(rs.next_reset('resets Oct 14, 7pm (UTC)', now), datetime(2026, 10, 14, 19, 0, tzinfo=timezone.utc))
        self.assertEqual(rs.next_reset('resets Oct 14 at 7:30pm (UTC)', now),
                         datetime(2026, 10, 14, 19, 30, tzinfo=timezone.utc))
        self.assertEqual(rs.next_reset('resets Jan 2, 1am (UTC)', now), datetime(2027, 1, 2, 1, 0, tzinfo=timezone.utc))
        self.assertEqual(rs.next_reset('resets 7:30pm (UTC)', now), datetime(2026, 10, 12, 19, 30, tzinfo=timezone.utc))

    def test_weekly_limit_without_parsable_text_waits_by_event(self):
        reset = T0 + timedelta(hours=20)
        lim = call(events=[ev_init(), ev_rate(kind='seven_day', resets_at=reset.timestamp()),
                           ev_limit("You've hit your weekly limit · resets Mon 7pm")])
        script = Script([lim, call(events=good_stream())])
        drv = self.driver(make_cfg(), script)
        drv.start()
        drv.run([self.job()])
        recs = read_journal(self.journal, 'T1')
        self.assertEqual([r['outcome'] for r in recs], [rs.NA, rs.OK])
        self.assertEqual(recs[0]['reset_source'], 'rate_limit_event')
        self.assertGreaterEqual(self.clock.t, reset + timedelta(seconds=120))

    def test_too_long_wait_stops(self):
        lim = call(events=[ev_init(), ev_rate(kind='seven_day', resets_at=(T0 + timedelta(days=5)).timestamp()),
                           ev_limit('weekly')])
        drv = self.driver(make_cfg(), Script([lim]))
        drv.start()
        with self.assertRaises(rs.RunStop) as cm:
            drv.run([self.job()])
        self.assertIn('слишком долгое', str(cm.exception))

    def test_start_timeout_with_rejected_event_waits_not_retries(self):
        reset = T0 + timedelta(hours=1)
        dead = call(events=[ev_init(), ev_rate(resets_at=reset.timestamp())], returncode=1)
        script = Script([dead, call(events=good_stream())])
        drv = self.driver(make_cfg(), script)
        drv.start()
        drv.run([self.job()])
        recs = read_journal(self.journal, 'T1')
        self.assertEqual((recs[0]['outcome'], recs[0]['waits'], recs[0]['retries']), (rs.NA, 1, 0))

    def test_zero_usage_with_allowed_event_and_no_text_is_bounded_retry(self):
        z = call(events=[ev_init(), ev_rate('allowed'), ev_result(structured=None, inp=0, out=0, cost=0, model=None,
                                                                  is_error=True, text='overloaded',
                                                                  default_structured=False)])
        drv = self.driver(make_cfg(), Script([z, call(events=good_stream())]))
        drv.start()
        drv.run([self.job()])
        recs = read_journal(self.journal, 'T1')
        self.assertEqual((recs[0]['waits'], recs[0]['retries']), (0, 1))
        self.assertNotIn('wait_s', recs[0])

    # остановки
    def test_spawn_error_stops_without_record(self):
        drv = self.driver(make_cfg(), Script([call(spawn_error='OSError: x')]))
        drv.start()
        with self.assertRaises(rs.RunStop) as cm:
            drv.run([self.job()])
        self.assertIn('не запустился', str(cm.exception))
        self.assertEqual(read_journal(self.journal, 'T1'), [])

    def test_empty_stream_failure_is_recorded_then_stops(self):
        drv = self.driver(make_cfg(), Script([call(events=[], returncode=1), call(events=good_stream())]))
        drv.start()
        with self.assertRaises(rs.RunStop) as cm:
            drv.run([self.job('j1'), self.job('j2')])
        self.assertIn('поток пуст', str(cm.exception))
        recs = read_journal(self.journal, 'T1')
        self.assertEqual([(r['outcome'], r['final']) for r in recs], [(rs.FAIL, 'потерян')])

    def test_consecutive_lost_stop(self):
        jobs = [self.job(f'j{i}') for i in range(5)]
        drv = self.driver(make_cfg(max_consecutive_lost=3), Script([self.lost() for _ in range(5)]))
        drv.start()
        with self.assertRaises(rs.RunStop) as cm:
            drv.run(jobs)
        self.assertIn('подряд', str(cm.exception))
        self.assertEqual(len(read_journal(self.journal, 'T1')), 3)

    def test_lost_streak_resets_on_good(self):
        jobs = [self.job(f'j{i}') for i in range(5)]
        seq = [self.lost(), self.lost(), call(events=good_stream()), self.lost(), self.lost()]
        drv = self.driver(make_cfg(max_consecutive_lost=3), Script(seq))
        drv.start()
        drv.run(jobs)
        self.assertEqual(len(read_journal(self.journal, 'T1')), 5)

    def test_existing_stream_file_is_not_overwritten(self):
        seen = []

        def fn(cfg, job, gz):
            seen.append(Path(gz).name)
            Path(gz).parent.mkdir(parents=True, exist_ok=True)
            Path(gz).write_bytes(b'x')
            return call(events=[ev_init(), ev_limit()]) if len(seen) == 1 else call(events=good_stream())
        drv = self.driver(make_cfg(), fn)
        drv.start()
        job = self.job()
        drv._one_call(job, 1, 'основной')
        drv._one_call(job, 1, 'основной')               # тот же номер попытки, как после гибели драйвера
        self.assertEqual(len(set(seen)), 2)
        self.assertIn('.r2.', seen[1])

    # журнал для git
    def test_journal_slims_signature_thinking_and_init(self):
        sig = 'S' * 5000
        ev = [dict(ev_init(), skills=['a'] * 50, session_id='x', cwd='/home/u'),
              {'type': 'system', 'subtype': 'thinking_tokens', 'estimated_tokens': 50},
              {'type': 'system', 'subtype': 'thinking_tokens', 'estimated_tokens': 900},
              {'type': 'assistant', 'message': {'content': [{'type': 'thinking', 'thinking': '', 'signature': sig}]}},
              ev_result()]
        out = rs.journal_events(ev)
        text = json.dumps(out, ensure_ascii=False)
        self.assertNotIn(sig, text)
        self.assertNotIn('skills', out[0])
        self.assertEqual(out[0]['init_sha256'], rs.init_sha(ev[0]))
        blk = out[1]['message']['content'][0]['signature']
        self.assertEqual(blk['длина'], 5000)
        self.assertEqual(out[-1]['событий'], 2)
        self.assertEqual(out[-1]['последняя_оценка'], 900)

    def test_init_sha_ignores_session_and_paths(self):
        a = dict(ev_init(), session_id='1', uuid='u1', cwd='/tmp/a', skills=['x'])
        b = dict(ev_init(), session_id='2', uuid='u2', cwd='/tmp/b', skills=['x'])
        c = dict(ev_init(), session_id='2', uuid='u2', cwd='/tmp/b', skills=['y'])
        self.assertEqual(rs.init_sha(a), rs.init_sha(b))
        self.assertNotEqual(rs.init_sha(a), rs.init_sha(c))

    def test_record_has_init_file_and_raw_stream_fields(self):
        drv = self.driver(make_cfg(), Script([call(events=good_stream(), stream_sha256='ab', stream_bytes=7)]))
        drv.start()
        drv.run([self.job()])
        r = read_journal(self.journal, 'T1')[0]
        self.assertTrue((self.journal / f"init_{r['init_sha256'][:12]}.json").exists())
        self.assertEqual((r['stream']['sha256'], r['stream']['bytes']), ('ab', 7))
        self.assertEqual(r['model_usage_out'], {TARGET: 50})

    def test_probe_fixture_journal_is_small(self):
        events = [json.loads(x) for x in FIXTURE.read_text(encoding='utf-8').splitlines() if x.strip()]
        raw = sum(len(json.dumps(e, ensure_ascii=False)) for e in events if not rs.is_delta(e))
        slim = len(json.dumps(rs.journal_events(events), ensure_ascii=False))
        self.assertLess(slim, raw)
        text = json.dumps(rs.journal_events(events), ensure_ascii=False)
        self.assertIsNone(re.search(r'"signature": "[^"]', text))     # непустых подписей в журнале нет
        self.assertNotIn('"uuid"', text)
        print(f'\n  образец пробного вызова: поток без дельт {raw} байт, журнал {slim} байт', end=' ')

    # формат v1
    def test_load_jobs_task_from_id(self):
        p = self.root / 'jobs.jsonl'
        p.write_text(json.dumps({'id': 'WH_1|B_blind|3', 'prompt': 'п', 'schema': {}}) + '\n' +
                     json.dumps({'id': 'WH_1|exec', 'prompt': 'п', 'schema': {}}) + '\n', encoding='utf-8')
        jobs = rs.load_jobs(p, task_from_id=True)
        self.assertEqual([(j['task'], j['arm']) for j in jobs], [('WH_1', 'B_blind'), ('WH_1', 'exec')])
        with self.assertRaises(SystemExit):
            rs.load_jobs(p)

    def test_export_v1_format(self):
        seq = [call(events=good_stream()), self.lost(), call(events=[ev_init(), ev_limit()]), call(events=good_stream())]
        drv = self.driver(make_cfg(max_consecutive_lost=9), Script(seq))
        drv.start()
        jobs = [self.job('WH_1|A|0', task='WH_1'), self.job('WH_1|A|1', task='WH_1'), self.job('WH_1|A|2', task='WH_1')]
        drv.run(jobs)
        out = self.root / 'out.jsonl'
        rs.cmd_export(type('A', (), {'journal': str(self.journal), 'out': str(out)}))
        recs = {r['id']: r for r in map(json.loads, out.read_text(encoding='utf-8').splitlines())}
        self.assertEqual(len(recs), 3)
        good = [r for r in recs.values() if not r.get('error')]
        bad = [r for r in recs.values() if r.get('error')]
        self.assertEqual((len(good), len(bad)), (2, 1))
        self.assertEqual(good[0]['result'], {'answer': 'да'})
        self.assertIsNone(bad[0]['result'])
        self.assertTrue(bad[0]['error'].startswith('потерян: '))
        for r in recs.values():
            self.assertIsInstance(r['inp'], int)
            self.assertIsInstance(r['out'], int)

    def test_answer_key_order_is_preserved(self):
        ans = {'plan': 1, 'claim': 2, 'doubt': 3}
        drv = self.driver(make_cfg(), Script([call(events=[ev_init(), ev_start(), ev_stop(), ev_result(structured=ans)])]))
        drv.start()
        drv.run([self.job()])
        r = read_journal(self.journal, 'T1')[0]
        self.assertEqual(list(r['answer']), ['plan', 'claim', 'doubt'])

    def test_summary_counts_started_call_without_record(self):
        drv = self.driver(make_cfg(), Script([call(events=good_stream())]))
        drv.start()
        drv.run([self.job()])
        drv._log_run('вызов', {'task': 'T1', 'job': 'j9', 'arm': 'A', 'attempt': 1, 'role': 'основной', 'поток': 'x'})
        buf = io.StringIO()
        with mock.patch('sys.stdout', buf):
            rs.cmd_summary(type('A', (), {'journal': str(self.journal)}))
        head, row = buf.getvalue().strip().splitlines()[:2]
        cols = head.split('\t')
        vals = dict(zip(cols, row.split('\t')))
        self.assertEqual((vals['годных'], vals['без_записи'], vals['init']), ('1', '1', '1'))


class ProbeFixtureTests(unittest.TestCase):
    """Образец реального пробного вызова (см. tools/run_sealed2.py probe)."""

    @classmethod
    def setUpClass(cls):
        if FIXTURE.exists():
            cls.lines = [x for x in FIXTURE.read_text(encoding='utf-8').splitlines() if x.strip()]
        else:
            cls.lines = None

    def test_fixture_exists(self):
        self.assertIsNotNone(self.lines, 'нет образца tools/fixtures/run_sealed2_probe.jsonl: сделать probe')

    def test_fixture_has_no_leaks(self):
        if self.lines is None:
            self.skipTest('образца нет')
        self.assertEqual(rs.leak_scan('\n'.join(self.lines)), [])

    def test_fixture_classifies_as_good(self):
        if self.lines is None:
            self.skipTest('образца нет')
        events = [json.loads(x) for x in self.lines]
        results = [e for e in events if e.get('type') == 'result']
        self.assertEqual(len(results), 1)
        init = next(e for e in events if e.get('type') == 'system' and e.get('subtype') == 'init')
        self.assertEqual(init.get('claude_code_version'), rs.PINNED_VERSION)
        final = rs.normalize_final(results[0])
        v = rs.classify(final, events=events, unparsable=0, timed_out=False, returncode=0,
                        target_model=PROBE_TARGET, results_count=1)
        self.assertEqual(v.outcome, rs.OK, v.reason)


def main():
    loader = unittest.defaultTestLoader
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=1, stream=sys.stdout).run(suite)
    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    skipped = len(result.skipped)
    print(f'\nИТОГ: тестов {total}, прошло {total - failed - skipped}, провалено {failed}, пропущено {skipped}')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
