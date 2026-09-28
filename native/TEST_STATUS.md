# Validation 0.2

Target application supplied by the user: Stream Deck 7.6.0, Windows 11.

Passed locally on Linux:
- 7 Python tests (image reassembly, malformed packets, key state, transforms,
  D6 framing, fill commands and invalid feature handling).
- C identity-response test compiled with cc -std=c11 -Wall -Wextra -Werror.
  This compiles the actual portable header used by the driver, not the driver itself.

NOT run: WDK driver compilation, signing, driver installation, VHF enumeration,
Windows tray, Stream Deck 7.6.0 recognition, real hardware exchange.

This is source-level progress, not a working native-device release.
