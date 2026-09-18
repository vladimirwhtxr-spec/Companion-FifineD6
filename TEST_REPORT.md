# Debug report / Отчёт об отладке

Candidate: 0.4.1-rc.1. Local test environment: Linux, Python 3.12.

**10 automated tests passed locally.** They cover image orientation/framing,
invalid bitmaps/API versions, a simulated Companion TCP session, key release and
surface removal, USB close on cancellation, normal restart/exit, a stuck child,
retry after failure, rapid Disable/Enable, captured import failures and cleanup
after a worker-thread start failure. BOM configuration is exercised by the
cancellation integration test. Real child processes are used for lifecycle tests.

Confirmed defects fixed: rapid Disable/Enable skipped shutdown; child stderr was
discarded; Windows UTF-8 BOM files failed JSON decoding; USB could remain open if
worker setup/start raised before entering the cleanup block. Defensive fixes:
broken-pipe cleanup and early tray logging. See CHANGELOG.md for supporting changes.

**Not verified:** Windows tray rendering/menu clicks, Windows mutex behavior,
USB unplug/replug with physical D6, sustained HID traffic, or end-to-end control
of Companion 5.0.5. CI status must be checked separately on GitHub; local test
success is not evidence that hosted CI ran or passed.

Стабильный релиз пока не подтверждён: автоматические тесты не заменяют проверку
Windows + D6 + Companion. Готовы исходники кандидата и инструкция ручной проверки.
