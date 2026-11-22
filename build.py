#!/usr/bin/env python3
"""Build AnyDL.cherri from AnyDL.cherri.in.

Fills in the embedded files (anydl.py, the welcome page), the version from
anydl.py, and the menu rows: @@CARD(Title|Subtitle|icon)@@ becomes a vCard
with icons/<icon>.png as its picture, which Shortcuts shows as a contact in
"Choose from List". The subtitle may contain {@variables}.

Compile and sign the result at https://playground.cherrilang.org
(paste AnyDL.cherri, press build, then Sign Shortcut), or use tools/.
"""
import base64
import pathlib
import re

here = pathlib.Path(__file__).parent


def b64(path):
    return base64.b64encode((here / path).read_bytes()).decode()


def card(match):
    title, subtitle, icon = (part.strip() for part in match.groups())
    for text in (title, subtitle):
        if any(c in text for c in ';"\\'):
            raise SystemExit("Menu text may not contain ; \" or \\: %r" % text)
    return ("BEGIN:VCARD\\nVERSION:3.0\\nN;CHARSET=utf-8:%s\\nORG:%s\\n"
            "PHOTO;ENCODING=b:%s\\nEND:VCARD" % (title, subtitle, b64("icons/%s.png" % icon)))


version = re.search(r'^VERSION = "(\d+)\.(\d+)"', (here / "anydl.py").read_text(), re.M)
source = (here / "AnyDL.cherri.in").read_text()
source = source.replace("__SCRIPT_B64__", b64("anydl.py"))
source = source.replace("__WELCOME_B64__", b64("welcome.html"))
source = source.replace("__VERSION_NUM__", str(int(version.group(1)) * 1000 + int(version.group(2))))
source = source.replace("__VERSION__", "%s.%s" % version.groups())
source = re.sub(r"@@CARD\(([^|)]*)\|([^|)]*)\|([\w-]+)\)@@", card, source)
code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("//"))
leftover = re.findall(r"__[A-Z_]+__|@@CARD", code)
if leftover:
    raise SystemExit("Not filled in: %s" % sorted(set(leftover)))
(here / "AnyDL.cherri").write_text(source)
print("Wrote AnyDL.cherri (%d bytes), version %s.%s" % ((len(source),) + version.groups()))
