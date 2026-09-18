# FIFINE D6 → Companion: English guide

[Русский](README_RU.md) · [Project overview](README.md)

Version **0.4.1-rc.1**, a release candidate. Windows tray and physical device testing
remain outstanding. No custom driver, firmware change or Elgato software is needed.

## Requirements

- Windows with Python 3.12 or newer. The installer uses the Python launcher (`py`),
  falling back to `python`. It rejects an older virtual environment.
- FIFINE D6, USB VID `3142`, PID `0060`.
- Bitfocus Companion with Satellite API 1.9+. Development targets the user's
  Companion 5.0.5 setup; compatibility with all versions is not established.
- A writable extracted project folder and internet access for initial dependencies.

## Installation and upgrade

1. Close the previous bridge and the FIFINE application.
2. Download the repository via **Code → Download ZIP** and extract it fully.
3. Run `01_install.cmd`. Dependencies are installed in the local `.venv`.
4. When upgrading, copy **only your `screen_map.json` and optional `config.json`**
   into the new folder. Do not copy the old `.venv` or overwrite your settings with
   someone else's map. No recalibration is needed for a previously verified map.
5. For a first installation, run `02_calibrate.cmd` as described below.
6. Start Companion and double-click `03_companion.vbs` for a launch without a
   console window. `03_companion.cmd` is an alternative whose launch window closes.
   If Windows disables VBScript, use the CMD launcher.

No administrator privileges or Windows startup entry are required. Keep the folder
in a stable location; the launchers and settings are relative to that folder.

## Calibration

The input key order and screen address order are different. Do not guess the map.
Only screen address 5 → bottom-right physical button (input 15) was individually
confirmed before full calibration support was added.

Run `02_calibrate.cmd`. The deck should display numbers 1–15. For each prompt,
press **and release the D6 button displaying that number**, not a PC keyboard key.
If numbers are missing or overlap, press Ctrl+C and retain the previous map.
After all buttons are assigned, verify that labels read 1–5, 6–10, 11–15 from
left to right, top to bottom. Type `YES` on the PC to save `screen_map.json`.

## Companion connection

The default is localhost TCP port 16622. Ensure Companion's Satellite service is
enabled/listening. This is separate from the Companion web UI port.

For another PC/address, copy `config.example.json` to `config.json`:

```json
{"host": "127.0.0.1", "port": 16622}
```

Use the Companion computer's address for `host` and permit this TCP connection
through its firewall as needed. The bridge does not supply transport encryption
or authentication; use a trusted network. Disable and enable the bridge after
changing settings. Open **Companion → Surfaces**, find **FIFINE D6 Bridge**, and
configure its page assignment and buttons. A green icon means registration was
acknowledged; verify an actual button action and image update as well.

## Tray controls

The menu labels are currently Russian. Right-click D6 near the clock; check the
hidden-icons arrow if it is not visible.

| Menu | Meaning |
| --- | --- |
| Включить | Enable: open D6 and connect to Companion |
| Выключить | Disable: release held keys, unregister, close USB and TCP; keep tray |
| Выход | Exit: stop the bridge and remove the tray icon |
| Открыть журнал | Open the bridge log |
| Журнал запуска и трея | Open startup/tray errors |
| Открыть папку | Open the project folder |

Green = registered; yellow = starting/connecting/offline/stopping; grey = disabled;
red = error. The bridge enables automatically whenever the tray program starts.
Only one tray instance per Windows session is allowed. This does not prevent a
separate old console bridge or FIFINE application from opening the device.

## Troubleshooting

- **Red icon:** open both logs. Missing `screen_map.json` requires calibration;
  missing modules require rerunning `01_install.cmd`.
- **Companion unavailable:** verify Satellite host/port and firewall. Connection
  retries are automatic. Offline key events are discarded, never replayed later.
- **USB unplugged:** reconnect D6, close competing software and click Enable again.
- **Old image remains after Disable:** display contents can persist after the
  device handle closes. This does not mean the script is still running.
- **Stop takes time:** allow up to eight seconds for graceful shutdown. A hung
  worker is then terminated; key-release delivery cannot be guaranteed in this case.
- **JSON editing:** UTF-8 with or without a BOM is supported; keep valid JSON.

Logs rotate: bridge 2 MB with three backups, tray 1 MB with two backups. Review
logs before sharing: they may include your Companion address or local file paths.

## Removal and validation

Choose Exit, then delete the extracted folder. There is no system service, custom
driver or automatic startup registration to uninstall.

Run `.venv\Scripts\python.exe -m unittest discover -v` for automated tests. Before
calling this release stable, complete [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)
on Windows with the actual D6. See [TEST_REPORT.md](TEST_REPORT.md) for what was
and was not tested.
