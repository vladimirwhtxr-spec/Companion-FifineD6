"""Minimal D6 USB framing derived from device captures."""
VID, PID = 0x3142, 0x0060
PREFIX = b"CRT\0\0"

def command(payload):
    if len(payload) > 1024:
        raise ValueError('Output report exceeds 1024 bytes')
    return payload.ljust(1024, b'\0')

def parse_key(report):
    # HIDAPI normally strips the zero report-ID on input; tolerate it if present.
    if report.startswith(b'\0ACK'):
        report = report[1:]
    if len(report) >= 11 and report[:9] == b'ACK\0\0OK\0\0':
        key, down = report[9:11]
        if 1 <= key <= 15 and down in (0, 1):
            return key, bool(down)
    return None
