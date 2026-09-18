"""D6 Companion Bridge v0.4.1-rc.1, Windows notification area application."""
import ctypes
from ctypes import wintypes as w
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
from tray_controller import Controller

ROOT=Path(__file__).resolve().parent
LABELS={'disabled':'Выключен','starting':'Запуск…','connecting':'Подключение к Companion…',
        'connected':'Подключён к Companion','offline':'Companion недоступен',
        'stopping':'Остановка…','error':'Ошибка — откройте журнал'}

def message(text):
    ctypes.windll.user32.MessageBoxW(None,text,'D6 Companion Bridge',0x40)

def main():
    if os.name!='nt': raise RuntimeError('Tray launcher requires Windows')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[w.LPVOID,w.BOOL,w.LPCWSTR]
    kernel.CreateMutexW.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE]
    mutex=kernel.CreateMutexW(None,False,r'Local\FifineD6CompanionTray')
    if not mutex: raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error()==183:
        kernel.CloseHandle(mutex)
        message('Мост уже запущен. Найдите значок D6 возле часов или в меню скрытых значков.')
        return
    controller=None
    try:
        handler=RotatingFileHandler(ROOT/'d6_tray.log',maxBytes=1_000_000,backupCount=2,encoding='utf-8')
        logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',handlers=[handler])
        import pystray
        from PIL import Image,ImageDraw,ImageFont
        def picture(state):
            color=('#33c885' if state=='connected' else '#e85c5c' if state=='error'
                   else '#84909e' if state=='disabled' else '#efb544')
            im=Image.new('RGBA',(64,64),(0,0,0,0));d=ImageDraw.Draw(im)
            d.rounded_rectangle((2,2,62,62),radius=12,fill='#18212c',outline=color,width=4)
            d.text((32,31),'D6',anchor='mm',fill='white',font=ImageFont.load_default(size=27))
            d.ellipse((45,45,61,61),fill=color)
            return im
        icon=pystray.Icon('fifine-d6-companion',picture('disabled'),'D6: выключен')
        def update(state):
            icon.icon=picture(state)
            icon.title='D6: '+LABELS[state]
            icon.update_menu()
        python=Path(sys.executable).with_name('python.exe')
        controller=Controller([str(python),'-u',str(ROOT/'d6_worker.py')],ROOT,update)
        def open_log(icon,item):
            path=ROOT/'d6_bridge.log'
            if not path.exists(): path=ROOT/'d6_tray.log'
            os.startfile(str(path))
        def exit_app(icon,item):
            controller.quit()
            def finish():
                controller.thread.join()
                icon.stop()
            threading.Thread(target=finish,daemon=True).start()
        icon.menu=pystray.Menu(
            pystray.MenuItem(lambda item: LABELS[controller.state],None,enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Включить',lambda icon,item: controller.set_enabled(True),
                             enabled=lambda item: not controller.enabled and not controller.quitting),
            pystray.MenuItem('Выключить',lambda icon,item: controller.set_enabled(False),
                             enabled=lambda item: controller.enabled and not controller.quitting),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Открыть журнал',open_log),
            pystray.MenuItem('Журнал запуска и трея',lambda icon,item: os.startfile(str(ROOT/'d6_tray.log'))),
            pystray.MenuItem('Открыть папку',lambda icon,item: os.startfile(str(ROOT))),
            pystray.MenuItem('Выход',exit_app,enabled=lambda item: not controller.quitting))
        def setup(icon):
            icon.visible=True
            controller.set_enabled(True)
        icon.run(setup=setup)
    finally:
        if controller:
            controller.quit();controller.thread.join()
        kernel.CloseHandle(mutex)

if __name__=='__main__':
    try: main()
    except Exception as e:
        logging.exception('Tray failed')
        if os.name=='nt': message('Не удалось запустить мост: '+str(e)+'\nЗапустите 01_install.cmd и проверьте d6_tray.log.')
