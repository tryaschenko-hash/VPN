#!/usr/bin/env python3
"""Universal proxy (SOCKS5 + HTTP CONNECT) with Russian IP detection.
   Deploy on Render, Railway, Fly.io, or any VPS.
   Env: HOST, PORT, AUTH (user:pass), L (log level)
"""

import asyncio, logging, os, struct, socket

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "1080"))
AUTH = os.getenv("AUTH", "")
BUF = 65536
RU = frozenset("5 23 31 37 46 62 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 109 128 176 178 185 188 192 193 194 195 212 213 217".split())

def is_ru(ip):
    return "." in ip and ip.split(".")[0] in RU

logging.basicConfig(level=getattr(logging, os.getenv("L", "INFO").upper()), format="%(asctime)s %(message)s", datefmt="%H:%M")
log = logging.getLogger("proxy")

def set_nodelay(w):
    try:
        w.transport.get_extra_info('socket').setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except: pass

async def tunnel(rd, wr, rdr, wtr):
    set_nodelay(wr); set_nodelay(wtr)
    async def _relay(src, dst):
        try:
            while True:
                d = await src.read(BUF)
                if not d: break
                dst.write(d); await dst.drain()
        except (asyncio.CancelledError, ConnectionError):
            pass
        except: pass
        finally:
            try: dst.close()
            except: pass
    t1 = asyncio.create_task(_relay(rd, wtr))
    t2 = asyncio.create_task(_relay(rdr, wr))
    done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED, timeout=3600)
    for t in pending: t.cancel()
    for t in pending:
        try: await t
        except: pass

async def dial(host, port):
    try:
        r, w = await asyncio.wait_for(asyncio.open_connection(host, port), 20)
        set_nodelay(w)
        return r, w
    except: return None, None

async def handle(rd, wr):
    set_nodelay(wr)
    try:
        first = await rd.readexactly(1)
    except:
        try: wr.close()
        except: pass
        return
    try:
        if first == b"\x05":
            await _socks5(rd, wr)
        elif first == b"C":
            await _connect(rd, wr, first)
        else:
            if first in (b"G", b"P", b"H", b"D", b"O", b"T"):
                while True:
                    l = await rd.readline()
                    if l in (b"\r\n", b"\n", b""): break
            wr.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
            await wr.drain()
    except Exception as e:
        if str(e):
            log.error(f"ERR: {e}")
    finally:
        try: wr.close()
        except: pass

async def _socks5(rd, wr):
    nm = (await rd.readexactly(1))[0]
    meth = set(await rd.readexactly(nm))
    if AUTH and 2 in meth:
        wr.write(b"\x05\x02"); await wr.drain()
        await rd.readexactly(1)
        ul = (await rd.readexactly(1))[0]; u = (await rd.readexactly(ul)).decode()
        pl = (await rd.readexactly(1))[0]; p = (await rd.readexactly(pl)).decode()
        if f"{u}:{p}" != AUTH:
            wr.write(b"\x01\x01"); await wr.drain(); return
        wr.write(b"\x01\x00"); await wr.drain()
    elif 0 in meth:
        wr.write(b"\x05\x00"); await wr.drain()
    else:
        wr.write(b"\x05\xff"); await wr.drain(); return
    _, cmd, _ = struct.unpack("!BBB", await rd.readexactly(3))
    if cmd != 1:
        wr.write(b"\x05\x07\x00\x01" + b"\x00" * 6); await wr.drain(); return
    atyp = (await rd.readexactly(1))[0]
    if atyp == 1: host = socket.inet_ntoa(await rd.readexactly(4))
    elif atyp == 3:
        dl = (await rd.readexactly(1))[0]; host = (await rd.readexactly(dl)).decode()
    elif atyp == 4: host = socket.inet_ntop(socket.AF_INET6, await rd.readexactly(16))
    else:
        wr.write(b"\x05\x08\x00\x01" + b"\x00" * 6); await wr.drain(); return
    port = struct.unpack("!H", await rd.readexactly(2))[0]
    rdr, wtr = await dial(host, port)
    if not rdr:
        wr.write(b"\x05\x05\x00\x01" + b"\x00" * 6); await wr.drain(); return
    log.info(f"[{'RU' if is_ru(host) else 'WW'}] {host}:{port}")
    wr.write(b"\x05\x00\x00\x01" + b"\x00" * 6); await wr.drain()
    await tunnel(rd, wr, rdr, wtr)

async def _connect(rd, wr, first):
    line = first + await rd.readline()
    parts = line.decode().split()
    if not parts or parts[0] != "CONNECT" or len(parts) < 2 or ":" not in parts[1]:
        wr.write(b"HTTP/1.1 400\r\n\r\n"); await wr.drain(); return
    host, port = parts[1].split(":")
    if host.startswith("["):
        host = host.strip("[]")
    port = int(port)
    while True:
        l = await rd.readline()
        if l in (b"\r\n", b"\n", b""): break
    rdr, wtr = await dial(host, port)
    if not rdr:
        wr.write(b"HTTP/1.1 502\r\n\r\n"); await wr.drain(); return
    log.info(f"[{'RU' if is_ru(host) else 'WW'}] {host}:{port}")
    wr.write(b"HTTP/1.1 200 Connection established\r\n\r\n"); await wr.drain()
    await tunnel(rd, wr, rdr, wtr)

async def main():
    srv = await asyncio.start_server(handle, HOST, PORT)
    log.info(f"Proxy on {HOST}:{PORT}")
    async with srv: await srv.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
