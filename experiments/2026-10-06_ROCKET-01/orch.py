# Оркестратор: begin/end эпизода (головам недоступно)
import json, socket, sys
def send(slot, req):
    s = socket.socket(socket.AF_UNIX); s.connect(f'/tmp/claude-0/fact/slot{slot}.sock'); s.sendall(json.dumps(req).encode() + b'\n\x00'); d = b''
    while True:
        p = s.recv(65536)
        if not p: break
        d += p
    return json.loads(d.decode())
if __name__ == '__main__':
    slot, cmd = int(sys.argv[1]), sys.argv[2]
    print(json.dumps(send(slot, dict(cmd=cmd, ep=sys.argv[3] if len(sys.argv) > 3 else None, max_steps=sys.argv[4] if len(sys.argv) > 4 else 0)), ensure_ascii=False, indent=1))
