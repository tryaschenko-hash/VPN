"""WebSocket tunnel server - deploy on Render, handles both HTTP and WS."""
import asyncio, base64, hashlib, json, logging, os, socket, struct

PORT = int(os.getenv("PORT", "1080"))
BUF = 65536
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
RU = frozenset("5 23 31 37 46 62 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 109 128 176 178 185 188 192 193 194 195 212 213 217".split())

def is_ru(ip): return "." in ip and ip.split(".")[0] in RU
logging.basicConfig(level=getattr(logging, os.getenv("L", "INFO").upper()), format="%(asctime)s %(message)s", datefmt="%H:%M")
log = logging.getLogger("ws")
set_nodelay = lambda w: w.transport.get_extra_info('socket').setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) if hasattr(w, 'transport') else None

async def dial(host, port):
    try:
        r, w = await asyncio.wait_for(asyncio.open_connection(host, port), 20)
        set_nodelay(w); return r, w
    except: return None, None

async def read_frame(rd):
    h = await rd.readexactly(2)
    op = h[0] & 0x0F
    msk = bool(h[1] & 0x80)
    ln = h[1] & 0x7F
    if ln == 126: ln = struct.unpack("!H", await rd.readexactly(2))[0]
    elif ln == 127: ln = struct.unpack("!Q", await rd.readexactly(8))[0]
    mk = await rd.readexactly(4) if msk else None
    pl = await rd.readexactly(ln)
    if mk: pl = bytes(b ^ mk[i%4] for i,b in enumerate(pl))
    return op, pl

async def handle(rd, wr):
    set_nodelay(wr)
    try:
        line = await rd.readuntil(b"\r\n")
    except: wr.close(); return
    parts = line.decode().split()
    if len(parts) < 2: wr.close(); return
    method, path = parts[0], parts[1]

    headers = {}
    while True:
        hl = await rd.readline()
        if hl in (b"\r\n", b"\n", b""): break
        if b":" in hl:
            k, v = hl.decode().split(":", 1)
            headers[k.strip().lower()] = v.strip()

    if method == "GET" and path in ("/", "/health"):
        wr.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"); await wr.drain(); wr.close(); return

    if method == "GET" and path.startswith("/tunnel?"):
        key = headers.get("sec-websocket-key", "")
        if not key: wr.write(b"HTTP/1.1 400\r\n\r\n"); await wr.drain(); wr.close(); return

        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse("http://h"+path).query)
        host, port = qs.get("host", [""])[0], int(qs.get("port", ["0"])[0])
        if not host or not port:
            wr.write(b"HTTP/1.1 400\r\n\r\n"); await wr.drain(); wr.close(); return

        accept = base64.b64encode(hashlib.sha1((key+WS_GUID).encode()).digest()).decode()
        wr.write(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n".encode())
        await wr.drain()

        rdr, wtr = await dial(host, port)
        if not rdr:
            await ws_send(wr, 0x8, b"")
            wr.close(); return
        log.info(f"[{'RU' if is_ru(host) else 'WW'}] {host}:{port}")

        async def ws2tcp():
            try:
                while True:
                    op, pl = await read_frame(rd)
                    if op == 0x8: break
                    if op == 0x9: await ws_send(wr, 0xA, pl)
                    elif op == 0x2: wtr.write(pl); await wtr.drain()
            except: pass
            finally:
                try: wtr.close()
                except: pass

        async def tcp2ws():
            try:
                while True:
                    d = await rdr.read(BUF)
                    if not d: break
                    await ws_send(wr, 0x2, d)
            except: pass
            finally:
                try: await ws_send(wr, 0x8, b""); wr.close()
                except: pass

        await asyncio.gather(ws2tcp(), tcp2ws())
    else:
        wr.write(b"HTTP/1.1 400\r\n\r\n"); await wr.drain(); wr.close()

async def ws_send(w, op, pl):
    h = bytes([0x80 | op])
    if len(pl) < 126: h += bytes([len(pl)])
    elif len(pl) < 65536: h += bytes([126]) + struct.pack("!H", len(pl))
    else: h += bytes([127]) + struct.pack("!Q", len(pl))
    w.write(h + pl); await w.drain()

async def main():
    srv = await asyncio.start_server(handle, "0.0.0.0", PORT)
    log.info(f"WS server on 0.0.0.0:{PORT}")
    async with srv: await srv.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
