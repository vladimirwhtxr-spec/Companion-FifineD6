"""Console helper; the tray starts --worker with redirected pipes."""
import sys
import traceback

def self_test():
    import hid
    from PIL import Image
    from d6_bridge import jpeg_bytes, reports, registration
    from d6_protocol import VID, PID
    jpeg = jpeg_bytes(Image.new('RGB', (112,112), 'red'))
    assert len(list(reports(jpeg,1))) >= 3
    assert 'LAYOUT_MANIFEST=' in registration()
    hid.enumerate(VID,PID)
    print('PASS: bundled HID, JPEG and Satellite protocol; no hardware test')

def main():
    if '--worker' in sys.argv:
        from d6_worker import main as worker
        return worker()
    if '--self-test' in sys.argv:
        self_test()
        return 0
    print('D6 Companion Bridge - Windows x64\n1 - Calibrate D6 screens\n2 - Check bundled components\n0 - Exit')
    choice=input('Select: ').strip()
    if choice=='0': return 0
    try:
        if choice=='1':
            print('Close D6Companion (Exit in tray), FIFINE software and other D6 bridges first.')
            input('Press Enter when ready...')
            from d6_bridge import calibrate
            calibrate()
        elif choice=='2': self_test()
    except Exception:
        traceback.print_exc()
        input('Press Enter to close...')
        return 1
    input('Press Enter to close...')
    return 0

if __name__=='__main__': raise SystemExit(main())
