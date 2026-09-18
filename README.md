# Companion-FifineD6

Мост для подключения FIFINE D6 к Bitfocus Companion.

[Русский — инструкция](README_RU.md) · [English — instructions](README_EN.md)

Windows tray application that connects a FIFINE D6 to Bitfocus Companion over
the Companion Satellite protocol. Buttons and display updates travel through
the bridge; the original FIFINE software should be closed.

**Current version: 0.4.1-rc.1 — release candidate, not a verified stable release.**
Automated protocol and process-lifecycle tests pass locally. Actual Windows tray
interaction and end-to-end operation with D6 + Companion still require testing.
This project is independent of FIFINE and Bitfocus and is not an Elgato emulator.

## Quick start

1. Install Python 3.12+ on Windows and extract this repository to a writable folder.
2. Run `01_install.cmd`.
3. Copy your existing `screen_map.json` and optional `config.json` from the previous
   bridge. For a new device, run `02_calibrate.cmd` instead.
4. Close FIFINE software and any older bridge, then start Companion.
5. Double-click `03_companion.vbs`, or use `03_companion.cmd`.
6. Right-click the D6 icon near the clock: **Включить** (Enable), **Выключить**
   (Disable), **Выход** (Exit).

The default Companion address is `127.0.0.1:16622`, the Satellite TCP service,
not the web interface. Change `config.json` for a different host or port.

See the language-specific guides for calibration, connection setup, troubleshooting,
updates and removal. See [CHANGELOG](CHANGELOG.md), [test report](TEST_REPORT.md)
and [release checklist](RELEASE_CHECKLIST.md) for current verification limits.

## Development

```sh
python -m pip install -r requirements.txt
python -m unittest discover -v
```

CI runs the same suite on Windows and Linux with Python 3.12 and 3.14. Tests use
simulated USB and Companion endpoints; passing CI is not a hardware certification.
The runtime writes rotating `d6_bridge.log` and `d6_tray.log` files locally.
Local settings, logs, captures and virtual environments are excluded from Git.

## License

[MIT](LICENSE). Protocol notes: [PROTOCOL.md](PROTOCOL.md).
Tray implementation uses [pystray](https://pystray.readthedocs.io/en/latest/usage.html).
