"""Experimental FIFINE D6 USB / Companion Satellite bridge, v0.4.1-rc.1."""
import argparse
import base64
from collections import OrderedDict
import io
import json
import logging
from pathlib import Path
import queue
import select
import shlex
import socket
import threading
import time
from PIL import Image, ImageDraw, ImageFont
from d6_protocol import VID, PID, PREFIX, command, parse_key

ROOT = Path(__file__).resolve().parent
DEVICE_ID = 'fifine-d6-local'
SIZE = 112


def jpeg_bytes(im):
    im = im.convert('RGB').resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    im = im.transpose(Image.Transpose.ROTATE_180)
    out = io.BytesIO()
    im.save(out, format='JPEG', quality=85, subsampling=0)
    return out.getvalue()


def reports(jpeg, slot):
    if not 1 <= slot <= 15 or not 0 < len(jpeg) <= 65535:
        raise ValueError('Invalid screen slot or JPEG size')
    yield command(PREFIX+b'BAT\0\0'+len(jpeg).to_bytes(2, 'big')+bytes([slot]))
    for n in range(0, len(jpeg), 1024):
        yield command(jpeg[n:n+1024])
    yield command(PREFIX+b'STP')


def label(text, color='#073244'):
    im = Image.new('RGB', (SIZE, SIZE), color)
    d = ImageDraw.Draw(im)
    d.rectangle((3, 3, 108, 108), outline='#32e6a1', width=3)
    d.text((56, 56), str(text), anchor='mm', fill='white', font=ImageFont.load_default(size=38 if len(str(text))<=2 else 17))
    return jpeg_bytes(im)


class D6:
    def __init__(self):
        import hid
        candidates = [d for d in hid.enumerate(VID, PID)
                      if d.get('usage_page') == 0xffa0 and d.get('usage') == 1]
        if len(candidates) != 1:
            raise RuntimeError('Expected exactly one D6 vendor HID collection; found %d' % len(candidates))
        self.handle = hid.device()
        self.handle.open_path(candidates[0]['path'])
        try:
            for c in [PREFIX+b'DIS', PREFIX+b'LIG\0\0\x3c',
                      PREFIX+b'QUCMD\x1f\x11\0\x11\0\x11', PREFIX+b'CLE\0\0\0\xff']:
                self.write(c)
                time.sleep(.025)
        except BaseException:
            self.handle.close()
            raise
        self.last_keepalive = time.monotonic()
        logging.info('D6 opened and initialized')

    def write(self, payload):
        data = b'\0' + command(payload)
        n = self.handle.write(data)
        if n != len(data):
            raise IOError('Incomplete USB write: %d/%d' % (n, len(data)))

    def draw(self, slot, jpeg):
        for report in reports(jpeg, slot):
            self.write(report)
            time.sleep(.002)

    def read(self):
        data = bytes(self.handle.read(512, 5))
        return parse_key(data) if data else None

    def tick(self):
        if time.monotonic() - self.last_keepalive >= 10:
            self.write(PREFIX+b'CONNECT')
            self.last_keepalive = time.monotonic()

    def close(self):
        self.handle.close()


def calibrate():
    device = D6()
    mapping = {}
    used_keys = set()
    try:
        for slot in range(1, 16):
            device.draw(slot, label(slot))
        print('\nThere should be 15 different numbers on D6: 1 through 15.')
        print('Press the D6 button DISPLAYING the requested number, not a PC keyboard key.')
        print('If numbers are missing or overlap, Ctrl+C and send a photo.\n')
        for slot in range(1, 16):
            print('PRESS AND RELEASE the button displaying %d' % slot, flush=True)
            deadline = time.monotonic()+120
            pressed = None
            while time.monotonic() < deadline:
                device.tick()
                event = device.read()
                if not event:
                    continue
                key, down = event
                if down:
                    if key in used_keys:
                        print('That physical button was already assigned. Press number %d.' % slot, flush=True)
                        pressed = None
                    else:
                        pressed = key
                elif key == pressed:
                    mapping[str(key)] = slot
                    used_keys.add(key)
                    logging.info('Calibration: physical key %d -> screen slot %d', key, slot)
                    break
            else:
                raise TimeoutError('Calibration timed out; previous mapping was not changed')
        validate_mapping(mapping)
        for key in range(1, 16):
            device.draw(mapping[str(key)], label(key, '#164333'))
        print('\nThe screen should now read:\n1 2 3 4 5\n6 7 8 9 10\n11 12 13 14 15')
        print('Top to bottom, left to right. Type YES on the PC keyboard to save.')
        if input('Confirm: ').strip().upper() != 'YES':
            raise RuntimeError('Calibration not confirmed; previous mapping unchanged')
        dest = ROOT/'screen_map.json'
        tmp = dest.with_suffix('.tmp')
        tmp.write_text(json.dumps(mapping, indent=2), encoding='utf-8')
        tmp.replace(dest)
        logging.info('Saved screen_map.json. Start 03_companion.cmd next.')
    finally:
        device.close()


