"""Single owner of a restartable bridge process; independent of Windows tray UI."""
import json
import logging
import os
import subprocess
import threading

class Controller:
    def __init__(self,command,cwd,on_status=lambda state: None,grace=8):
        self.command,self.cwd,self.on_status,self.grace=command,cwd,on_status,grace
        self.lock=threading.Lock()
        self.wake=threading.Event()
        self.enabled=False
        self.quitting=False
        self.state='disabled'
        self.process=None
        self.stop_generation=0
        self.process_generation=0
        self.thread=threading.Thread(target=self._run,name='bridge-supervisor')
        self.thread.start()

    def set_enabled(self,value):
        with self.lock:
            if not self.quitting:
                if self.enabled and not value: self.stop_generation+=1
                self.enabled=value
        self.wake.set()

    def quit(self):
        with self.lock:
            self.quitting=True
            self.enabled=False
        self.wake.set()

    def _status(self,state):
        self.state=state
        try: self.on_status(state)
        except Exception: logging.exception('Tray status update failed')

    def _read(self,process):
        try:
            for line in process.stdout:
                try: state=json.loads(line)['state']
                except (ValueError,KeyError,TypeError):
                    logging.error('Bridge startup output: %s',line.rstrip()[:2000])
                    continue
                with self.lock:
                    active=(self.enabled and not self.quitting and self.process is process
                            and self.process_generation==self.stop_generation)
                if active and state in ('connecting','connected','offline','error'):
                    self._status(state)
        finally:
            process.stdout.close()

    def _stop(self,process):
        self._status('stopping')
        try:
            try:
                process.stdin.write('stop\n');process.stdin.flush()
            except (OSError,ValueError): pass
            try: process.wait(timeout=self.grace)
            except subprocess.TimeoutExpired:
                logging.warning('Bridge did not stop in time; terminating child')
                process.terminate()
                try: process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait()
        finally:
            try: process.stdin.close()
            except OSError: pass  # A failed flush must not abort supervisor cleanup.

    def _run(self):
        reader=None
        try:
            while True:
                with self.lock:
                    enabled,quitting=self.enabled,self.quitting
                    generation=self.stop_generation
                process=self.process
                if process is not None and (not enabled or quitting or generation!=self.process_generation):
                    self._stop(process)
                    if reader: reader.join(timeout=2)
                    self.process=None
                    self._status('disabled')
                elif process is not None and process.poll() is not None:
                    try: process.stdin.close()
                    except OSError: pass
                    if reader: reader.join(timeout=2)
                    self.process=None
                    with self.lock: self.enabled=False
                    self._status('error')
                elif enabled and process is None:
                    self._status('starting')
                    try:
                        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
                        self.process_generation=generation
                        self.process=subprocess.Popen(self.command,cwd=self.cwd,
                            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                            text=True,encoding='utf-8',bufsize=1,creationflags=flags)
                        reader=threading.Thread(target=self._read,args=(self.process,),daemon=True)
                        reader.start()
                    except Exception:
                        logging.exception('Cannot start bridge')
                        with self.lock: self.enabled=False
                        self._status('error')
                if quitting and self.process is None: break
                self.wake.wait(.1);self.wake.clear()
        finally:
            if self.process is not None:
                self._stop(self.process)
                self.process=None
