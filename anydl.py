#!/usr/bin/env python3
"""AnyDL - download whatever a link points to.

Runs inside a-Shell on iOS, started by the AnyDL shortcut. The shortcut writes
anydl_job.txt, runs this script, and reads the result back:

    anydl_job.txt      line 1: mode (video | audio | gallery | file | pick |
                       playlist), then the link, or for "pick" the chosen list
                       entries, or for "playlist" the chosen amount. Lines of
                       the form key=value are settings (see read_job).
    anydl_settings.txt the shortcut's saved settings, as key=value lines
    anydl_status.txt   "OK", "PICK", "PLAYLIST", "SAVED", "VIEW", or a
                       one-line error message
    anydl_message.txt  when PLAYLIST or SAVED: the text for the shortcut to show
    anydl_open.txt     when SAVED: a link that opens the folder in Files
    anydl_number.txt   when PLAYLIST: the question for typing an amount
    anydl_update.txt   a newer AnyDL version, once (see check_for_update)
    anydl_files.txt    when OK: one downloaded file name per line
    anydl_choices.txt  when PICK or PLAYLIST: one entry per line to choose from
    anydl_large.txt    when VIEW: full paths of the files saved for the preview

The shortcut does not wait for this script. When there is something for it
to show (status PICK, OK or an error), the script starts AnyDL again with
"anydl-return" as input (see back_to_shortcuts). For "VIEW" it shows the
download in a-Shell's own preview instead (see show_in_ashell).

What each mode tries, after first checking whether the link itself is a file:
    video    yt-dlp, then for X posts FxTwitter, then video found on the page
    audio    yt-dlp (audio only), then audio found on the page
    gallery  gallery-dl, then for X posts FxTwitter, then images on the page
    file     documents, archives and media linked on the page
"""
import html
import importlib
import json
import mimetypes
import os
import re
import shutil
import site
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

VERSION = "2.8"

BASE = os.environ.get("ANYDL_DIR") or os.environ.get("SHORTCUTS") or os.getcwd()
TMP = os.path.join(BASE, "anydl_tmp")
JOB_FILE = os.path.join(BASE, "anydl_job.txt")
STATUS_FILE = os.path.join(BASE, "anydl_status.txt")
LIST_FILE = os.path.join(BASE, "anydl_files.txt")
LARGE_FILE = os.path.join(BASE, "anydl_large.txt")
CHOICES_FILE = os.path.join(BASE, "anydl_choices.txt")
CANDIDATES_FILE = os.path.join(BASE, "anydl_candidates.json")
PLAYLIST_FILE = os.path.join(BASE, "anydl_playlist.json")
MESSAGE_FILE = os.path.join(BASE, "anydl_message.txt")
OPEN_FILE = os.path.join(BASE, "anydl_open.txt")
NUMBER_FILE = os.path.join(BASE, "anydl_number.txt")
UPDATE_FILE = os.path.join(BASE, "anydl_update.txt")
UPDATE_STATE_FILE = os.path.join(BASE, "anydl_update_state.json")
STAMP_FILE = os.path.join(BASE, "anydl_stamp.txt")

# Used only for plain page and file requests. The downloaders keep their own
# identity: forcing one on yt-dlp breaks sites such as TikTok.
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
UPDATE_EVERY = 7 * 24 * 3600
MAX_ITEMS = 25          # cap for galleries and items found on a page
PLAYLIST_LIMIT = 100    # most videos one playlist download takes
MENU_LIMIT = 60
MODES = ("video", "audio", "gallery", "file")

# Settings, as the shortcut saves them (human-readable values).
DEFAULT_OPTIONS = {"quality": "best", "audio": "original", "updates": "on"}
QUALITY_HEIGHTS = {"1080p": 1080, "720p": 720, "480p": 480, "data saver": 360}

RELEASES_API = "https://api.github.com/repos/h4sw5q2wr9-byte/AnyDL/releases/latest"
UPDATE_EVERY_DAY = 24 * 3600

# A single download is shown in a-Shell's own Quick Look preview, which has
# the same share button as the one in Shortcuts, and is kept in a folder the
# Files app shows (On My iPhone > a-Shell > AnyDL). a-Shell can only preview
# one file at a time, so several files go back to Shortcuts, which can page
# through them, unless one of them is large: Shortcuts gets files from a-Shell
# with "Get File", which fails for large files (with "copy file" it loads the
# whole file into memory, and without it Shortcuts crashes on iOS 27.2, see
# a-Shell issue #1138). Then the largest file is shown in a-Shell, and all of
# them are in the Files folder.
LARGE_BYTES = 50 * 1024 * 1024
VISIBLE_DIR = os.path.join(os.path.expanduser("~"), "Documents", "AnyDL")

# Set once control has been handed back to Shortcuts or to the preview.
_handed_off = False


def a_shell(command):
    """Run an a-Shell command such as `open` or `view` (no-op elsewhere)."""
    try:
        subprocess.run(command)
        return True
    except Exception:
        return False


# Starts the shortcut again so it can show the results. The shortcut has to
# keep the name AnyDL for this. The URL has no spaces, so it needs no quoting.
RETURN_URL = "shortcuts://run-shortcut?name=AnyDL&input=text&text=anydl-return"


def back_to_shortcuts():
    global _handed_off
    if not _handed_off:
        _handed_off = True
        a_shell("open " + RETURN_URL)


def show_in_ashell(path):
    global _handed_off
    _handed_off = True
    # a-Shell splits the command line itself; names never contain double
    # quotes or backslashes (see safe_name), so plain quoting is enough.
    a_shell('view "%s"' % path)

