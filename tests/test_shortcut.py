"""Static checks on the shortcut source (AnyDL.cherri.in) and its build.

Shortcuts gives no error for a menu choice that matches nothing or a view
nobody draws: the shortcut just ends. These tests catch those mistakes.
"""
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parent.parent
source = (root / "AnyDL.cherri.in").read_text(encoding="utf-8")
code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith(("//", "/*", "*")))
cards = re.findall(r"@@CARD\(([^|)]*)\|([^|)]*)\|([\w-]+)\)@@", code)


def test_build_fills_everything(tmp_path):
    result = subprocess.run([sys.executable, str(root / "build.py")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    built = (root / "AnyDL.cherri").read_text(encoding="utf-8")
    lines = [l for l in built.splitlines() if not l.lstrip().startswith("//")]
    assert not re.search(r"__[A-Z_]+__|@@CARD", "\n".join(lines))
    version = re.search(r'^VERSION = "([\d.]+)"', (root / "anydl.py").read_text(), re.M).group(1)
    assert version in built


def test_version_matches_changelog():
    version = re.search(r'^VERSION = "([\d.]+)"', (root / "anydl.py").read_text(), re.M).group(1)
    top = re.search(r"^## (\S+)", (root / "CHANGELOG.md").read_text(), re.M).group(1)
    assert top == version


def test_every_menu_icon_exists():
    assert cards
    missing = sorted({icon for _, _, icon in cards if not (root / "icons" / (icon + ".png")).exists()})
    assert not missing


def test_constants_are_unique_and_do_not_clash_with_variables():
    consts = re.findall(r"^\s*const (\w+)\s*=", code, re.M)
    duplicates = sorted({c for c in consts if consts.count(c) > 1})
    assert not duplicates, duplicates
    variables = set(re.findall(r"@(\w+)", code))
    assert not (set(consts) & variables), sorted(set(consts) & variables)


def test_variables_are_set_before_they_are_read():
    assigned = set(re.findall(r"@(\w+)\s*(?:=|\+=|:)", code))
    assigned |= set(re.findall(r"for (\w+) in", code))           # loop variables
    used = set(re.findall(r"@(\w+)", code))
    builtins = {"input", "CARD"}
    assert not (used - assigned - builtins), sorted(used - assigned - builtins)


def blocks():
    """Each view's code, keyed by view name."""
    found = {}
    starts = [(m.start(), m.group(1)) for m in re.finditer(r'^    if @view == "([\w-]+)" \{', code, re.M)]
    for i, (start, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(code)
        found[name] = found.get(name, "") + code[start:end]
    return found


def test_every_view_has_a_screen():
    targets = set(re.findall(r'@view = "([\w-]+)"', code))
    assert targets - set(blocks()) == set()


def test_every_menu_choice_matches_a_row():
    for view, text in blocks().items():
        rows = {title.strip() for title, _, _ in re.findall(r"@@CARD\(([^|)]*)\|([^|)]*)\|([\w-]+)\)@@", text)}
        rows |= set(re.findall(r'"([^"{}]+)"', " ".join(re.findall(r"list\(([^)]*)\)", text))))
        rows |= set(re.findall(r'\+= "([^"@{]+)"', text))
        if not rows:
            continue
        checked = set(re.findall(r'@menuPick == "([^"]+)"', text))
        unknown = sorted(c for c in checked if c not in rows)
        assert not unknown, (view, unknown)


def test_menus_stay_short():
    for name, text in re.findall(r"@(\w+Items): array(.*?)setName", code, re.S):
        branches = re.split(r"\} else \{", text)
        for branch in branches:
            rows = len(re.findall(r"@%s \+=" % name, branch))
            assert rows <= 7, (name, rows)


def test_menu_text_is_safe_for_vcards():
    for title, subtitle, _ in cards:
        for text in (title, subtitle):
            assert not set(';"\\') & set(text), text


def test_script_statuses_are_all_handled():
    script = (root / "anydl.py").read_text()
    statuses = set(re.findall(r'status\("([A-Z]+)"', script)) | set(re.findall(r'finish_status = "([A-Z]+)"', script))
    statuses |= set(re.findall(r'return "([A-Z]{2,})"', script))
    handled = set(re.findall(r'[=!]= "([A-Z]{2,})"', code))
    assert statuses, "no statuses found in anydl.py"
    assert not (statuses - handled - {"VIEW", "FILES"}), sorted(statuses - handled)


def test_video_sizes_use_the_multiplication_sign():
    sizes = re.findall(r'encodeVideo\w*\([^)]*"([^"]*\d+[x×]\d+)"', code)
    sizes += re.findall(r'"WFMediaSize": "([^"]+)"', code)
    assert sizes and all("x" not in size for size in sizes), sizes


def test_a_file_name_is_not_taken_for_a_link():
    # A shared video's name (IMG_1234.MOV) reads as a link: .mov is a web domain.
    pattern = re.search(r"const fileNameFound = matchText\('([^']+)'", code).group(1)
    for name in ("http://IMG_1234.MOV", "IMG_5678.HEIC", "http://clip.mp4/"):
        assert re.search(pattern, name, re.I), name
    for link in ("https://youtu.be/abc", "https://example.com/video.mp4", "https://www.tiktok.com/@a/video/1",
                 "https://x.com/a/status/1"):
        assert not re.search(pattern, link, re.I), link
    assert code.index("fileNameFound") < code.index('fileDetailOf(@firstShared, "File Extension")')


def test_errors_return_to_the_menu():
    second_half = code[code.index('if @input contains "anydl-return"'):code.index("const welcomeText")]
    assert 'if @status != "NOLINK"' in second_half
    assert 'alert("{@status}", "AnyDL")\n            stop()' not in second_half
