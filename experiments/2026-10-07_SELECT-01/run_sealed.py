# SELECT-01: запуск голов БЕЗ инструментов (линза 1, находка 1: у голов workflow были Bash/Read и т.д., изоляция держалась на словах).
# Каждая голова — отдельный `claude -p` с --tools "" (доступен только StructuredOutput), без настроек и CLAUDE.md (--setting-sources ""),
# без MCP (--strict-mcp-config), из пустой папки, без сохранения сессии. Модель задана явно. Токены — из usage ответа.
#   python3 run_sealed.py <jobs.jsonl> <out.jsonl> [параллельно, 6]
# jobs.jsonl: {"id": ..., "prompt": ..., "schema": {...}}. Продолжает с места: id, уже записанные в out.jsonl без ошибки, пропускаются.
# Сбой (нет structured_output, ненулевой код, таймаут) — один автоматический перезапуск; второй сбой пишется как error.
import concurrent.futures as cf, json, os, subprocess, sys, tempfile, threading
MODEL = 'claude-opus-5-5'; TIMEOUT = 1800
lock = threading.Lock()

def call(job):
    with tempfile.TemporaryDirectory(prefix='sealed_') as cwd:
        cmd = ['claude', '-p', job['prompt'], '--tools', '', '--setting-sources', '', '--strict-mcp-config', '--no-session-persistence',
               '--model', MODEL, '--json-schema', json.dumps(job['schema']), '--output-format', 'json']
        try:
            p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT)
            d = json.loads(p.stdout)
        except Exception as e:
            return dict(error=f'{type(e).__name__}: {str(e)[:200]}')
    u = d.get('usage') or {}; so = d.get('structured_output')
    rec = dict(result=so, inp=u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0),
               out=u.get('output_tokens', 0), thinking=(u.get('output_tokens_details') or {}).get('thinking_tokens'),
               models={m: v.get('outputTokens') for m, v in (d.get('modelUsage') or {}).items()}, permission_denials=len(d.get('permission_denials') or []),
               cost_usd=d.get('total_cost_usd'))
    if so is None: rec['error'] = f"нет structured_output: {str(d.get('result'))[:200]}"
    return rec

def run(job, fh):
    rec = call(job)
    if rec.get('error'): rec = dict(call(job), retried=True)
    with lock:
        fh.write(json.dumps(dict(id=job['id'], **rec), ensure_ascii=False) + '\n'); fh.flush()
    return rec

if __name__ == '__main__':
    jobs = [json.loads(l) for l in open(sys.argv[1])]; out = sys.argv[2]; par = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    done = set()
    if os.path.exists(out):
        for l in open(out):
            r = json.loads(l)
            if not r.get('error'): done.add(r['id'])
    todo = [j for j in jobs if j['id'] not in done]
    print(f'заданий {len(jobs)}, уже сделано {len(done)}, осталось {len(todo)}', flush=True)
    with open(out, 'a') as fh, cf.ThreadPoolExecutor(par) as ex:
        for k, r in enumerate(cf.as_completed([ex.submit(run, j, fh) for j in todo]), 1):
            if k % 10 == 0 or k == len(todo): print(f'{k}/{len(todo)}', flush=True)
