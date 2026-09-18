# D6 protocol observations

These are observations from user-provided USB captures and limited device testing,
not a manufacturer specification. Raw captures and device serial numbers are not
part of this repository.

## Transport

- VID `0x3142`, PID `0x0060`.
- Vendor collection: usage page `0xFFA0`, usage `0x0001`.
- HID input payload: 512 bytes; output payload: 1024 bytes.
- The descriptor has no numbered reports. HIDAPI writes prepend a zero report ID;
  this leading byte is not part of the captured output payload.
- Captured interrupt endpoints: input `0x82`, output `0x03`.

## Key events

Input reports start with `ACK\0\0OK\0\0`, followed by a key byte and a state byte.
Keys 1–15 were captured in row-major physical order, left to right, top to bottom.
State 1 means pressed; state 0 means released. Remaining bytes are padding.

## Output commands

Output payloads start with `CRT\0\0` and are zero-padded to 1024 bytes.
The implementation uses the observed `DIS`, `LIG`, `QUCMD`, `CLE`, and `CONNECT`
sequences from startup. The names should not be treated as proven semantics.
In particular, `CONNECT` is sent periodically as a presumed keepalive.

## Images

The observed header begins `CRT\0\0BAT\0\0`:

| Byte offset | Interpretation |
| --- | --- |
| 10–11 | JPEG byte length, big endian |
| 12 | Screen address |
| 13–1023 | Zero padding in observed transfers |

The header is followed by JPEG data in 1024-byte payloads. The final data payload
is zero-padded. A padded `CRT\0\0STP` command completes the transfer.

Observed JPEG dimensions are 112 × 112. Images require a 180° pre-rotation on the
tested device. Screen address 5 is the physical bottom-right key (key event 15).
Screen addresses must not be equated with input key codes. Addresses 1–15 are
candidates used by calibration; the complete mapping has not yet been confirmed.

## Next validation steps

1. Complete all-screen calibration and record the physical key/address mapping.
2. Connect to a real Companion instance and check all image/input positions.
3. Check feedback changes initiated from outside the D6, page changes, held keys,
   server restart, and a sustained session.
4. Diagnose the isolated missing release observed in a prototype log.
