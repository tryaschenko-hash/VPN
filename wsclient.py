"""Local SOCKS5 proxy -> WebSocket tunnel to Render."""
import asyncio, json, logging, os, socket, struct, websockets

TARGET = os.getenv("WS_TARGET", "wss://vpn-c6bv.onrender.com")
LOCAL_PORT = int(os.getenv("LOCAL_PORT", "1080"))
BUF = 65536

logging.basicConfig(level=getattr(logging, os.getenv("L", "INFO").upper()), format="%(asctime)s %(message)s", datefmt="%H:%M")
log = logging.getLogger("client")

async def handle(rd, wr):
    try:
        first = await rd.readexactly(1)
    except:
        try: wr.close()
        except: pass
        return

    if first != b"\x05":
        wr.close(); return

    nm = (await rd.readexactly(1))[0]
    meth = set(await rd.readexactly(nm))
    wr.write(b"\x05\x00"); await wr.drain()

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

    try:
        ws = await websockets.connect(TARGET, max_size=2**24)
        await ws.send(json.dumps({"host": host, "port": port}))
        resp = json.loads(await ws.recv())
        if "error" in resp:
            wr.write(b"\x05\x05\x00\x01" + b"\x00" * 6); await wr.drain(); return
    except:
        wr.write(b"\x05\x05\x00\x01" + b"\x00" * 6); await wr.drain(); return

    log.info(f"[WS] {host}:{port}")
    wr.write(b"\x05\x00\x00\x01" + b"\x00" * 6); await wr.drain()

    async def local2ws():
        try:
            while True:
                d = await rd.read(BUF)
                if not d: break
                await ws.send(d)
        except: pass

    async def ws2local():
        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    wr.write(msg); await wr.drain()
        except: pass
        finally:
            try: wr.close()
            except: pass

    await asyncio.gather(local2ws(), ws2local())

async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", LOCAL_PORT)
    log.info(f"SOCKS5 on 127.0.0.1:{LOCAL_PORT} -> {TARGET}")
    async with srv: await srv.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
