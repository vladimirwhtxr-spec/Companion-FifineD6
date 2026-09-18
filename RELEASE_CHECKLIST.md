# Release gate / Проверка перед релизом

Record Windows, Python and Companion versions with results. / Запиши версии и результат.

- [ ] CI passes on Windows and Linux. / CI проходит на Windows и Linux.
- [ ] Clean install and upgrade with existing config/map. / Установка и перенос карты.
- [ ] Hidden launch, tray menu, second-instance warning. / Фоновый запуск и защита от дубля.
- [ ] Surface appears in Companion; all 15 key presses/releases work. / Все 15 кнопок.
- [ ] Correct screen positions, orientation and page changes. / Экраны и страницы.
- [ ] Hold a key, Disable: release arrives, USB is freed. / Остановка с зажатой кнопкой.
- [ ] Repeated and rapid Disable/Enable reconnect without duplicate children. / Повторные включения.
- [ ] Restart Companion; offline keys are not replayed. / Переподключение Companion.
- [ ] Unplug/replug D6; Enable restores operation. / Переподключение USB.
- [ ] Exit removes icon and child process. / После выхода нет оставшегося процесса.
- [ ] Sustained use for 30 minutes with page/image updates. / Длительная работа.

Until these pass, retain the release-candidate label. No stable release has been
approved by this checklist merely because automated tests pass.
