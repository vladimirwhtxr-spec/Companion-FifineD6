# D6 Companion Bridge — Windows x64

FIFINE AmpliGame D6 to Bitfocus Companion 5.0.5 using Satellite API 1.9+.
Python is bundled. Elgato Stream Deck and the D6VirtualDeck driver are not used.

## Setup

1. Extract the complete ZIP to a writable folder. Keep both EXE files together.
2. Close FIFINE software and any other D6 bridge; connect D6 over USB.
3. Copy your existing working Companion bridge `screen_map.json` beside the EXEs. Otherwise run `D6Tools.exe`, choose `1`, and press/release each D6 button displaying the requested number. Confirm the final 3×5 grid by typing `YES` on your PC. Abort if numbers overlap or are missing.
4. Start Companion and enable its Satellite listener on TCP 16622. Default destination: `127.0.0.1:16622`. For another address or port, copy `config.example.json` to `config.json`, edit `host`/`port`, then disable/enable the bridge.
5. Run `D6Companion.exe`; look for D6 in the Windows notification area or hidden icons. If a screen map exists, the bridge starts automatically.
6. Configure `FIFINE D6 Bridge` under Companion Surfaces.

## Tray menu (Russian labels)

- **Включить** — Enable/retry.
- **Выключить** — Disable and release USB, keeping the tray app open.
- **Открыть журнал** — Open bridge log.
- **Журнал запуска и трея** — Open launcher/tray log.
- **Открыть папку** — Open settings/log folder.
- **Выход** — Stop the worker and exit the app completely.

Green: registered with Companion; yellow: connecting/offline; grey: disabled; red: error.
A second tray instance is blocked. Exit the tray before calibration; do not run multiple calibration processes.
TCP reconnection is automatic. Offline button presses are not replayed. After USB failure, reconnect D6 and select Enable.

`D6Tools.exe`, option `2`, or `D6Tools.exe --self-test` checks bundled components only.
Settings and logs are stored beside the EXEs: `screen_map.json`, `config.json`, `d6_bridge.log`, `d6_tray.log`. Preserve these when updating.
Administrator privileges are not required. Windows startup is not changed automatically.

## Validation limits

This is a hardware-validation build, not a broadcast-qualified stable release. Automated tests cover protocol and process start/stop/restart, including simulated USB cleanup. Windows CI also launches both packaged EXEs. No physical D6 is available in CI; actual button/image operation and long-running Companion 5.0.5 compatibility still need hardware testing. EXEs are unsigned.
Source/build: branch `build/companion-exe-20260928` at https://github.com/vladimirwhtxr-spec/Companion-FifineD6.
