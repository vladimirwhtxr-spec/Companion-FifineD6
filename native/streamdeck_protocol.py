"""Original V2 protocol subset. Hardware discovery is NOT implemented here."""
import io
import time
from PIL import Image


class ImageAssembler:
    """Bounded per-key reassembly; no partially received image is displayed."""
    def __init__(self):
        self.pending = {}

    def feed(self, report):
        now = time.monotonic()
        self.pending = {k: v for k, v in self.pending.items() if now-v[2] < 2}
        if len(report) != 1024 or report[:2] != b'\x02\x07':
            raise ValueError('Unsupported output report')
        key, final = report[2:4]
        length = int.from_bytes(report[4:6], 'little')
        page = int.from_bytes(report[6:8], 'little')
        if key >= 15 or final not in (0, 1) or not 1 <= length <= 1016:
            self.pending.pop(key, None)
            raise ValueError('Invalid image header')
        if page == 0:
            self.pending[key] = (0, bytearray(), now)
        expected, data, _ = self.pending.get(key, (-1, bytearray(), now))
        if page != expected or len(data)+length > 65535:
            self.pending.pop(key, None)
            raise ValueError('Out-of-order or oversized image')
        data.extend(report[8:8+length])
        if final:
            self.pending.pop(key, None)
            if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
                raise ValueError('Incomplete JPEG')
            return key+1, bytes(data)
        self.pending[key] = (page+1, data, now)
        return None


def to_d6(jpeg):
    # Elgato Original V2 expects both-axis-flipped JPEGs; undo its transform.
    # jpeg_bytes then applies the separately verified D6 180-degree transform.
    from d6_usb import jpeg_bytes
    with Image.open(io.BytesIO(jpeg)) as im:
        if im.format != 'JPEG' or im.size != (72, 72):
            raise ValueError('Expected a 72x72 Original V2 JPEG')
        im.load()
        return jpeg_bytes(im.transpose(Image.Transpose.ROTATE_180))


def key_report(states):
    if len(states) != 15 or any(s not in (0, 1, False, True) for s in states):
        raise ValueError('Expected 15 boolean key states')
    return bytes([1, 0, 15, 0, *states])


def feature_frames(report):
    """Translate documented fill commands. Show-logo uses a black placeholder."""
    from d6_usb import jpeg_bytes
    if len(report) != 32 or report[0] != 3:
        raise ValueError('Expected 32-byte setter feature report')
    command = report[1]
    if command == 2:
        keys, color = range(1,16), (0,0,0)
    elif command == 5:
        keys, color = range(1,16), tuple(report[2:5])
    elif command == 6:
        if report[2] >= 15:
            raise ValueError('Invalid fill key index')
        keys, color = [report[2]+1], tuple(report[3:6])
    elif command == 8:
        if report[2] > 100:
            raise ValueError('Invalid brightness')
        return []  # Real D6 brightness scale still needs hardware validation.
    else:
        raise ValueError('Unsupported setter command')
    jpeg = jpeg_bytes(Image.new('RGB',(112,112),color))
    return [(key,jpeg) for key in keys]