def validate_mapping(m):
    if set(m) != {str(i) for i in range(1, 16)} or any(type(v) is not int for v in m.values()) or set(m.values()) != set(range(1, 16)):
        raise ValueError('screen_map.json must map every physical key 1..15 to a unique screen slot 1..15')


class USBWorker(threading.Thread):
    def __init__(self, device, mapping):
        super().__init__(daemon=True)
        self.device, self.mapping = device, mapping
        self.lock = threading.Lock()
        self.frames = OrderedDict()
        self.events = queue.Queue(maxsize=256)
        self.stop_event = threading.Event()
        self.error = None
        self.generation = 0

    def frame(self, key, jpeg):
        with self.lock:
            self.frames[key] = (self.generation, jpeg)

    def status(self, text):
        pic = label(text, '#48252b')
        with self.lock:
            self.generation += 1
            self.frames.clear()
            for key in range(1, 16):
                self.frames[key] = (self.generation, pic)

    def run(self):
        try:
            while not self.stop_event.is_set():
                event = self.device.read()
                if event:
                    self.events.put_nowait(event)
                self.device.tick()
                with self.lock:
                    item = self.frames.popitem(last=False) if self.frames else None
                if item:
                    key, (generation, jpeg) = item
                    # One complete image at a time: USB packet sequences never interleave.
                    self.device.draw(self.mapping[str(key)], jpeg)
        except Exception as e:
            self.error = e
            logging.exception('USB worker stopped')
            self.stop_event.set()
        finally:
            self.device.close()


def parse_line(line):
    parts = shlex.split(line)
    if not parts:
        return '', {}, []
    fields = dict(p.split('=', 1) for p in parts[1:] if '=' in p)
    return parts[0], fields, parts[1:]


def control_key(cid):
    row, col = map(int, cid.split('/'))
    if not 0 <= row < 3 or not 0 <= col < 5:
        raise ValueError('Control outside 3x5 grid')
    return row*5+col+1


def registration():
    manifest = {'stylePresets': {'default': {'bitmap': {'w':SIZE, 'h':SIZE}}},
                'controls': {f'{r}/{c}': {'row':r, 'column':c} for r in range(3) for c in range(5)}}
    encoded = base64.b64encode(json.dumps(manifest,separators=(',',':')).encode()).decode()
    return f'ADD-DEVICE DEVICEID={DEVICE_ID} PRODUCT_NAME="FIFINE D6 Bridge" BRIGHTNESS=0 LAYOUT_MANIFEST={encoded}'


class Session:
    def __init__(self, sock, usb):
        self.sock, self.usb = sock, usb
        self.ready = False
        self.registered = False
        self.down = set()
        self.image_count = 0

    def send(self, line):
        self.sock.sendall((line+'\n').encode('utf-8'))

    def key(self, key, down):
        if not self.ready:
            return  # Do not replay presses made while disconnected.
        if down and key in self.down or not down and key not in self.down:
            return
        r,c = divmod(key-1,5)
        self.send(f'KEY-PRESS DEVICEID={DEVICE_ID} CONTROLID="{r}/{c}" PRESSED={int(down)}')
        if down:
            self.down.add(key)
        else:
            self.down.discard(key)
        logging.info('KEY %02d %s -> Companion', key, 'DOWN' if down else 'UP')

    def line(self, line):
        if line.startswith('PING'):
            self.send('PONG'+line[4:])
            return
        cmd, fields, rest = parse_line(line)
        if cmd == 'BEGIN':
            logging.info('Companion greeting: %s',line)
            version = tuple(int(v) for v in fields.get('ApiVersion','0.0.0').split('-')[0].split('.')[:2])
            if version < (1,9):
                raise RuntimeError('Satellite API 1.9+ required')
            self.send(registration())
            self.registered = True
        elif cmd == 'ERROR' or 'ERROR' in rest:
            raise RuntimeError('Companion: '+line[:500])
        elif cmd == 'ADD-DEVICE' and 'OK' in rest:
            while True:
                try:self.usb.events.get_nowait()
                except queue.Empty:break
            self.ready = True
            logging.info('Surface registered. Open Companion > Surfaces.')
        elif cmd == 'KEY-STATE' and fields.get('DEVICEID') == DEVICE_ID:
            cid = fields.get('CONTROLID')
            bitmap = fields.get('BITMAP')
            if cid is None or bitmap is None:
                return
            key = control_key(cid)
            raw = base64.b64decode(bitmap,validate=True)
            if len(raw) != SIZE*SIZE*3:
                raise ValueError('Unexpected RGB bitmap length: %d' % len(raw))
            pic = jpeg_bytes(Image.frombytes('RGB',(SIZE,SIZE),raw))
            self.usb.frame(key,pic)
            self.image_count += 1
            if self.image_count <= 15 or self.image_count % 100 == 0:
                logging.info('Bitmap %s -> key %d (update %d)',cid,key,self.image_count)
        elif cmd == 'KEYS-CLEAR' and fields.get('DEVICEID') == DEVICE_ID:
            pic = jpeg_bytes(Image.new('RGB',(SIZE,SIZE),'black'))
            for key in range(1,16):self.usb.frame(key,pic)

    def close(self):
        try:
            for key in list(self.down):self.key(key,False)
            if self.registered:self.send(f'REMOVE-DEVICE DEVICEID={DEVICE_ID}')
        except OSError:
            pass


