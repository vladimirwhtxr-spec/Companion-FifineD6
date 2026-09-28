import sys
import tempfile
from pathlib import Path
import time
import unittest
from unittest.mock import patch
import threading
import json
from tray_controller import Controller

class TrayLifecycleTests(unittest.TestCase):
    def test_bridge_cancel_releases_usb(self):
        import d6_bridge as b
        closed=threading.Event();connecting=threading.Event();stop=threading.Event()
        class Device:
            def read(self): time.sleep(.005)
            def tick(self): pass
            def draw(self,*args): pass
            def close(self): closed.set()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'screen_map.json').write_text(json.dumps({str(i):i for i in range(1,16)}),encoding='utf-8-sig')
            (root/'config.json').write_text(json.dumps({'host':'127.0.0.1','port':16622}),encoding='utf-8-sig')
            errors=[]
            def run():
                try: b.bridge(stop,lambda state: connecting.set())
                except Exception as e: errors.append(e)
            with patch.object(b,'ROOT',root),patch.object(b,'D6',Device),patch.object(b.socket,'create_connection',side_effect=ConnectionRefusedError):
                thread=threading.Thread(target=run);thread.start()
                try:
                    self.assertTrue(connecting.wait(2))
                finally:
                    stop.set();thread.join(3)
                self.assertFalse(thread.is_alive())
                self.assertTrue(closed.is_set())
                self.assertEqual(errors,[])

    def wait_for(self,predicate,timeout=4):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if predicate(): return
            time.sleep(.01)
        self.fail('Timed out waiting for process state')

    def test_stop_restart_and_exit(self):
        # A real child process: the supervisor must not leave it running on disable.
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'closed'
            code="import sys,json; from pathlib import Path; print(json.dumps({'state':'connected'}),flush=True); sys.stdin.readline(); Path('closed').write_text('released')"
            c=Controller([sys.executable,'-u','-c',code],tmp)
            try:
                c.set_enabled(True)
                self.wait_for(lambda:c.state=='connected')
                first=c.process
                c.set_enabled(True)  # repeated enable never spawns another child
                time.sleep(.15)
                self.assertIs(c.process,first)
                c.set_enabled(False)
                self.wait_for(lambda:c.state=='disabled')
                self.assertIsNotNone(first.poll())
                self.assertEqual(marker.read_text(),'released')
                marker.unlink()
                c.set_enabled(True)
                self.wait_for(lambda:c.state=='connected')
                second=c.process
                self.assertNotEqual(first.pid,second.pid)
                c.quit();c.thread.join(4)
                self.assertFalse(c.thread.is_alive())
                self.assertIsNotNone(second.poll())
                self.assertTrue(marker.exists())
            finally:
                c.quit();c.thread.join(4)

    def test_hung_child_is_terminated(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=Controller([sys.executable,'-u','-c',"import time; print('{\"state\":\"connected\"}',flush=True); time.sleep(60)"],tmp,grace=.1)
            try:
                c.set_enabled(True)
                self.wait_for(lambda:c.state=='connected')
                child=c.process
                c.quit();c.thread.join(4)
                self.assertFalse(c.thread.is_alive())
                self.assertIsNotNone(child.poll())
            finally: c.quit();c.thread.join(4)

    def test_quick_disable_enable_restarts_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            code="import sys; print('{\"state\":\"connected\"}',flush=True); sys.stdin.readline()"
            c=Controller([sys.executable,'-u','-c',code],tmp)
            try:
                c.set_enabled(True)
                self.wait_for(lambda:c.state=='connected')
                old=c.process
                # Both requests arrive before the supervisor's next iteration.
                with c.lock:
                    c.enabled=False;c.stop_generation+=1;c.enabled=True
                c.wake.set()
                self.wait_for(lambda:c.state=='connected' and c.process is not old)
                self.assertIsNotNone(old.poll())
            finally: c.quit();c.thread.join(4)

    def test_import_error_is_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=Controller([sys.executable,'-c','import nonexistent_d6_test_module'],tmp)
            try:
                with self.assertLogs(level='ERROR') as captured:
                    c.set_enabled(True)
                    self.wait_for(lambda:c.state=='error' and not c.enabled)
                self.assertIn('ModuleNotFoundError','\n'.join(captured.output))
            finally: c.quit();c.thread.join(4)

    def test_usb_closed_if_thread_start_fails(self):
        import d6_bridge as b
        closed=threading.Event()
        class Device:
            def close(self): closed.set()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'screen_map.json').write_text(json.dumps({str(i):i for i in range(1,16)}))
            (root/'config.json').write_text('{"host":"localhost","port":16622}')
            with patch.object(b,'ROOT',root),patch.object(b,'D6',Device),patch.object(b.USBWorker,'start',side_effect=RuntimeError('thread failed')):
                with self.assertRaisesRegex(RuntimeError,'thread failed'): b.bridge()
            self.assertTrue(closed.is_set())

    def test_child_error_can_be_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=Controller([sys.executable,'-c','raise SystemExit(1)'],tmp)
            try:
                c.set_enabled(True)
                self.wait_for(lambda:c.state=='error' and not c.enabled)
                self.assertIsNone(c.process)
                c.command=[sys.executable,'-u','-c',"import sys; print('{\"state\":\"connected\"}',flush=True); sys.stdin.readline()"]
                c.set_enabled(True)
                self.wait_for(lambda:c.state=='connected')
            finally: c.quit();c.thread.join(4)

if __name__=='__main__': unittest.main()