VIDEO_EXT = {"mp4", "m4v", "mov", "webm", "mkv", "avi", "flv", "wmv", "mpg", "mpeg", "3gp", "ts"}
AUDIO_EXT = {"mp3", "m4a", "aac", "wav", "flac", "ogg", "opus", "wma", "aiff"}
STREAM_EXT = {"m3u8", "mpd"}
IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp", "heic", "bmp", "tiff", "svg", "avif"}
FILE_EXT = {
    "pdf", "epub", "mobi", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp",
    "rtf", "txt", "csv", "json", "xml", "md",
    "zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz", "iso", "dmg", "pkg",
    "apk", "ipa", "exe", "msi", "deb", "rpm", "appimage", "jar",
    "ttf", "otf", "woff", "woff2", "psd", "ai", "sketch", "fig", "stl", "obj", "blend",
    "srt", "vtt", "ass", "torrent", "shortcut", "mobileconfig", "ics", "vcf",
}
STREAM_TYPES = ("mpegurl", "dash+xml")
HTML_TYPES = ("text/html", "application/xhtml")
# Which page-scan finds each mode accepts.
MODE_KINDS = {
    "video": ("video", "stream"),
    "audio": ("audio",),
    "gallery": ("image",),
    "file": ("video", "stream", "audio", "file"),
}


class Failed(Exception):
    """A method could not handle the link."""


class NeedPick(Exception):
    """Several items were found; the shortcut must ask which to download."""


class NeedPlaylistCount(Exception):
    """The link is a playlist; the shortcut must ask how many to download."""


def say(msg=""):
    print(msg, flush=True)


def write_status(text):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def finish(files=None, error=None):
    """Write the result files the shortcut reads, then exit."""
    shutil.rmtree(TMP, ignore_errors=True)
    if files and (len(files) == 1 or any(os.path.getsize(p) > LARGE_BYTES for p in files)):
        shown = move_visible(files)
        with open(LARGE_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(shown))
        write_status("VIEW")
        say("\nDone: %d file%s, saved in Files > On My iPhone > a-Shell > AnyDL."
            % (len(shown), "" if len(shown) == 1 else "s"))
        biggest = max(shown, key=os.path.getsize)
        show_in_ashell(biggest)
        sys.exit(0)
    if files:
        with open(LIST_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(os.path.basename(p) for p in files))
        status = "OK"
        say("\nDone: %d file%s." % (len(files), "" if len(files) == 1 else "s"))
    else:
        status = re.sub(r"\s+", " ", error or "Nothing was downloaded.").strip()[:400]
        say("\nFailed: " + status)
    write_status(status)
    back_to_shortcuts()
    sys.exit(0)


def move_visible(files):
    """Move a run's files into the folder the Files app shows."""
    os.makedirs(VISIBLE_DIR, exist_ok=True)
    out = []
    for src in files:
        name = os.path.basename(src)
        stem, ext = os.path.splitext(name)
        dest = os.path.join(VISIBLE_DIR, name)
        n = 2
        while os.path.exists(dest):
            dest = os.path.join(VISIBLE_DIR, "%s (%d)%s" % (stem, n, ext))
            n += 1
        shutil.move(src, dest)
        out.append(dest)
    return out


def cleanup_previous(keep_candidates=False):
    """Delete the files left by the last run so storage does not pile up."""
    for listing in (LIST_FILE, LARGE_FILE):
        if not os.path.exists(listing):
            continue
        try:
            with open(listing, encoding="utf-8") as f:
                for line in f.read().splitlines():
                    name = os.path.basename(line.strip())
                    if not name or name.startswith("anydl"):
                        continue
                    folder = VISIBLE_DIR if listing == LARGE_FILE else BASE
                    path = os.path.join(folder, name)
                    if os.path.isfile(path):
                        os.remove(path)
        except OSError:
            pass
    leftovers = [LIST_FILE, LARGE_FILE, CHOICES_FILE, MESSAGE_FILE, OPEN_FILE, NUMBER_FILE]
    if not keep_candidates:
        leftovers += [CANDIDATES_FILE, PLAYLIST_FILE]
    for path in leftovers:
        try:
            os.remove(path)
        except OSError:
            pass
    shutil.rmtree(TMP, ignore_errors=True)


def new_folder(label="work"):
    os.makedirs(TMP, exist_ok=True)
    n = 1
    while True:
        path = os.path.join(TMP, "%s_%d" % (label, n))
        if not os.path.exists(path):
            os.makedirs(path)
            return path
        n += 1


def safe_name(name, fallback="download"):
    name = urllib.parse.unquote(name or "")
    # Letters, digits and a few safe marks only: the name travels through
    # Shortcuts text and a-Shell paths, where emoji and symbols cause trouble.
    name = re.sub(r"[^\w .()'\-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" ._-")
    if not name:
        name = fallback
    stem, ext = os.path.splitext(name)
    if len(ext) > 12:
        stem, ext = name, ""
    return stem[:90].rstrip(" ._") + ext


def publish(paths):
    """Move finished files next to the status files, with safe unique names."""
    out = []
    for src in paths:
        if not os.path.isfile(src) or os.path.getsize(src) == 0:
            continue
        name = safe_name(os.path.basename(src))
        if name.startswith("anydl"):
            name = "file_" + name
        stem, ext = os.path.splitext(name)
        dest = os.path.join(BASE, name)
        n = 2
        while os.path.exists(dest):
            dest = os.path.join(BASE, "%s (%d)%s" % (stem, n, ext))
            n += 1
        shutil.move(src, dest)
        out.append(dest)
    return out


def collect(folder):
    found = []
    for root, _dirs, names in os.walk(folder):
        for name in sorted(names):
            if name.endswith((".part", ".ytdl", ".tmp")) or name.startswith("."):
                continue
            found.append(os.path.join(root, name))
    return found


def empty(folder):
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder, exist_ok=True)


# ---------------------------------------------------------------- network

def _context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def open_url(url, referer=None, timeout=30):
    headers = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), ssl.SSLError):
            return urllib.request.urlopen(req, timeout=timeout, context=_context())
        raise


