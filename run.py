"""Download xray-core and start it - works on Render (Python env)."""
import os, subprocess, sys, urllib.request, zipfile, json, shutil, stat

PORT = os.environ.get("PORT", "10000")
URL = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
DIR = os.path.dirname(os.path.abspath(__file__))
XRAY = os.path.join(DIR, "xray")
CFG = os.path.join(DIR, "xray-config.json")

if not os.path.exists(XRAY):
    print("Downloading xray-core...")
    zip_path = os.path.join(DIR, "xray.zip")
    urllib.request.urlretrieve(URL, zip_path)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(DIR)
    os.remove(zip_path)
    os.chmod(XRAY, os.stat(XRAY).st_mode | stat.S_IEXEC)
    print("Done")

with open(CFG) as f:
    cfg = json.load(f)
for i in cfg.get("inbounds", []):
    i["port"] = int(PORT)
with open(CFG, "w") as f:
    json.dump(cfg, f)

print(f"Starting xray on port {PORT}")
os.execv(XRAY, [XRAY, "run", "-c", CFG])
