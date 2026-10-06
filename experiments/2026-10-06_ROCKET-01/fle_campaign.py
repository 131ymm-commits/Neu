# Утилита головы в кампании ROCKET-01: step (код из stdin) | status | notes | note (текст из stdin)
import json, socket, sys
slot, cmd = int(sys.argv[1]), sys.argv[2]
req = dict(cmd=cmd, code=sys.stdin.read() if cmd in ('step', 'note') else '')
if cmd in ('begin', 'end'): raise SystemExit('эта команда только для оркестратора')
s = socket.socket(socket.AF_UNIX); s.connect(f'/tmp/claude-0/fact/slot{slot}.sock'); s.sendall(json.dumps(req).encode() + b'\n\x00')
d = b''
while True:
    p = s.recv(65536)
    if not p: break
    d += p
print(json.dumps(json.loads(d.decode()), ensure_ascii=False, indent=1))
