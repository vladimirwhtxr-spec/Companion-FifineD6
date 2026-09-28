# Both executables share one runtime directory. Onedir workers have no extra
# bootloader parent, so forced termination cannot leave a hidden worker behind.
tools = Analysis(['tools_app.py'], pathex=[], binaries=[], datas=[], hiddenimports=['hid'])
tray = Analysis(['d6_tray.py'], pathex=[], binaries=[], datas=[], hiddenimports=['pystray._win32'])
tools_exe = EXE(PYZ(tools.pure), tools.scripts, [], exclude_binaries=True, name='D6Tools', console=True, upx=False)
tray_exe = EXE(PYZ(tray.pure), tray.scripts, [], exclude_binaries=True, name='D6Companion', console=False, upx=False)
app = COLLECT(tools_exe, tray_exe, tools.binaries, tools.datas, tray.binaries, tray.datas,
              name='D6Companion', upx=False)
