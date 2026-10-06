# Утилита агента: python3 fle_step.py <slot> step < код.py   |   python3 fle_step.py <slot> info
import json, socket, sys
slot, cmd = int(sys.argv[1]), sys.argv[2]
req = dict(cmd=cmd, code=sys.stdin.read() if cmd == 'step' else '')
s = socket.socket(socket.AF_UNIX); s.connect(f'/tmp/claude-0/fact/slot{slot}.sock'); s.sendall(json.dumps(req).encode() + b'\n\x00')
data = b''
while True:
    p = s.recv(65536)
    if not p: break
    data += p
print(json.dumps(json.loads(data.decode()), ensure_ascii=False, indent=1))