def ext_of(url):
    path = urllib.parse.urlsplit(url).path
    return os.path.splitext(path)[1].lower().lstrip(".")


def name_from_response(resp, url):
    cd = resp.headers.get("Content-Disposition") or ""
    m = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", cd, re.I)
    if m:
        return safe_name(m.group(1))
    m = re.search(r"filename\s*=\s*\"?([^\";]+)", cd, re.I)
    if m:
        return safe_name(m.group(1))
    name = os.path.basename(urllib.parse.urlsplit(resp.geturl() or url).path)
    name = safe_name(name)
    if not os.path.splitext(name)[1]:
        ctype = (resp.headers.get_content_type() or "").lower()
        guess = mimetypes.guess_extension(ctype) or ""
        name += {".jpe": ".jpg", ".htm": ".html"}.get(guess, guess)
    return name


def save_stream(resp, dest):
    total = int(resp.headers.get("Content-Length") or 0)
    done = 0
    last = 0.0
    with open(dest, "wb") as f:
        while True:
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            now = time.time()
            if now - last > 0.7:
                last = now
                if total:
                    sys.stdout.write("\r  %.1f / %.1f MB (%d%%)   " % (done / 1e6, total / 1e6, done * 100 // total))
                else:
                    sys.stdout.write("\r  %.1f MB   " % (done / 1e6))
                sys.stdout.flush()
    sys.stdout.write("\r  %.1f MB downloaded.        \n" % (done / 1e6))
    if total and done < total:
        raise Failed("The download stopped early (%d of %d bytes)." % (done, total))
    if done == 0:
        raise Failed("The server sent an empty file.")
    return dest


def direct_download(url, folder, resp=None, referer=None):
    if resp is None:
        resp = open_url(url, referer=referer)
    with resp:
        name = name_from_response(resp, url)
        say("Downloading " + name)
        return save_stream(resp, os.path.join(folder, name))


# ---------------------------------------------------------------- packages

def _pip(args):
    cmd = ["install", "-q", "--disable-pip-version-check"] + args
    try:
        if subprocess.call([sys.executable or "python3", "-m", "pip"] + cmd) == 0:
            return True
    except Exception:
        pass
    try:
        return subprocess.call(["pip"] + cmd) == 0
    except Exception:
        return False


def _refresh_paths(package):
    """Make a just-installed package importable in this running Python.

    The first install on a fresh a-Shell creates the packages folder, and a
    Python that was already running does not look there by itself.
    """
    folders = []
    try:
        out = subprocess.check_output(
            [sys.executable or "python3", "-m", "pip", "show", package],
            stderr=subprocess.DEVNULL).decode("utf-8", "replace")
        m = re.search(r"^Location:\s*(.+)$", out, re.M)
        if m:
            folders.append(m.group(1).strip())
    except Exception:
        pass
    try:
        folders.append(site.getusersitepackages())
    except Exception:
        pass
    try:
        folders.extend(site.getsitepackages())
    except Exception:
        pass
    ver = "python%d.%d" % sys.version_info[:2]
    folders.append(os.path.expanduser("~/Library/lib/%s/site-packages" % ver))
    for folder in folders:
        if folder and os.path.isdir(folder) and folder not in sys.path:
            site.addsitedir(folder)
    importlib.invalidate_caches()


def ensure(module, package, extras=()):
    """Import a pure-Python package, installing it on first use.

    Returns None when it is installed but cannot be imported; the caller then
    runs the command-line tool instead.
    """
    try:
        return importlib.import_module(module)
    except ImportError:
        pass
    _refresh_paths(package)
    try:
        return importlib.import_module(module)
    except ImportError:
        pass
    say("First run: installing %s (this can take a minute)..." % package)
    if not _pip([package]):
        raise Failed("Could not install %s. Check the internet connection." % package)
    for extra in extras:
        _pip([extra])
    _refresh_paths(package)
    try:
        return importlib.import_module(module)
    except ImportError:
        return None


def _run_tool(names, args):
    """Run a downloader as a command when it cannot be imported."""
    for name in names:
        try:
            code = subprocess.call((name if isinstance(name, list) else [name]) + args)
        except Exception:
            continue
        if code == 0:
            return True
    return False


def weekly_update():
    """Sites change often, so refresh the downloaders once a week."""
    try:
        with open(STAMP_FILE) as f:
            last = float(f.read().strip() or 0)
    except (OSError, ValueError):
        _stamp()            # first run: ensure() installs what is needed
        return
    if time.time() - last < UPDATE_EVERY:
        return
    say("Updating downloaders...")
    _pip(["--upgrade", "yt-dlp", "gallery-dl"])
    _stamp()


def _stamp():
    try:
        with open(STAMP_FILE, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass


# ---------------------------------------------------------------- yt-dlp

# H.264 + AAC in an mp4 first, so the result saves straight to Photos. The
# second entry needs no merging, for when ffmpeg is unavailable.
VIDEO_FORMATS = [
    ("bv*[vcodec^=avc1]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b", "mp4"),
    ("b[ext=mp4]/b", None),
]


def video_formats(quality):
    """VIDEO_FORMATS, limited to a resolution for the quality setting.

    "720p" means the short side of the picture, so an upright video (TikTok,
    Shorts) of 720x1280 counts as 720p. yt-dlp's filters cannot take the
    smaller of two fields, so wide and upright formats get their own filter.
    If nothing is small enough, the smallest available is taken ("w").
    """
    limit = QUALITY_HEIGHTS.get((quality or "").lower())
    if not limit:
        return VIDEO_FORMATS
    sides = ("[aspect_ratio>=?1][height<=?%d]" % limit,   # wide, or size unknown
             "[aspect_ratio<1][width<=?%d]" % limit)      # upright

    def alternatives(*pieces):
        return "/".join(piece.format(side) for piece in pieces for side in sides)

    merged = alternatives("bv*{0}[vcodec^=avc1]+ba[ext=m4a]", "b{0}[ext=mp4]", "bv*{0}+ba", "b{0}")
    single = alternatives("b{0}[ext=mp4]", "b{0}")
    return [(merged + "/w", "mp4"), (single + "/w", None)]


def have_ffmpeg():
    """Whether yt-dlp can use ffmpeg (to join video and sound, or make MP3s)."""
    try:
        from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor
        return bool(FFmpegPostProcessor().available)
    except Exception:
        return False


def mp3_postprocessors(with_cover=True):
    steps = []
    if with_cover:
        steps.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
    steps += [
        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
        {"key": "FFmpegMetadata", "add_metadata": True},
    ]
    if with_cover:
        steps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    return steps
AUDIO_FORMATS = [
    ("ba[ext=m4a]/ba[ext=mp3]/ba/b", None),
]


# yt-dlp writes these four fields into the file name; tidy_media_names() then
# turns them into a short readable name.
NAME_SEP = " ~~ "
NAME_TEMPLATE = "%(uploader,channel,creator|)s ~~ %(title|).120B ~~ %(extractor_key|)s ~~ %(id)s.%(ext)s"
TITLE_LIMIT = 48


def nice_title(title, uploader=""):
    """A caption cut down to a few readable words: no links, tags or emoji."""
    title = title or ""
    if uploader and title.lower().startswith(uploader.lower()):
        title = title[len(uploader):]
    title = re.sub(r"https?://\S+", " ", title)
    title = re.sub(r"[#@＃＠]\w+", " ", title)
    title = re.sub(r"[\u2018\u2019`]", "'", title)
    title = re.sub(r"[^\w ()'\-]+", " ", title).replace("_", " ")
    title = re.sub(r"\s+", " ", title).strip(" -'")
    if len(title) > TITLE_LIMIT:
        cut = title[:TITLE_LIMIT + 1]
        title = (cut[:cut.rfind(" ")] if " " in cut[20:] else cut[:TITLE_LIMIT]).strip(" -'")
    if title.count("(") > title.count(")"):
        title = title[:title.rfind("(")].strip(" -'")
    return title


def media_name(uploader, title, site, vid):
    uploader = re.sub(r"\s+", " ", re.sub(r"[^\w ()\-.]+", " ", uploader or "")).strip(" .-")[:30]
    title = nice_title(title, uploader)
    site = re.sub(r"[^\w]+", "", site or "") or "Video"
    if site.lower() == "generic":
        site = ""
    if uploader and title:
        return "%s - %s" % (uploader, title)
    if title:
        return title
    tail = ("%s %s" % (site, vid[:16])).strip() or "download"
    return "%s - %s" % (uploader, tail) if uploader else tail


def tidy_media_names(files):
    out = []
    for path in files:
        folder, base = os.path.split(path)
        stem, ext = os.path.splitext(base)
        parts = stem.split(NAME_SEP)
        if len(parts) != 4:
            parts = [p.strip() for p in stem.split("~~")]
        if len(parts) == 4:
            name = media_name(*[p.strip() for p in parts])
            target = os.path.join(folder, name + ext)
            n = 2
            while os.path.exists(target):
                target = os.path.join(folder, "%s (%d)%s" % (name, n, ext))
                n += 1
            try:
                os.rename(path, target)
                path = target
            except OSError:
                pass
        out.append(path)
    return out


# YouTube's challenge solver sets the page location to a made-up watch link.
# Runtimes without a real page need that; inside the WebKit view used on iOS
# it is a real navigation, which iOS hands to the YouTube app ("video
# unavailable"). a-Shell then sits in the background and cannot switch back to
# Shortcuts. The page's own location only changes once that navigation
# happens, so the statement adds nothing to solving there and can be dropped.
SOLVER_NAVIGATION = re.compile(
    r"globalThis\.location\s*=\s*new URL\(\s*\\*[\"']"
    r"https://www\.youtube\.com/watch\?v=yt-dlp-wins"
    r"\\*[\"']\s*\)")


def stop_solver_navigation():
    """Keep the WebKit challenge solver from navigating to youtube.com."""
    try:
        from yt_dlp.extractor.youtube.jsc._builtin import ejs
    except Exception:
        return False
    cls = getattr(ejs, "EJSBaseJCP", None)
    if cls is None or not hasattr(cls, "_construct_stdin"):
        return False
    if getattr(cls, "_anydl_patched", False):
        return True
    original = cls._construct_stdin

    def construct(self, *args, **kwargs):
        text = original(self, *args, **kwargs)
        name = "%s %s" % (getattr(self, "JS_RUNTIME_NAME", ""), type(self).__name__)
        if "webkit" in name.lower():
            text = SOLVER_NAVIGATION.sub("void 0", text)
        return text

    cls._construct_stdin = construct
    cls._anydl_patched = True
    return True


def clean_error(text):
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(text))
    text = re.sub(r"^ERROR:\s*", "", text.strip())
    text = re.split(r";?\s*please report this issue", text, flags=re.I)[0]
    text = re.split(r"\s*\(caused by ", text)[0]
    # Drop yt-dlp's command-line advice; it means nothing in an iPhone alert.
    text = re.split(r"\s+(?:This helps protect our community\.\s*)?Use --cookies|\s+See https://github\.com/yt-dlp", text)[0]
    text = text.strip()
    if re.search(r"NSFW|authenticat|log ?in|sign in|cookies|age.restricted|private", text, re.I):
        text += " (This post needs a logged-in account, and AnyDL has no login.)"
    return text


def looks_unmerged(files):
    """yt-dlp leaves name.f123.mp4 + name.f456.m4a behind when it cannot merge."""
    return any(re.search(r"\.f[\w-]+\.\w+$", os.path.basename(p)) for p in files)


def try_ytdlp(url, folder, audio=False, referer=None, options=None, playlist=0):
    """Download with yt-dlp. playlist > 0 downloads that many playlist items."""
    options = options or DEFAULT_OPTIONS
    yt_dlp = ensure("yt_dlp", "yt-dlp", extras=("yt-dlp-ejs", "yt-dlp-apple-webkit-jsi"))
    formats = AUDIO_FORMATS if audio else video_formats(options.get("quality"))
    ffmpeg = yt_dlp is not None and have_ffmpeg()
    if yt_dlp is not None and not ffmpeg and not audio:
        # Without ffmpeg, separate video and sound streams cannot be joined,
        # which limits some sites (YouTube above 360p) to lower quality.
        formats = [f for f in formats if not f[1]] or formats
        say("Note: ffmpeg is not available, so some videos come in lower quality.")
    mp3 = audio and options.get("audio", "").lower() == "mp3"
    if mp3 and not ffmpeg:
        say("Note: ffmpeg is not available, so audio keeps its original format.")
        mp3 = False
    outtmpl = os.path.join(folder, NAME_TEMPLATE)
    error = None
    attempts = [(fmt, merge, cover) for fmt, merge in formats for cover in ((True, False) if mp3 else (False,))]

    for fmt, merge, cover in attempts:
        empty(folder)
        if yt_dlp is None:
            args = ["-f", fmt, "-o", outtmpl, "--no-warnings", "--windows-filenames"]
            args += (["--yes-playlist", "--playlist-end", str(playlist), "--ignore-errors"]
                     if playlist else ["--no-playlist"])
            if merge:
                args += ["--merge-output-format", merge]
            if referer:
                args += ["--referer", referer]
            py = sys.executable or "python3"
            if not _run_tool(["yt-dlp", [py, "-m", "yt_dlp"]], args + [url]):
                error = "yt-dlp could not download this link."
        else:
            opts = {
                "format": fmt,
                "outtmpl": outtmpl,
                "noplaylist": not playlist,
                "no_warnings": True,
                "retries": 3,
                "fragment_retries": 5,
                "windowsfilenames": True,
            }
            if playlist:
                opts["playlistend"] = playlist
                opts["ignoreerrors"] = True     # one broken video should not stop the rest
            if merge:
                opts["merge_output_format"] = merge
            if mp3:
                opts["postprocessors"] = mp3_postprocessors(cover)
                opts["writethumbnail"] = cover
            if referer:
                opts["http_headers"] = {"Referer": referer}
            try:
                stop_solver_navigation()
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url) or {}
                if not audio and not playlist and info.get("width") and info.get("height"):
                    say("Quality: %dp (%sx%s)" % (min(info["width"], info["height"]),
                                                  info["width"], info["height"]))
            except Exception as e:
                error = clean_error(e)
                if "Unsupported URL" in error or "DRM" in error or "No video could be found" in error:
                    break
                continue
        files = collect(folder)
        if mp3 or audio:
            # Leftover cover images are not downloads.
            files = [f for f in files if ext_of(f) not in IMAGE_EXT] or files
        if mp3 and files and not all(f.lower().endswith(".mp3") for f in files):
            error = "The audio could not be converted to MP3."
            continue
        if files and not looks_unmerged(files):
            return tidy_media_names(files)
        if files:
            error = "The video and sound could not be joined (ffmpeg is missing)."
    empty(folder)
    raise Failed(error or "yt-dlp found nothing to download.")


# ---------------------------------------------------------------- playlists

def is_playlist_link(url):
    """Whether yt-dlp treats the link as a playlist, channel or profile.

    Decided from the link alone, so single videos are not looked up twice.
    """
    try:
        from yt_dlp.extractor import gen_extractor_classes
    except ImportError:
        return False
    for ie in gen_extractor_classes():
        if ie.IE_NAME == "generic" or not ie.suitable(url):
            continue
        kind = getattr(ie, "_RETURN_TYPE", None)
        if kind == "playlist":
            return True
        if ie.IE_NAME == "youtube:tab":
            # Playlists and channels; a watch link inside a playlist is one video.
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            return "v" not in query and "/watch" not in url
        return False
    return False


def playlist_info(url):
    """(title, number of items up to PLAYLIST_LIMIT + 1) of a playlist link."""
    import itertools
    yt_dlp = ensure("yt_dlp", "yt-dlp", extras=("yt-dlp-ejs", "yt-dlp-apple-webkit-jsi"))
    if yt_dlp is None:
        raise Failed("Playlists need yt-dlp to load in Python.")
    opts = {"extract_flat": "in_playlist", "quiet": True, "no_warnings": True,
            "playlistend": PLAYLIST_LIMIT + 1}
    try:
        stop_solver_navigation()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False, process=False)
            entries = info.get("entries") or []
            count = len(list(itertools.islice(entries, PLAYLIST_LIMIT + 1)))
    except Exception as e:
        raise Failed(clean_error(e))
    title = info.get("title") or info.get("uploader") or info.get("id") or "Playlist"
    return title, count


