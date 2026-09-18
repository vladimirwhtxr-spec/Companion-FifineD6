import base64
import io
import json
import queue
import socket
import threading
import time
import unittest
from PIL import Image
import d6_bridge as b

class FakeUSB:
    def __init__(self):
        self.events=queue.Queue();self.stop_event=threading.Event();self.error=None;self.frames={}
    def frame(self,key,jpeg):self.frames[key]=jpeg

class BridgeTest(unittest.TestCase):
    def test_mapping_and_image(self):
        b.validate_mapping({str(i):16-i for i in range(1,16)})
        with self.assertRaises(ValueError):b.validate_mapping({str(i):5 for i in range(1,16)})
        im=Image.new('RGB',(112,112),'black')
        for x in range(56):
            for y in range(56):im.putpixel((x,y),(255,0,0))
        jpeg=b.jpeg_bytes(im);decoded=Image.open(io.BytesIO(jpeg))
        self.assertGreater(decoded.getpixel((95,95))[0],240)
        self.assertLess(decoded.getpixel((15,15))[0],10)
        frames=list(b.reports(jpeg,5))
        self.assertEqual(frames[0][12],5)
        self.assertEqual(int.from_bytes(frames[0][10:12],'big'),len(jpeg))
        self.assertEqual(b''.join(frames[1:-1])[:len(jpeg)],jpeg)

    def test_socket_session(self):
        client,server=socket.socketpair();client.settimeout(1);server.settimeout(2)
        usb=FakeUSB();errors=[]
        def run():
            try:b.connected(client,usb)
            except Exception as e:errors.append(e)
        thread=threading.Thread(target=run);thread.start()
        reader=server.makefile('rb')
        try:
            # Split greeting across TCP reads; remaining messages are coalesced.
            server.sendall(b'BEGIN CompanionVersion=5.0.5 ApiVer')
            time.sleep(.02)
            server.sendall(b'sion=1.12.0\nCAPS BITMAP_FORMATS=rgb,png\n')
            reg=reader.readline().decode();cmd,f,_=b.parse_line(reg)
            self.assertEqual(cmd,'ADD-DEVICE')
            manifest=json.loads(base64.b64decode(f['LAYOUT_MANIFEST']))
            self.assertEqual(len(manifest['controls']),15)
            self.assertEqual(manifest['controls']['2/4']['column'],4)
            raw=bytes([17,90,150])*(112*112)
            bmp=base64.b64encode(raw).decode()
            reply=('ADD-DEVICE OK\nPING verify\n'+f'KEY-STATE DEVICEID={b.DEVICE_ID} CONTROLID="2/4" BITMAP={bmp}\n').encode()
            server.sendall(reply[:100]);server.sendall(reply[100:])
            self.assertEqual(reader.readline().decode().strip(),'PONG verify')
            deadline=time.monotonic()+2
            while 15 not in usb.frames and time.monotonic()<deadline:time.sleep(.01)
            self.assertIn(15,usb.frames)
            usb.events.put((15,True));usb.events.put((15,False))
            lines=[reader.readline().decode().strip() for _ in range(2)]
            self.assertTrue(lines[0].endswith('CONTROLID="2/4" PRESSED=1'))
            self.assertTrue(lines[1].endswith('CONTROLID="2/4" PRESSED=0'))
            # Simulate a held key when the bridge is stopped: explicit release required.
            usb.events.put((1,True));self.assertIn('PRESSED=1',reader.readline().decode())
            usb.stop_event.set()
            self.assertIn('PRESSED=0',reader.readline().decode())
            self.assertIn('REMOVE-DEVICE',reader.readline().decode())
        finally:
            usb.stop_event.set();thread.join(3);reader.close();client.close();server.close()
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])

    def test_bad_bitmap_and_api(self):
        class Sink:
            def sendall(self,data):pass
        s=b.Session(Sink(),FakeUSB())
        with self.assertRaises(RuntimeError):s.line('BEGIN ApiVersion=1.8.0')
        with self.assertRaises(ValueError):s.line(f'KEY-STATE DEVICEID={b.DEVICE_ID} CONTROLID="0/0" BITMAP=YWJj')
        with self.assertRaises(ValueError):b.control_key('3/0')
        # Before registration, button presses are discarded.
        s.key(1,True);self.assertEqual(s.down,set())

if __name__=='__main__':unittest.main()
