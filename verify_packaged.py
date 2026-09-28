"""Windows packaging gates: real executables, no attached D6 required."""
import subprocess
import tempfile
import shutil
from pathlib import Path
root=Path(__file__).resolve().parent/'dist'
subprocess.run([str(root/'D6Tools.exe'),'--self-test'],check=True,timeout=30)
# Test the actual console helper with redirected pipes, as started by the tray.
with tempfile.TemporaryDirectory() as tmp:
    worker=Path(tmp)/'D6Tools.exe'
    shutil.copy2(root/'D6Tools.exe',worker)
    child=subprocess.Popen([str(worker),'--worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    try:
        child.wait(timeout=30)
        output=child.stdout.read()
    except subprocess.TimeoutExpired:
        child.kill();child.communicate();raise
    child.stdin.close();child.stdout.close()
    assert child.returncode==1,(child.returncode,output)
    assert '"state": "error"' in output,output
    assert 'screen_map.json' in (Path(tmp)/'d6_bridge.log').read_text(encoding='utf-8')
# Launch the real Windows tray event loop, then exit through its normal cleanup.
subprocess.run([str(root/'D6Companion.exe'),'--smoke-test'],check=True,timeout=30)
print('PASS: packaged components, redirected worker failure reporting, tray startup and shutdown')
