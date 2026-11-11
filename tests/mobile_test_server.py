"""Browser test server with graceful cross-process shutdown on Windows."""
from pathlib import Path
import sys
import threading
import time
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
server = uvicorn.Server(uvicorn.Config('kiosk.server:app', host='127.0.0.1', port=int(sys.argv[1])))
stop_path = Path(sys.argv[2])

def watch():
    while not stop_path.exists():
        time.sleep(.1)
    server.should_exit = True

threading.Thread(target=watch, daemon=True).start()
server.run()
