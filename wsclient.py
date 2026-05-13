"""Local SOCKS5 -> WebSocket tunnel to Render."""
import asyncio, hashlib, base64, json, logging, os, socket, struct

TARGET = os.getenv("WS_TARGET", "https://vpn-c6bv.onrender.com")
LOCAL_PORT = int(os.getenv("LOCAL_PORT", "1080"))
BUF = 65536
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

logging.basicConfig(level=getattr(logging, os.getenv("L", "INFO").upper()), format="%(asctime)s %(message)s", datefmt="%H:%M")
log = logging.getLogger("wsclient")

async def ws_open(host, tcp_host, tcp_port):
    r, w = await asyncio.wait_for(asyncio.open_connection(host, 443, ssl=True), 15)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET /tunnel?host={tcp_host}&port={tcp_port} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    ).encode()
    w.write(req); await w.drain()
    while True:
        l = await r.readline()
        if l in (b"\r\n", b"\n", b""): break
    return r, w

async def ws_recv(rd):
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

async def ws_send(w, op, pl):
    h = bytes([0x80 | op])
    if len(pl) < 126: h += bytes([0x80 | len(pl)])
    elif len(pl) < 65536: h += bytes([0x80 | 126]) + struct.pack("!H", len(pl))
    else: h += bytes([0x80 | 127]) + struct.pack("!Q", len(pl))
    mk = os.urandom(4)
    w.write(h + mk + bytes(b ^ mk[i%4] for i,b in enumerate(pl))); await w.drain()

async def handle(rd, wr):
    try:
        first = await rd.readexactly(1)
    except: wr.close(); return
    if first != b"\x05": wr.close(); return

    nm = (await rd.readexactly(1))[0]
    meth = set(await rd.readexactly(nm))
    wr.write(b"\x05\x00"); await wr.drain()

    _, cmd, _ = struct.unpack("!BBB", await rd.readexactly(3))
    if cmd != 1:
        wr.write(b"\x05\x07\x00\x01" + b"\x00"*6); await wr.drain(); return

    atyp = (await rd.readexactly(1))[0]
    if atyp == 1: host = socket.inet_ntoa(await rd.readexactly(4))
    elif atyp == 3:
        dl = (await rd.readexactly(1))[0]; host = (await rd.readexactly(dl)).decode()
    elif atyp == 4: host = socket.inet_ntop(socket.AF_INET6, await rd.readexactly(16))
    else:
        wr.write(b"\x05\x08\x00\x01" + b"\x00"*6); await wr.drain(); return
    port = struct.unpack("!H", await rd.readexactly(2))[0]

    try:
        wsr, wsw = await ws_open("vpn-c6bv.onrender.com", host, port)
    except:
        wr.write(b"\x05\x05\x00\x01" + b"\x00"*6); await wr.drain(); return

    log.info(f"[WS] {host}:{port}")
    wr.write(b"\x05\x00\x00\x01" + b"\x00"*6); await wr.drain()

    async def to_ws():
        try:
            while True:
                d = await rd.read(BUF)
                if not d: break
                await ws_send(wsw, 0x2, d)
        except: pass
        finally:
            try: await ws_send(wsw, 0x8, b"")
            except: pass

    async def from_ws():
        try:
            while True:
                op, pl = await ws_recv(wsr)
                if op == 0x8: break
                if op == 0x2: wr.write(pl); await wr.drain()
        except: pass
        finally:
            try: wr.close()
            except: pass

    await asyncio.gather(to_ws(), from_ws())

async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", LOCAL_PORT)
    log.info(f"SOCKS5 on 127.0.0.1:{LOCAL_PORT} -> {TARGET}")
    async with srv: await srv.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
