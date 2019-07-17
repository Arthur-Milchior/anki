import aqt
import shutil
import os

def test_gui():
    orig = "tests/support"
    copy = "tests/supportCopy"
    try:
        shutil.rmtree(copy)
    except:
        pass
    shutil.copytree(orig, copy)
    os.system(f"./runanki --base {copy} -p TEST")
    #aqt.run(["Anki","--base", copy, "-p", "TEST"])
    shutil.rmtree(copy)