def connected(sock, usb, on_status=lambda state: None):
    session = Session(sock,usb)
    buffer = bytearray()
    ping = time.monotonic()
    last_rx = time.monotonic()
    started = last_rx
    try:
        while not usb.stop_event.is_set():
            now = time.monotonic()
            if now-last_rx>15:
                raise TimeoutError('No response from Companion for 15 seconds')
            if not session.ready and now-started>10:
                raise TimeoutError('Companion surface registration timed out')
            if now-ping>=2:
                session.send('PING d6')
                ping=now
            if select.select([sock],[],[],.01)[0]:
                chunk=sock.recv(65536)
                if not chunk:raise ConnectionError('Companion disconnected')
                last_rx=time.monotonic()
                buffer.extend(chunk)
                if len(buffer)>4*1024*1024:raise ValueError('Satellite message exceeds size limit')
                while b'\n' in buffer:
                    line,_,tail=buffer.partition(b'\n');buffer=bytearray(tail)
                    was_ready = session.ready
                    session.line(line.decode('utf-8').rstrip('\r'))
                    if session.ready and not was_ready: on_status('connected')
            for _ in range(64):
                try:event=usb.events.get_nowait()
                except queue.Empty:break
                session.key(*event)
        if usb.error:raise RuntimeError('USB stopped') from usb.error
    finally:
        session.close()


def bridge(stop_event=None, on_status=lambda state: None):
    stop_event = stop_event or threading.Event()
    if stop_event.is_set(): return
    m=json.loads((ROOT/'screen_map.json').read_text(encoding='utf-8-sig'))
    validate_mapping(m)
    config_path = ROOT/'config.json'
    if not config_path.exists():
        config_path = ROOT/'config.example.json'
    cfg=json.loads(config_path.read_text(encoding='utf-8-sig'))
    host,port=cfg['host'],int(cfg['port'])
    if not isinstance(host,str) or not 1<=port<=65535:raise ValueError('Invalid host/port')
    usb=USBWorker(D6(),m)
    usb.stop_event=stop_event
    try:
        usb.status('WAIT');usb.start()
    except BaseException:
        usb.device.close()
        raise
    try:
        while not usb.stop_event.is_set():
            try:
                on_status('connecting')
                logging.info('Connecting to Companion %s:%d',host,port)
                with socket.create_connection((host,port),timeout=3) as sock:
                    sock.settimeout(2)
                    connected(sock,usb,on_status)
            except (OSError,ValueError,RuntimeError) as e:
                logging.warning('Connection interrupted: %s',e)
                if usb.stop_event.is_set():break
                on_status('offline')
                usb.status('OFFLINE')
                # Drain offline key events while waiting. Never execute them later.
                until=time.monotonic()+3
                while time.monotonic()<until and not usb.stop_event.is_set():
                    try:usb.events.get(timeout=.05)
                    except queue.Empty:pass
        if usb.error:raise RuntimeError('USB error; reconnect D6 and restart bridge') from usb.error
    finally:
        usb.stop_event.set();usb.join(timeout=3)
        if usb.is_alive():logging.warning('USB worker did not finish; close window and reconnect device')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['calibrate','bridge'])
    args=parser.parse_args()
    logfile=ROOT/f'd6_{args.mode}_{time.strftime("%Y%m%d_%H%M%S")}.log'
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.StreamHandler(),logging.FileHandler(logfile,encoding='utf-8')])
    logging.info('D6 Bridge v0.4.1-rc.1; mode=%s',args.mode)
    try:
        if args.mode=='calibrate':calibrate()
        else:bridge()
    except KeyboardInterrupt:logging.info('Stopped by user')
    except Exception:
        logging.exception('FAILED. Send this log for diagnosis.')
        return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
