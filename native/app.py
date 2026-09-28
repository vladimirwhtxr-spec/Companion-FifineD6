"""Packaged native Stream Deck research bridge, Windows console launcher."""
import sys
import traceback

def self_test():
    import io
    import hid
    from PIL import Image
    from streamdeck_protocol import key_report, to_d6
    assert len(key_report([False]*15)) == 19
    out=io.BytesIO()
    Image.new('RGB',(72,72),'red').save(out,format='JPEG')
    assert Image.open(io.BytesIO(to_d6(out.getvalue()))).size == (112,112)
    assert callable(hid.enumerate)
    # Load Windows HID backend; no writes or driver installation.
    hid.enumerate(0x3142,0x0060)
    print('PASS: bundled Python, HID backend, Pillow/JPEG and protocol imports')

def main():
    if '--self-test' in sys.argv:
        self_test()
        return
    if len(sys.argv)>1:
        if sys.argv[1]=='--calibrate':
            from d6_usb import calibrate
            calibrate()
        else:
            from native_bridge import main as bridge
            bridge()
        return
    print('D6 Native Stream Deck Bridge - experimental 0.2')
    print('Target: Elgato Stream Deck 7.6.0. Compatibility NOT yet verified.')
    print('Recognition needs the separately built/signed D6VirtualDeck driver.')
    print('This EXE does not install a driver or modify Windows security settings.')
    print('\n1 - Probe virtual driver (90 seconds; no physical D6 required)')
    print('2 - Calibrate D6 screen mapping')
    print('3 - Start bridge (requires driver and screen_map.json)')
    print('4 - Check bundled components only')
    print('0 - Exit')
    choice=input('Select: ').strip()
    if choice=='0': return
    try:
        if choice=='1':
            sys.argv=[sys.argv[0],'--probe','--seconds','90']
            from native_bridge import main as bridge
            bridge()
        elif choice=='2':
            from d6_usb import calibrate
            calibrate()
        elif choice=='3':
            from native_bridge import main as bridge
            bridge()
        elif choice=='4': self_test()
        else: print('Unknown selection')
    except KeyboardInterrupt: print('\nStopped')
    except Exception:
        traceback.print_exc()
        print('\nIf D6VirtualDeck cannot be opened: the signed virtual driver must be installed first.')
    input('\nPress Enter to close...')

if __name__=='__main__': main()
