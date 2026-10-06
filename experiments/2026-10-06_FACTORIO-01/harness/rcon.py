import socket, struct
class RCON:
    def __init__(s, host='127.0.0.1', port=27015, pw='neu'):
        s.s = socket.create_connection((host, port), 10); s.i = 0; s._send(3, pw); s._recv()
    def _send(s, t, body):
        s.i += 1; b = body.encode() + b'\x00\x00'; s.s.sendall(struct.pack('<iii', len(b) + 8, s.i, t) + b)
    def _recv(s):
        n = struct.unpack('<i', s._read(4))[0]; d = s._read(n); return d[8:-2].decode(errors='replace')
    def _read(s, n):
        b = b''
        while len(b) < n: b += s.s.recv(n - len(b))
        return b
    def cmd(s, c): s._send(2, c); return s._recv()
