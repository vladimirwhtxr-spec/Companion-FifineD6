import sys
"""D6 transport reused from the experimental Companion bridge."""
from collections import OrderedDict
import io
import json
import logging
from pathlib import Path
import queue
import threading
import time
from PIL import Image, ImageDraw, ImageFont
from d6_protocol import VID, PID, PREFIX, command, parse_key

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
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
        print('Saved screen_map.json. Run native_bridge.py after virtual-device setup.')
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


if __name__ == "__main__":
    calibrate()
