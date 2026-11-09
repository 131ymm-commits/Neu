#!/usr/bin/env python3
# TESTER-01: драйвер голов — tools/run_sealed2.py (закреплённый CLI, чистый контекст вне git, журнал, ожидание лимита, возобновление)
# с одним отличием: голове подключается MCP-сервер игры, и разрешены только его инструменты (mcp__game__*).
# Файл run_sealed2.py не меняется (его хеши — в регистрациях прошлых опытов). Каталог сессии — свой на каждый вызов (callNN).
#   python3 driver_tester01.py run --jobs <jobs.jsonl> --seed 1 --journal <каталог> --streams <каталог> --config cfg_tester01.json --task-from-id
import importlib.util, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('run_sealed2', ROOT / 'tools' / 'run_sealed2.py'); RS = importlib.util.module_from_spec(spec); spec.loader.exec_module(RS)
_orig, _calls = RS.build_cmd, {}

def build_cmd(cfg, job):
    cmd = _orig(cfg, job)
    m = job.get('mcp')
    if not m:
        return cmd
    k = job['id']; _calls[k] = _calls.get(k, 0) + 1
    srv = json.loads(json.dumps(m))
    env = srv['mcpServers']['game'].setdefault('env', {})
    env['TESTER_OUT'] = str(Path(env['TESTER_OUT']) / f'call{_calls[k]:02d}')
    # --mcp-config — последним: он принимает несколько значений
    return cmd + ['--allowedTools', 'mcp__game__*', '--max-turns', str(job.get('max_turns', 220)), '--mcp-config', json.dumps(srv, ensure_ascii=False)]

RS.build_cmd = build_cmd
if __name__ == '__main__':
    sys.exit(RS.main())
