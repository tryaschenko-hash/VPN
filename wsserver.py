"""WebSocket tunnel server - deploy on Render."""
import asyncio, json, logging, os, socket, websockets

PORT = int(os.getenv("PORT", "1080"))
BUF = 65536
RU = frozenset("5 23 31 37 46 62 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 109 128 176 178 185 188 192 193 194 195 212 213 217".split())
def is_ru(ip): return "." in ip and ip.split(".")[0] in RU

logging.basicConfig(level=getattr(logging, os.getenv("L", "INFO").upper()), format="%(asctime)s %(message)s", datefmt="%H:%M")
log = logging.getLogger("ws")

def set_nodelay(w):
    try: w.transport.get_extra_info('socket').setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except: pass

async def tunnel_ws(ws):
    info = json.loads(await ws.recv())
    host, port = info["host"], info["port"]
    try:
        r, w = await asyncio.wait_for(asyncio.open_connection(host, port), 20)
        set_nodelay(w)
    except:
        await ws.send(json.dumps({"error": "connect failed"}))
        return
    log.info(f"[{'RU' if is_ru(host) else 'WW'}] {host}:{port}")
    await ws.send(json.dumps({"ok": True}))

    async def ws2tcp():
        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    w.write(msg); await w.drain()
        except: pass
        finally:
            try: w.close()
            except: pass

    async def tcp2ws():
        try:
            while True:
                d = await r.read(BUF)
                if not d: break
                await ws.send(d)
        except: pass
        finally:
            try: await ws.close()
            except: pass

    await asyncio.gather(ws2tcp(), tcp2ws())

async def health(request):
    return websockets.http11.Response(200, "OK", [(b"Content-Type", b"text/plain")], b"OK\n")

async def main():
    async with websockets.serve(tunnel_ws, "0.0.0.0", PORT, process_request=health):
        log.info(f"WS server on 0.0.0.0:{PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
