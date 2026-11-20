#!/usr/bin/env python3
"""AnyDL - download whatever a link points to.

Runs inside a-Shell on iOS, started by the AnyDL shortcut. The shortcut writes
anydl_job.txt, runs this script, and reads the result back:

    anydl_job.txt      line 1: mode (video | audio | gallery | file | pick)
                       then the link, or for "pick" the chosen list entries
    anydl_status.txt   "OK", "PICK", "VIEW", or a one-line error message
    anydl_files.txt    when OK: one downloaded file name per line
    anydl_choices.txt  when PICK: one entry per line for the shortcut to list
    anydl_large.txt    when VIEW: full paths of the files saved for the preview

The script switches back to Shortcuts itself, except for "VIEW": then the
download is shown in a-Shell's own preview instead (see show_in_ashell).

What each mode tries, after first checking whether the link itself is a file:
    video    yt-dlp, then video found on the page
    audio    yt-dlp (audio only), then audio found on the page
    gallery  gallery-dl, then images found on the page
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

VERSION = "2.5"

BASE = os.environ.get("ANYDL_DIR") or os.environ.get("SHORTCUTS") or os.getcwd()
TMP = os.path.join(BASE, "anydl_tmp")
JOB_FILE = os.path.join(BASE, "anydl_job.txt")
STATUS_FILE = os.path.join(BASE, "anydl_status.txt")
LIST_FILE = os.path.join(BASE, "anydl_files.txt")
LARGE_FILE = os.path.join(BASE, "anydl_large.txt")
CHOICES_FILE = os.path.join(BASE, "anydl_choices.txt")
CANDIDATES_FILE = os.path.join(BASE, "anydl_candidates.json")
STAMP_FILE = os.path.join(BASE, "anydl_stamp.txt")

# Used only for plain page and file requests. The downloaders keep their own
# identity: forcing one on yt-dlp breaks sites such as TikTok.
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
UPDATE_EVERY = 7 * 24 * 3600
MAX_ITEMS = 25          # cap for playlists and galleries
MENU_LIMIT = 60
MODES = ("video", "audio", "gallery", "file")

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


def back_to_shortcuts():
    global _handed_off
    if not _handed_off:
        _handed_off = True
        a_shell("open shortcuts://")


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
    leftovers = [LIST_FILE, LARGE_FILE, CHOICES_FILE]
    if not keep_candidates:
        leftovers.append(CANDIDATES_FILE)
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
    text = text.strip()
    if re.search(r"NSFW|authenticat|log ?in|sign in|cookies|age.restricted|private", text, re.I):
        text += " (This post needs a logged-in account, and AnyDL has no login.)"
    return text


def looks_unmerged(files):
    """yt-dlp leaves name.f123.mp4 + name.f456.m4a behind when it cannot merge."""
    return any(re.search(r"\.f[\w-]+\.\w+$", os.path.basename(p)) for p in files)


def try_ytdlp(url, folder, audio=False, referer=None):
    yt_dlp = ensure("yt_dlp", "yt-dlp", extras=("yt-dlp-ejs", "yt-dlp-apple-webkit-jsi"))
    formats = AUDIO_FORMATS if audio else VIDEO_FORMATS
    outtmpl = os.path.join(folder, NAME_TEMPLATE)
    error = None

    for fmt, merge in formats:
        empty(folder)
        if yt_dlp is None:
            args = ["-f", fmt, "-o", outtmpl, "--no-playlist", "--playlist-end", str(MAX_ITEMS),
                    "--no-warnings", "--windows-filenames"]
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
                "noplaylist": True,
                "playlistend": MAX_ITEMS,
                "no_warnings": True,
                "retries": 3,
                "fragment_retries": 5,
                "windowsfilenames": True,
            }
            if merge:
                opts["merge_output_format"] = merge
            if referer:
                opts["http_headers"] = {"Referer": referer}
            try:
                stop_solver_navigation()
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                error = clean_error(e)
                if "Unsupported URL" in error or "DRM" in error or "No video could be found" in error:
                    break
                continue
        files = collect(folder)
        if files and not looks_unmerged(files):
            return tidy_media_names(files)
        if files:
            error = "The video and sound could not be joined (ffmpeg is missing)."
    empty(folder)
    raise Failed(error or "yt-dlp found nothing to download.")


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
    try:
        with open(JOB_FILE, encoding="utf-8") as f:
            lines = [l.strip() for l in f.read().splitlines() if l.strip()]
    except OSError:
        lines = sys.argv[1:]
    if not lines:
        return None, []
    mode = lines[0].lower()
    if mode == "pick":
        return mode, lines[1:]
    rest = " ".join(lines[1:]) if mode in MODES else " ".join(lines)
    if mode not in MODES:
        mode = "video"
    m = re.search(r"https?://[^\s<>\"']+", rest)
    return mode, ([m.group(0)] if m else [])


def run(mode, url):
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
    if mode in ("video", "audio"):
        say("\nTrying yt-dlp...")
        try:
            return try_ytdlp(url, new_folder("ytdlp"), audio=(mode == "audio"))
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
    mode, args = read_job()
    cleanup_previous(keep_candidates=(mode == "pick"))
    say("AnyDL %s" % VERSION)
    try:
        if mode == "pick":
            files = publish(run_pick(args))
        else:
            if not args:
                finish(error="No link was given.")
            say("%s: %s" % (mode, args[0]))
            weekly_update()
            files = publish(run(mode, args[0]))
    except NeedPick:
        shutil.rmtree(TMP, ignore_errors=True)
        write_status("PICK")
        say("\nSeveral items found - choose in the shortcut.")
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