def ask_playlist_count(mode, url, options):
    title, count = playlist_info(url)
    if not count:
        raise Failed("This playlist is empty, or private.")
    what = "videos" if mode == "video" else "tracks"
    most = min(count, PLAYLIST_LIMIT)
    choices = [("All %d %s" % (count, what)) if count <= PLAYLIST_LIMIT
               else "First %d %s" % (PLAYLIST_LIMIT, what)]
    if most > 1:
        choices.append("Choose a number")
    with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
        json.dump({"url": url, "mode": mode, "title": title, "options": options,
                   "most": most}, f)
    with open(CHOICES_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(choices))
    with open(NUMBER_FILE, "w", encoding="utf-8") as f:
        f.write("How many %s? (1 to %d)" % (what, most))
    more = "more than %d" % PLAYLIST_LIMIT if count > PLAYLIST_LIMIT else str(count)
    with open(MESSAGE_FILE, "w", encoding="utf-8") as f:
        f.write("%s has %s %s. How many do you want?" % (nice_title(title) or "This playlist", more, what))
    raise NeedPlaylistCount()


def run_playlist(lines):
    """Download the amount chosen in the shortcut into its own Files folder."""
    try:
        with open(PLAYLIST_FILE, encoding="utf-8") as f:
            job = json.load(f)
    except (OSError, ValueError):
        raise Failed("The playlist details are gone. Run the shortcut again.")
    m = re.search(r"(\d+)", " ".join(lines))
    if not m:
        raise Failed("Nothing was selected.")
    most = job.get("most") or PLAYLIST_LIMIT
    amount = max(1, min(int(m.group(1)), most, PLAYLIST_LIMIT))
    title = nice_title(job.get("title") or "") or "Playlist"
    say("Downloading %d from %s" % (amount, title))
    files = try_ytdlp(job["url"], new_folder("playlist"), audio=(job.get("mode") == "audio"),
                      options=job.get("options"), playlist=amount)
    folder = os.path.join(VISIBLE_DIR, safe_name(title, "Playlist"))
    n = 2
    base = folder
    while os.path.exists(folder):
        folder = "%s (%d)" % (base, n)
        n += 1
    os.makedirs(folder)
    for src in files:
        shutil.move(src, os.path.join(folder, os.path.basename(src)))
    what = "video" if job.get("mode") == "video" else "track"
    what += "" if len(files) == 1 else "s"
    missing = amount - len(files)
    note = (" %d could not be downloaded." % missing) if missing > 0 else ""
    with open(MESSAGE_FILE, "w", encoding="utf-8") as f:
        f.write("Saved %d %s in Files › On My iPhone › a-Shell › AnyDL › %s.%s"
                % (len(files), what, os.path.basename(folder), note))
    with open(OPEN_FILE, "w", encoding="utf-8") as f:
        f.write("shareddocuments://" + urllib.parse.quote(os.path.realpath(folder)))
    return len(files)


