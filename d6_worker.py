"""Hidden child process. EOF/stop on the private parent pipe means shutdown."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import threading
from d6_bridge import bridge

def main():
    root=Path(__file__).resolve().parent
    handler=RotatingFileHandler(root/'d6_bridge.log',maxBytes=2_000_000,backupCount=3,encoding='utf-8')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',handlers=[handler])
    stop=threading.Event()
    def control():
        sys.stdin.readline()  # A command or EOF (parent gone) both stop the bridge.
        stop.set()
    threading.Thread(target=control,daemon=True).start()
    def status(state):
        print(json.dumps({'state':state}),flush=True)
    try:
        bridge(stop,on_status=status)
        return 0
    except Exception:
        logging.exception('Bridge failed')
        status('error')
        return 1

if __name__=='__main__': sys.exit(main())
