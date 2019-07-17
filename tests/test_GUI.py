import aqt
def test_gui():
    aqt.run(["Anki","--base","tests/support", "-p", "TEST"])
    print("Ended running")
