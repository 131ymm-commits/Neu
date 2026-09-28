# PERSUADE-01: задачи с правдой от кода. Генератор — hive_q.make из HIVE-01 (сверено по коду, не по памяти).
# Публичная часть (тексты) — tasks/<tag>.json; правда — /root/persuade_secret/<tag>.json, вне репозитория (головы её не видят).
#   python3 tasks.py <tag> <seed0> <per_family> [семейства через запятую]
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '2026-09-26_HIVE-01'))
from hive_q import make
SECRET = '/root/persuade_secret'
DEFAULT = ['TWIN', 'COL3', 'SUB5', 'PART', 'COLLATZ']
def build(tag, seed0, per, fams=DEFAULT):
    os.makedirs(SECRET, exist_ok=True); os.makedirs('tasks', exist_ok=True)
    pub, truth = [], {}
    for f in fams:
        for i in range(per):
            q = make(f, seed0 + i); tid = f'{f}-{seed0 + i}'
            pub.append(dict(id=tid, fam=f, text=q['text'])); truth[tid] = str(q['truth'])
    json.dump(pub, open(f'tasks/{tag}.json', 'w'), ensure_ascii=False, indent=1)
    json.dump(truth, open(f'{SECRET}/{tag}.json', 'w'))
    return pub
if __name__ == '__main__':
    fams = sys.argv[4].split(',') if len(sys.argv) > 4 else DEFAULT
    pub = build(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), fams)
    print(f'{len(pub)} задач → tasks/{sys.argv[1]}.json; правда → {SECRET}/{sys.argv[1]}.json')
