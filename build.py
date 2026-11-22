#!/usr/bin/env python3
"""Build AnyDL.cherri from AnyDL.cherri.in by embedding anydl.py, the
welcome page and the menu icons as base64.

Compile and sign the result at https://playground.cherrilang.org
(paste AnyDL.cherri, press build, then Sign Shortcut), or use tools/.
"""
import base64
import pathlib

here = pathlib.Path(__file__).parent


def b64(path):
    return base64.b64encode((here / path).read_bytes()).decode()


source = (here / "AnyDL.cherri.in").read_text()
source = source.replace("__SCRIPT_B64__", b64("anydl.py"))
source = source.replace("__WELCOME_B64__", b64("welcome.html"))
for name in ("video", "audio", "gallery", "file", "settings"):
    source = source.replace("__ICON_%s__" % name.upper(), b64("icons/%s.png" % name))
(here / "AnyDL.cherri").write_text(source)
print("Wrote AnyDL.cherri (%d bytes)" % len(source))
