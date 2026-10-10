"""Actual descendant termination, parent-death cleanup and address isolation."""
import os
from pathlib import Path
import subprocess
import sys
import time
import pytest
from pydantic import ValidationError
from app.config import Settings
from app.processes import spawn_owned
import app.processes as managed

@pytest.mark.parametrize('parent_death',[False,True])
def test_complete_owned_tree_stops(tmp_path,parent_death):
    marker=tmp_path/'heartbeat'
    child=tmp_path/'child.py'
    child.write_text("import sys,time\nfrom pathlib import Path\np=Path(sys.argv[1])\nwhile True:\n p.write_text(str(time.time_ns()))\n time.sleep(.05)\n")
    supervisor=tmp_path/'parent.py'
    supervisor.write_text("import subprocess,sys,time\nsubprocess.Popen([sys.executable,sys.argv[1],sys.argv[2]])\ntime.sleep(60)\n")
    launcher=tmp_path/'launcher.py'
    launcher.write_text("import sys,time\nfrom app.processes import spawn_owned\np,tree=spawn_owned(sys.argv[1:])\ntime.sleep(60)\n")
    env=os.environ.copy();env['PYTHONPATH']=str(Path(managed.__file__).resolve().parents[1])
    command=[sys.executable,str(supervisor),str(child),str(marker)]
    process=tree=None
    try:
        if parent_death:process=subprocess.Popen([sys.executable,str(launcher),*command],env=env)
        else:process,tree=spawn_owned(command,env=env)
        deadline=time.monotonic()+10
        while not marker.exists() and time.monotonic()<deadline:time.sleep(.05)
        assert marker.exists(),'Real grandchild did not start'
        if parent_death:process.kill()
        else:tree.close()
        process.wait(timeout=10)
        time.sleep(.3);before=marker.read_text();time.sleep(.3)
        assert marker.read_text()==before,'Descendant survived owned-tree shutdown'
    finally:
        if tree:tree.close()
        if process and process.poll() is None:process.kill();process.wait(timeout=10)

def test_container_addresses_do_not_relax_native_defaults(monkeypatch):
    for key in tuple(os.environ):
        if key.startswith('GOV_'):monkeypatch.delenv(key)
    native=Settings(_env_file=None)
    assert native.db_host=='127.0.0.1' and native.index_url=='http://127.0.0.1:8011'
    for changes in ({'db_host':'postgres'},{'index_url':'http://index:8011'},
                    {'deployment_mode':'container_local','db_host':'remote.example','index_url':'http://index:8011'}):
        with pytest.raises(ValidationError):Settings(_env_file=None,**changes)
    packaged=Settings(_env_file=None,deployment_mode='container_local',db_host='postgres',index_url='http://index:8011')
    assert packaged.owner_path('index')==packaged.data_dir.parent/'vectors/owner.lock'
