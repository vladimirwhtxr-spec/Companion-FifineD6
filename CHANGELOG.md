# Changelog

## 0.4.1-rc.1

- Preserve a Disable request even when Enable follows before the supervisor polls.
- Capture worker startup/import errors in the tray log instead of discarding stderr.
- Make pipe cleanup tolerate a broken pipe after a failed flush.
- Accept UTF-8 BOM in Windows-edited settings and screen maps.
- Close USB when image/status setup or thread startup fails.
- Initialize tray logging before importing optional UI dependencies.
- Add a separate menu item for startup/tray errors.
- Reject Python versions below 3.12 during installation.
- Add regression tests, bilingual guides and CI configuration.

## 0.4

- Windows tray, hidden bridge process, Enable/Disable/Exit and rotating logs.

## 0.3

- Experimental Companion Satellite bridge and D6 screen calibration.