# ---------------------------------------------------------------- updates

def version_tuple(text):
    return tuple(int(x) for x in re.findall(r"\d+", text or "")[:3])


def check_for_update(options):
    """Once a day, note a newer AnyDL release for the shortcut to offer.

    Each new version is offered once: the shortcut clears the note after
    showing it, and the version is remembered so it is not written again.
    """
    if options.get("updates", "").lower() == "off":
        return
    try:
        with open(UPDATE_STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    if time.time() - state.get("checked", 0) < UPDATE_EVERY_DAY:
        return
    state["checked"] = time.time()
    try:
        req = urllib.request.Request(RELEASES_API, headers={
            "User-Agent": "AnyDL/%s" % VERSION, "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            latest = (json.load(resp).get("tag_name") or "").lstrip("v")
        if (version_tuple(latest) > version_tuple(VERSION)
                and latest != state.get("announced")):
            with open(UPDATE_FILE, "w", encoding="utf-8") as f:
                f.write(latest)
            state["announced"] = latest
            say("AnyDL %s is available." % latest)
    except Exception:
        pass        # offline or rate-limited: try again tomorrow
    try:
        with open(UPDATE_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass


# ---------------------------------------------------------------- gallery-dl

def try_gallerydl(url, folder):
    module = ensure("gallery_dl", "gallery-dl")
    if module is None:
        py = sys.executable or "python3"
        _run_tool(["gallery-dl", [py, "-m", "gallery_dl"]],
                  ["-D", folder, "--range", "1-%d" % MAX_ITEMS, url])
        files = collect(folder)
        if not files:
            raise Failed("gallery-dl found nothing to download.")
        return files
    from gallery_dl import config, exception, job
    config.clear()
    config.set(("extractor",), "base-directory", folder)
    config.set(("extractor",), "directory", [])
    config.set(("extractor",), "image-range", "1-%d" % MAX_ITEMS)
    config.set(("output",), "mode", "terminal")
    try:
        job.DownloadJob(url).run()
    except exception.NoExtractorError:
        raise Failed("gallery-dl does not know this site.")
    except Exception as e:
        raise Failed("gallery-dl: %s" % clean_error(e))
    files = collect(folder)
    if not files:
        raise Failed("gallery-dl found nothing to download.")
    return files


# ---------------------------------------------------------------- X fallback

# X hides the media of many posts from logged-out visitors (age-restricted
# posts, for example), so yt-dlp and gallery-dl see the post but no video.
# FxTwitter's public API (https://github.com/FxEmbed/FxEmbed) still returns
# direct links to the files on X's own media servers for such posts.
X_HOSTS = ("x.com", "twitter.com", "fxtwitter.com", "fixupx.com", "vxtwitter.com",
           "fixvx.com", "twittpr.com", "nitter.net")
FXTWITTER_API = "https://api.fxtwitter.com/status/%s"


class FxAnswer(Failed):
    """FxTwitter gave a definite answer, such as the post being deleted."""


def x_status_id(url):
    """The post id of an X / Twitter post link, or None."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in X_HOSTS):
        return None
    m = re.search(r"/status(?:es)?/(\d+)", parts.path)
    return m.group(1) if m else None


def fxtwitter_media(post_id):
    """Return (post, [(kind, url)]) for an X post, via FxTwitter."""
    req = urllib.request.Request(FXTWITTER_API % post_id,
                                 headers={"User-Agent": "AnyDL/%s" % VERSION})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FxAnswer("This post does not exist or was deleted.")
        if e.code == 401:
            raise FxAnswer("This post is from a private account.")
        raise Failed("FxTwitter: %s" % e)
    except (OSError, ValueError) as e:
        raise Failed("FxTwitter could not read this post (%s)." % type(e).__name__)
    post = data.get("tweet") or {}
    found = []
    # The post's own media, or else the media of the post it quotes.
    for source in (post, post.get("quote") or {}):
        media = source.get("media") or {}
        for video in media.get("videos") or []:
            if video.get("url"):
                found.append(("video", video["url"]))
        for photo in media.get("photos") or []:
            if photo.get("url"):
                found.append(("image", photo["url"]))
        if found:
            return source, found
    return post, found


def try_fxtwitter(url, folder, kinds):
    post_id = x_status_id(url)
    if not post_id:
        raise Failed("Not an X post.")
    post, media = fxtwitter_media(post_id)
    items = [link for kind, link in media if kind in kinds][:MAX_ITEMS]
    if not items:
        raise FxAnswer("No %s found in this post." % ("video" if "video" in kinds else "images"))
    author = post.get("author") or {}
    base = media_name(author.get("name") or author.get("screen_name") or "",
                      post.get("text") or "", "Twitter", post.get("id") or post_id)
    files = []
    for n, link in enumerate(items, 1):
        path = direct_download(link, folder)
        ext = os.path.splitext(path)[1] or ".mp4"
        name = base if len(items) == 1 else "%s %d" % (base, n)
        target = os.path.join(folder, name + ext)
        if target != path and not os.path.exists(target):
            os.rename(path, target)
            path = target
        files.append(path)
    return files


# ---------------------------------------------------------------- page scan

class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = []          # (url, source tag)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.found.append((a["href"], "download" if "download" in a else "a"))
        elif tag in ("video", "audio", "source", "embed", "track"):
            for key in ("src", "data-src"):
                if a.get(key):
                    self.found.append((a[key], "audio" if tag == "audio" else "media"))
        elif tag == "img":
            for key in ("src", "data-src", "data-original"):
                if a.get(key):
                    self.found.append((a[key], "img"))
        elif tag == "meta":
            prop = (a.get("property") or a.get("name") or "").lower()
            content = a.get("content")
            if content and prop in ("og:video", "og:video:url", "og:video:secure_url",
                                    "twitter:player:stream"):
                self.found.append((content, "media"))
            elif content and prop in ("og:audio", "og:audio:url"):
                self.found.append((content, "audio"))
            elif content and prop in ("og:image", "og:image:url", "twitter:image"):
                self.found.append((content, "img"))


def find_candidates(page_url, text):
    """Return [(kind, url)] for everything downloadable on the page, best first."""
    parser = _Links()
    try:
        parser.feed(text)
    except Exception:
        pass
    raw = list(parser.found)
    # Links buried in scripts / JSON, e.g. "https:\/\/cdn.site\/clip.mp4?x=1".
    # Web fonts and data files found this way are site plumbing, not downloads.
    loose = text.replace("\\/", "/").replace("\\u0026", "&").replace("&amp;", "&")
    noise = {"txt", "json", "xml", "md", "csv", "ttf", "otf", "woff", "woff2"}
    all_ext = "|".join(sorted(VIDEO_EXT | AUDIO_EXT | STREAM_EXT | FILE_EXT - noise))
    for m in re.finditer(r"https?://[^\s\"'<>\\)]+?\.(?:%s)(?:\?[^\s\"'<>\\)]*)?(?=[\s\"'<>\\)]|$)" % all_ext, loose, re.I):
        raw.append((m.group(0), "script"))

    order = {"video": 0, "stream": 0, "audio": 1, "file": 2, "image": 3}
    seen = set()
    out = []
    for link, source in raw:
        link = html.unescape(link.strip())
        if not link or link.startswith(("javascript:", "mailto:", "tel:", "data:", "blob:", "#")):
            continue
        full = urllib.parse.urljoin(page_url, link)
        if not full.startswith(("http://", "https://")) or full in seen:
            continue
        ext = ext_of(full)
        if ext in VIDEO_EXT:
            kind = "video"
        elif ext in STREAM_EXT:
            kind = "stream"
        elif ext in AUDIO_EXT or source == "audio":
            kind = "audio"
        elif ext in FILE_EXT or source == "download":
            kind = "file"
        elif ext in IMAGE_EXT or source == "img":
            kind = "image"
        elif source == "media":
            kind = "video"
        else:
            continue
        seen.add(full)
        out.append((kind, full))
    out.sort(key=lambda c: order[c[0]])
    return out


def label_for(index, kind, link):
    name = safe_name(os.path.basename(urllib.parse.urlsplit(link).path), "item")
    return "%d. %s  (%s)" % (index, name[:60], kind)


def download_items(items, page_url):
    files = []
    errors = []
    for kind, link in items:
        folder = new_folder("item")
        try:
            if kind == "stream":
                files.extend(try_ytdlp(link, folder, referer=page_url))
            else:
                files.append(direct_download(link, folder, referer=page_url))
        except Exception as e:
            errors.append(clean_error(e))
            say("  skipped: %s" % e)
    if not files:
        raise Failed(errors[0] if errors else "Could not download the selected items.")
    return files


def scan_page(url, text, mode):
    """Download what the page offers for this mode, or ask when there are several."""
    if not text:
        raise Failed("Could not read the page.")
    kinds = MODE_KINDS[mode]
    pool = [c for c in find_candidates(url, text) if c[0] in kinds]
    if mode == "file" and not pool:
        pool = [c for c in find_candidates(url, text) if c[0] == "image"]
    if not pool:
        raise Failed("Found nothing to download on that page.")
    if len(pool) == 1:
        return download_items(pool, url)
    pool = pool[:MENU_LIMIT]
    with open(CANDIDATES_FILE, "w", encoding="utf-8") as f:
        json.dump({"page": url, "items": pool}, f)
    with open(CHOICES_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(label_for(i, k, u) for i, (k, u) in enumerate(pool, 1)))
    raise NeedPick()


def run_pick(lines):
    try:
        with open(CANDIDATES_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        raise Failed("The list of items is gone. Run the shortcut again.")
    items = data.get("items") or []
    picked = []
    for line in lines:
        m = re.match(r"\s*(\d+)\.", line)
        if m and 1 <= int(m.group(1)) <= len(items):
            item = tuple(items[int(m.group(1)) - 1])
            if item not in picked:
                picked.append(item)
    if not picked:
        raise Failed("Nothing was selected.")
    return download_items(picked, data.get("page"))


# ---------------------------------------------------------------- main

def read_job():
    """Return (mode, payload lines, options) from the job file.

    key=value lines are settings: first the saved ones, then any chosen for
    this run, so the last one wins.
    """
    try:
        with open(JOB_FILE, encoding="utf-8") as f:
            lines = [l.strip() for l in f.read().splitlines() if l.strip()]
    except OSError:
        lines = sys.argv[1:]
    options = dict(DEFAULT_OPTIONS)
    payload = []
    for line in lines:
        m = re.match(r"^([a-z]+)=(.*)$", line)
        if m:
            options[m.group(1)] = m.group(2).strip()
        else:
            payload.append(line)
    if not payload:
        return None, [], options
    mode = payload[0].lower()
    if mode in ("pick", "playlist"):
        return mode, payload[1:], options
    rest = " ".join(payload[1:]) if mode in MODES else " ".join(payload)
    if mode not in MODES:
        mode = "video"
    m = re.search(r"https?://[^\s<>\"']+", rest)
    return mode, ([m.group(0)] if m else []), options


def run(mode, url, options=None):
    options = options or DEFAULT_OPTIONS
    page = None
    probe_error = None

    # Is the link itself a file? Then the mode does not matter.
    resp = None
    try:
        resp = open_url(url)
        ctype = (resp.headers.get_content_type() or "").lower()
        is_stream = any(t in ctype for t in STREAM_TYPES) or ext_of(resp.geturl()) in STREAM_EXT
        if ctype.startswith(HTML_TYPES):
            raw = resp.read(4 * 1024 * 1024)
            page = raw.decode(resp.headers.get_content_charset() or "utf-8", "replace")
            page_url = resp.geturl() or url
            resp.close()
        elif not is_stream:
            say("The link is a file.")
            return [direct_download(url, new_folder("direct"), resp=resp)]
        else:
            resp.close()
            page_url = url
    except Failed:
        raise
    except Exception as e:
        probe_error = str(e)
        page_url = url
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass

    tool_error = None
    if mode in ("video", "audio") and is_playlist_link(url):
        say("\nThis is a playlist.")
        ask_playlist_count(mode, url, options)
    if mode in ("video", "audio"):
        say("\nTrying yt-dlp...")
        try:
            return try_ytdlp(url, new_folder("ytdlp"), audio=(mode == "audio"), options=options)
        except Failed as e:
            tool_error = str(e)
            say("  %s" % e)
    elif mode == "gallery":
        say("\nTrying gallery-dl...")
        try:
            return try_gallerydl(url, new_folder("gallery"))
        except Failed as e:
            tool_error = str(e)
            say("  %s" % e)

    if mode in ("video", "gallery") and x_status_id(url):
        say("\nTrying FxTwitter...")
        try:
            kinds = ("video",) if mode == "video" else ("image",)
            return try_fxtwitter(url, new_folder("fxtwitter"), kinds)
        except Failed as e:
            say("  %s" % e)
            # Show FxTwitter's reason only when it is definite; otherwise
            # the downloader's own error says more.
            if isinstance(e, FxAnswer) or not tool_error:
                tool_error = str(e)

    say("\nLooking through the page...")
    try:
        return scan_page(page_url, page, mode)
    except Failed as e:
        say("  %s" % e)
        if tool_error and "Unsupported URL" not in tool_error:
            raise Failed(tool_error)
        if page is None and probe_error:
            raise Failed("Could not open the link: %s" % probe_error)
        what = {"video": "No video", "audio": "No audio", "gallery": "No images", "file": "No files"}[mode]
        raise Failed("%s found at that link." % what)


def main():
    os.makedirs(BASE, exist_ok=True)
    os.chdir(BASE)
    write_status("The download did not finish. Run the shortcut again and wait for a-Shell to return.")
    mode, args, options = read_job()
    cleanup_previous(keep_candidates=(mode in ("pick", "playlist")))
    say("AnyDL %s" % VERSION)
    try:
        if mode == "pick":
            files = publish(run_pick(args))
        elif mode == "playlist":
            run_playlist(args)
            shutil.rmtree(TMP, ignore_errors=True)
            write_status("SAVED")
            say("\nDone.")
            back_to_shortcuts()
            sys.exit(0)
        else:
            if not args:
                finish(error="No link was given.")
            say("%s: %s" % (mode, args[0]))
            check_for_update(options)
            weekly_update()
            files = publish(run(mode, args[0], options))
    except NeedPick:
        shutil.rmtree(TMP, ignore_errors=True)
        write_status("PICK")
        say("\nSeveral items found - choose in the shortcut.")
        back_to_shortcuts()
        sys.exit(0)
    except NeedPlaylistCount:
        shutil.rmtree(TMP, ignore_errors=True)
        write_status("PLAYLIST")
        say("\nChoose how many in the shortcut.")
        back_to_shortcuts()
        sys.exit(0)
    except Failed as e:
        finish(error=str(e))
    except KeyboardInterrupt:
        finish(error="Cancelled.")
    except Exception as e:
        finish(error="Unexpected error: %s" % e)
    finish(files=files)


if __name__ == "__main__":
    try:
        main()
    finally:
        # Never leave the shortcut waiting, even if something above crashed.
        back_to_shortcuts()
