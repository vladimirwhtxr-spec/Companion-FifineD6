"""Windows bridge for the accompanying experimental VHF driver."""
import argparse
import ctypes
from ctypes import wintypes as w
import json
import logging
from pathlib import Path
import queue
import struct
import sys
import time
from streamdeck_protocol import ImageAssembler, key_report, to_d6, feature_frames

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
EVENT = struct.Struct('<II1024s')


def ioctl_code(function, access):
    return (0x22 << 16) | (access << 14) | (function << 2)


class Driver:
    def __init__(self):
        if sys.platform != 'win32':
            raise RuntimeError('The VHF bridge requires Windows')
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.k.CreateFileW.argtypes = [w.LPCWSTR,w.DWORD,w.DWORD,w.LPVOID,w.DWORD,w.DWORD,w.HANDLE]
        self.k.CreateFileW.restype = w.HANDLE
        self.k.DeviceIoControl.argtypes = [w.HANDLE,w.DWORD,w.LPVOID,w.DWORD,w.LPVOID,w.DWORD,ctypes.POINTER(w.DWORD),w.LPVOID]
        self.k.DeviceIoControl.restype = w.BOOL
        self.k.CloseHandle.argtypes = [w.HANDLE]
        self.k.CloseHandle.restype = w.BOOL
        self.h = self.k.CreateFileW(r'\\.\D6VirtualDeck',0xc0000000,0,None,3,0,None)
        if self.h == w.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())

    def call(self, code, data=b'', size=0):
        src = ctypes.create_string_buffer(data) if data else None
        dst = ctypes.create_string_buffer(size) if size else None
        got = w.DWORD()
        if not self.k.DeviceIoControl(self.h,code,src,len(data),dst,size,ctypes.byref(got),None):
            raise ctypes.WinError(ctypes.get_last_error())
        return dst.raw[:got.value] if dst else b''

    def keys(self, states):
        self.call(ioctl_code(0x800,2),key_report(states))

    def poll(self):
        raw = self.call(ioctl_code(0x801,1),size=EVENT.size*16)
        if len(raw)%EVENT.size:
            raise RuntimeError('Driver returned invalid event framing')
        events = []
        for kind,length,data in EVENT.iter_unpack(raw):
            if not 1 <= length <= 1024:
                raise RuntimeError('Invalid driver event length')
            events.append((kind,data[:length]))
        return events

    def stats(self):
        raw=self.call(ioctl_code(0x802,1),size=16)
        if len(raw)!=16:
            raise RuntimeError('Invalid driver statistics')
        version,queued,dropped,_=struct.unpack('<IIII',raw)
        if version!=1:
            raise RuntimeError('Unsupported driver ABI')
        return {'version':version,'queued':queued,'dropped':dropped}

    def close(self):
        self.k.CloseHandle(self.h)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--probe',action='store_true',help='Observe virtual HID traffic without opening D6')
    parser.add_argument('--seconds',type=float,default=0,help='0 = run until Ctrl+C')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.StreamHandler(),logging.FileHandler(ROOT/'native_bridge.log',encoding='utf-8')])
    driver=None
    usb=None
    states=[0]*15
    assembler=ImageAssembler()
    try:
        driver=Driver()
        logging.info('Driver connected; %s',driver.stats())
        driver.keys(states)
        if not args.probe:
            from d6_usb import D6, USBWorker, validate_mapping
            mapping=json.loads((ROOT/'screen_map.json').read_text(encoding='utf-8-sig'))
            validate_mapping(mapping)
            usb=USBWorker(D6(),mapping)
            usb.start()
        start=time.monotonic()
        last_stats=start
        logged_unknown=set()
        while not args.seconds or time.monotonic()-start < args.seconds:
            if usb:
                if usb.error:
                    raise RuntimeError('D6 disconnected or USB worker failed') from usb.error
                for _ in range(256):
                    try: key,down=usb.events.get_nowait()
                    except queue.Empty: break
                    states[key-1]=int(down)
                    driver.keys(states)
            for kind,data in driver.poll():
                if kind==1 and data[:2]==b'\x02\x07':
                    try:
                        image=assembler.feed(data)
                        if image:
                            key,jpeg=image
                            converted=to_d6(jpeg)
                            if usb: usb.frame(key,converted)
                            logging.info('Image key=%d bytes=%d',key,len(jpeg))
                    except (ValueError,OSError) as e:
                        logging.warning('Image rejected: %s',e)
                elif kind==1 and data==b'\x02'+bytes(1023):
                    assembler.pending.clear()
                    logging.info('Image stream reset')
                else:
                    # Only the prefix is retained; no raw images or device serials.
                    tag=(kind,data[:12].hex(),len(data))
                    if tag not in logged_unknown:
                        logging.info('HID kind=%d prefix=%s length=%d',*tag)
                        if len(logged_unknown)<512: logged_unknown.add(tag)
                    if kind==2:
                        try:
                            frames=feature_frames(data)
                            if frames:
                                assembler.pending.clear()
                                for key,jpeg in frames:
                                    if usb: usb.frame(key,jpeg)
                        except ValueError as e:
                            logging.warning('Feature rejected: %s',e)
                    # Brightness is intentionally logged only: D6 range unverified.
            if time.monotonic()-last_stats>=2:
                stats=driver.stats()
                if stats['dropped']:
                    raise RuntimeError('HID queue overflow; restart app/bridge: %s'%stats)
                last_stats=time.monotonic()
            time.sleep(.002)
    finally:
        try:
            if driver:
                try: driver.keys([0]*15)
                finally: driver.close()
        finally:
            if usb:
                usb.stop_event.set()
                usb.join(timeout=3)


if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: pass
    except Exception:
        logging.exception('Bridge stopped')
        sys.exit(1)
