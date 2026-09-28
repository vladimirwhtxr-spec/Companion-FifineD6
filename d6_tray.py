from app_paths import app_root
"""D6 Companion Bridge v0.4.1-rc.1, Windows notification area application."""
import ctypes
from ctypes import wintypes as w
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
import time
from tray_controller import Controller

ROOT=app_root()
LABELS={'disabled':'Выключен','starting':'Запуск…','connecting':'Подключение к Companion…',
        'connected':'Подключён к Companion','offline':'Companion недоступен',
        'stopping':'Остановка…','error':'Ошибка — откройте журнал'}

def message(text):
    ctypes.windll.user32.MessageBoxW(None,text,'D6 Companion Bridge',0x40)

def main(smoke_test=False):
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
        command=([str(ROOT/'D6Tools.exe'),'--worker'] if getattr(sys,'frozen',False)
                 else [str(python),'-u',str(ROOT/'d6_worker.py')])
        controller=Controller(command,ROOT,update)
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
        smoke_errors=[]
        def smoke_lifecycle():
            try:
                if (ROOT/'screen_map.json').exists():
                    raise RuntimeError('Smoke test requires a clean folder without screen_map.json')
                for _ in range(2):
                    controller.set_enabled(True)
                    deadline=time.monotonic()+10
                    while controller.enabled or controller.process is not None:
                        if time.monotonic()>deadline: raise TimeoutError('Packaged worker did not exit')
                        time.sleep(.02)
                    if controller.state!='error': raise RuntimeError('Expected missing-map error')
            except Exception as exc:
                smoke_errors.append(exc)
            finally:
                exit_app(icon,None)
        def setup(icon):
            icon.visible=True
            if smoke_test:
                threading.Thread(target=smoke_lifecycle,daemon=True).start()
            elif (ROOT/'screen_map.json').exists():
                controller.set_enabled(True)
            else:
                message('Нужна калибровка: выйдите из трея, запустите D6Tools.exe и выберите 1. Если у вас уже есть screen_map.json, скопируйте его в папку программы и нажмите Включить.')
        icon.run(setup=setup)
        if smoke_errors: raise smoke_errors[0]
    finally:
        if controller:
            controller.quit();controller.thread.join()
        kernel.CloseHandle(mutex)

if __name__=='__main__':
    try: main('--smoke-test' in sys.argv)
    except Exception as e:
        logging.exception('Tray failed')
        if '--smoke-test' in sys.argv: raise
        if os.name=='nt': message('Не удалось запустить мост: '+str(e)+'\nПроверьте права записи в папку программы и d6_tray.log.')


