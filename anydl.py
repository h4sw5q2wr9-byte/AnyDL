#!/usr/bin/env python3
"""AnyDL - download whatever a link points to.

Runs inside a-Shell on iOS, started by the AnyDL shortcut. The shortcut writes
anydl_job.txt, runs this script, and reads the result back:

    anydl_job.txt      line 1: mode (video | audio | gallery | file | pick |
                       playlist | again | clear), then the link, or for "pick"
                       the chosen list entries, for "playlist" the amount, for
                       "again" the history number, for "clear" all or old.
                       Lines of the form key=value are settings (read_job).
    anydl_settings.txt the shortcut's saved settings, as key=value lines
    anydl_status.txt   "OK", "PICK", "PLAYLIST", "SAVED", "PHOTOS",
                       "CLEARED", "VIEW", "FILES", or a one-line error
    anydl_message.txt  when PLAYLIST, SAVED or CLEARED: text to show
    anydl_open.txt     when SAVED: a link that opens the folder in Files
    anydl_number.txt   when PLAYLIST: the question for typing an amount
    anydl_update.txt   a newer AnyDL version, once (see check_for_update)
    anydl_files.txt    when OK or PHOTOS: one file name per line, in this
                       folder, for the shortcut to fetch
    anydl_choices.txt  when PICK or PLAYLIST: one entry per line to choose from
    anydl_library.txt  a link to the AnyDL folder in Files, then a summary
    anydl_history.txt  recent downloads, newest first, one per line, with
    anydl_history_links.txt  their links in the same order

The shortcut does not wait for this script. When there is something for it
to show, the script starts AnyDL again with "anydl-return" as input (see
back_to_shortcuts). For "VIEW" it shows the download in a-Shell's own
preview instead (see show_in_ashell); for "FILES" it opens the Files app.

Downloads are kept in On My iPhone > a-Shell > AnyDL, sorted into Videos,
Audio, Photos, Files and Playlists (see the library section).

What each mode tries, after first checking whether the link itself is a file:
    video    yt-dlp, then for X posts FxTwitter, then video found on the page
    audio    yt-dlp (audio only), then audio found on the page
    gallery  gallery-dl, then for X posts FxTwitter, then images on the page
    file     documents, archives and media linked on the page
"""
import html
import importlib
import json
import math
import mimetypes
import os
import re
import shutil
import site
import ssl
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

VERSION = "3.0"

BASE = os.environ.get("ANYDL_DIR") or os.environ.get("SHORTCUTS") or os.getcwd()
TMP = os.path.join(BASE, "anydl_tmp")
JOB_FILE = os.path.join(BASE, "anydl_job.txt")
STATUS_FILE = os.path.join(BASE, "anydl_status.txt")
LIST_FILE = os.path.join(BASE, "anydl_files.txt")
LARGE_FILE = os.path.join(BASE, "anydl_large.txt")
PREVIOUS_FILE = os.path.join(BASE, "anydl_previous.txt")
CHOICES_FILE = os.path.join(BASE, "anydl_choices.txt")
CANDIDATES_FILE = os.path.join(BASE, "anydl_candidates.json")
PLAYLIST_FILE = os.path.join(BASE, "anydl_playlist.json")
MESSAGE_FILE = os.path.join(BASE, "anydl_message.txt")
OPEN_FILE = os.path.join(BASE, "anydl_open.txt")
NUMBER_FILE = os.path.join(BASE, "anydl_number.txt")
UPDATE_FILE = os.path.join(BASE, "anydl_update.txt")
UPDATE_STATE_FILE = os.path.join(BASE, "anydl_update_state.json")
STAMP_FILE = os.path.join(BASE, "anydl_stamp.txt")
LIBRARY_FILE = os.path.join(BASE, "anydl_library.txt")
HISTORY_FILE = os.path.join(BASE, "anydl_history.json")
HISTORY_LIST_FILE = os.path.join(BASE, "anydl_history.txt")
HISTORY_LINKS_FILE = os.path.join(BASE, "anydl_history_links.txt")
HISTORY_LIMIT = 30

# Used only for plain page and file requests. The downloaders keep their own
# identity: forcing one on yt-dlp breaks sites such as TikTok.
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
UPDATE_EVERY = 7 * 24 * 3600
MAX_ITEMS = 25          # cap for galleries and items found on a page
PLAYLIST_LIMIT = 100    # most videos one playlist download takes
MENU_LIMIT = 60
MODES = ("video", "audio", "gallery", "file")

# Settings, as the shortcut saves them (human-readable values; see the
# Settings part of AnyDL.cherri.in for the choices).
DEFAULT_OPTIONS = {"quality": "Best", "fps": "Any", "codec": "Most compatible",
                   "audio": "Original", "subtitles": "Off", "after": "Preview",
                   "keep": "Forever", "updates": "On"}
OPTIONS = dict(DEFAULT_OPTIONS)     # this run's settings, set by main()
JOB = {}                            # this run's link and mode, for the history

SUBTITLE_LANGUAGES = {
    "english": "en", "dutch": "nl", "german": "de", "french": "fr", "spanish": "es",
    "portuguese": "pt", "italian": "it", "polish": "pl", "turkish": "tr",
    "arabic": "ar", "hindi": "hi", "indonesian": "id", "japanese": "ja",
    "korean": "ko", "chinese": "zh",
}
KEEP_DAYS = {"1 day": 1, "1 week": 7, "1 month": 30}


def quality_height(quality):
    """The short side a quality setting allows, or None for Best."""
    q = (quality or "").lower()
    if "4k" in q:
        return 2160
    if "data saver" in q:
        return 360
    m = re.search(r"(\d{3,4})p", q)
    return int(m.group(1)) if m else None


def fps_limit(setting):
    m = re.search(r"(\d+)\s*fps", (setting or "").lower())
    return int(m.group(1)) if m else None

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
TYPE_FOLDERS = {"video": "Videos", "audio": "Audio", "image": "Photos", "file": "Files"}
# A cookies.txt exported from a browser where you are signed in to YouTube
# (Netscape format). Optional; see "YouTube says I'm a bot" in the README.
COOKIES_FILE = os.path.join(VISIBLE_DIR, "cookies.txt")
BOT_FIX_STAMP = os.path.join(BASE, "anydl_botfix.txt")

# When YouTube answers "Sign in to confirm you're not a bot" for yt-dlp's
# default player types (tv_samsung, visionos, web), these are tried next.
# None of them needs a GVS PO token for its formats (web_safari and mweb
# only for their HLS formats), which AnyDL cannot generate on iOS.
YOUTUBE_FALLBACK_CLIENTS = [["tv", "web_safari"], ["web_embedded", "tv_downgraded"], ["mweb"]]
BOT_CHECK = re.compile(r"confirm you.re not a bot|LOGIN_REQUIRED", re.I)
PLAYLISTS_FOLDER = "Playlists"

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


# ---------------------------------------------------------------- terminal
#
# a-Shell's terminal is narrow on an iPhone (about 40 columns upright), and a
# line that wraps can no longer be redrawn in place, which made progress
# jump. Everything here is sized to the terminal width, the screen is
# cleared at the start, and a short summary closes every run.

NOTES = []          # lines for the summary at the end of the run


def width():
    try:
        return max(30, min(72, shutil.get_terminal_size((40, 20)).columns))
    except Exception:
        return 40


def wrap(text, indent="  ", then="  "):
    for line in textwrap.wrap(text, width() - 1, initial_indent=indent,
                              subsequent_indent=then) or [indent]:
        say(line)


def rule():
    say("─" * (width() - 1))


def start_screen(title, subtitle=""):
    """A clean screen for each run, so the terminal never fills up."""
    sys.stdout.write("\033[2J\033[3J\033[H")
    sys.stdout.flush()
    a_shell("hideKeyboard")
    say("AnyDL %s · %s" % (VERSION, title))
    if subtitle:
        say(subtitle[:width() - 1])
    rule()


def note(text):
    NOTES.append(text)


def short_size(size):
    mb = size / 1e6
    if mb >= 100:
        return "%d MB" % round(mb)
    if mb >= 1:
        return "%.1f MB" % mb
    return "%d KB" % max(1, round(size / 1e3))


def short_time(seconds):
    """Remaining time, rounded more coarsely the longer it is, so it does
    not flicker: 7s, 25s, 1m 10s, 12m."""
    seconds = max(0, seconds)
    if seconds < 10:
        return "%ds" % math.ceil(seconds)
    if seconds < 60:
        return "%ds" % (5 * math.ceil(seconds / 5))
    if seconds < 600:
        rounded = 10 * math.ceil(seconds / 10)
        return "%dm %02ds" % divmod(rounded, 60)
    return "%dm" % math.ceil(seconds / 60)


class Progress:
    """One progress line, redrawn in place.

    The speed is averaged over a few seconds (an exponential moving
    average), so the remaining time counts down smoothly instead of jumping
    with every chunk, and a small rise is ignored so it never flickers.
    """

    def __init__(self, label):
        self.label = label
        self.start = self.last = time.time()
        self.done = 0
        self.speed = None
        self.shown_eta = None
        self.drawn = 0.0
        self.finished = False

    def update(self, done, total=None):
        now = time.time()
        dt = now - self.last
        if dt >= 0.2 and done >= self.done:
            rate = (done - self.done) / dt
            weight = 1 - math.exp(-dt / 3.0)
            self.speed = rate if self.speed is None else self.speed + weight * (rate - self.speed)
            self.last, self.done = now, done
        elif self.done == 0:
            self.done = done
        if now - self.drawn < 0.5 and not (total and done >= total):
            return
        self.drawn = now
        self.draw(done, total, now)

    def draw(self, done, total, now):
        label = "%-5s" % self.label[:5]
        if total:
            pct = min(100, int(done * 100 / total))
            eta = "…"
            if self.speed and now - self.start > 1.5:
                seconds = (total - done) / self.speed
                if self.shown_eta is None or seconds < self.shown_eta or seconds > self.shown_eta * 1.25 + 3:
                    self.shown_eta = seconds
                eta = short_time(self.shown_eta)
            total_text = short_size(total)
            number, unit = total_text.split()
            scale = {"MB": 1e6, "KB": 1e3}[unit]
            done_text = ("%d" if "." not in number else "%.1f") % (done / scale)
            sizes = "%s/%s" % (done_text.rjust(len(number)), total_text)
            if not getattr(self, "bar_len", None):
                # Fixed for the whole download, sized for the longest line,
                # so the bar does not wobble as the numbers change.
                longest = len(label) + len(" 100% ") + len(" %s %s" % (sizes, "10m 00s"))
                self.bar_len = max(4, min(16, width() - 1 - longest))
            filled = int(self.bar_len * pct / 100)
            line = "%s %3d%% %s %s %s" % (label, pct, "█" * filled + "░" * (self.bar_len - filled),
                                          sizes, eta)
        else:
            speed = (" · %s/s" % short_size(self.speed)) if self.speed else ""
            line = "%s %s%s" % (label, short_size(done), speed)
        line = line[:width() - 1]
        sys.stdout.write("\r" + line + " " * max(0, width() - 1 - len(line)))
        sys.stdout.flush()

    def finish(self, done=None, total=None):
        if self.finished:
            return
        self.finished = True
        done = done or self.done
        took = time.time() - self.start
        line = "%-5s %s in %s" % (self.label[:5], short_size(done), short_time(took).replace("~", ""))
        sys.stdout.write("\r" + line[:width() - 1] + " " * max(0, width() - 1 - len(line)) + "\n")
        sys.stdout.flush()


FRIENDLY_ERRORS = [
    (r"confirm you.re not a bot", "YouTube thinks this is a bot. AnyDL already tried other ways. "
                                  "Wait a few minutes, switch between Wi-Fi and mobile data, "
                                  "or turn off any VPN, then try again. If it keeps happening, set up "
                                  "YouTube sign-in: Settings › YouTube sign-in."),
    (r"429|too many requests", "The site says there were too many requests. Wait a few minutes, "
                               "then try again."),
    (r"confirm your age|age.restricted|inappropriate for some users",
     "This video is age-restricted and needs a signed-in account, which AnyDL does not have."),
    (r"private video|this video is private", "This video is private."),
    (r"members.only|join this channel", "This video is only for the channel's members."),
    (r"video unavailable|this video is not available|has been removed",
     "This video is unavailable: removed, private, or blocked in your country."),
    (r"not available in your country|geo.?restrict", "This video is blocked in your country."),
    (r"premieres in|live event will begin|is upcoming", "This video has not been released yet."),
    (r"No video could be found|no video formats found", "No video found in this post or page."),
    (r"\bDRM\b", "This video is copy-protected (DRM) and cannot be downloaded."),
    (r"HTTP Error 403|Forbidden", "The site refused the download. Try again; if it keeps happening "
                                  "the site may have changed, and AnyDL updates its tools weekly."),
    (r"HTTP Error 404|not found", "The link leads nowhere (not found). Check that it is complete."),
    (r"No space left|Errno 28", "Your iPhone is out of storage."),
    (r"Unable to download webpage|timed out|Network is unreachable|Name or service not known|"
     r"nodename nor servname|Connection (refused|reset)", "Could not reach the site. Check your "
                                                          "internet connection and try again."),
]


def first_sentence(text):
    m = re.match(r"(.+?[.!?])(\s|$)", text or "")
    return m.group(1) if m else text


def friendly_error(text):
    """A short explanation for common failures; otherwise the error itself."""
    for pattern, message in FRIENDLY_ERRORS:
        if re.search(pattern, text or "", re.I):
            return message
    return text


def write_status(text):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def finish(files=None, error=None):
    """Put the downloads in the library, show or hand them over, then exit.

    What happens depends on the After download setting: a preview (in
    a-Shell for one file or a large one, in Shortcuts for several small
    files), saving to Photos (done by the shortcut, so only for photos and
    videos small enough to hand over), or only keeping them in Files.
    """
    shutil.rmtree(TMP, ignore_errors=True)
    if not files:
        detail = re.sub(r"\s+", " ", error or "Nothing was downloaded.").strip()[:400]
        status = friendly_error(detail)
        say()
        rule()
        wrap("✗ " + status, indent="", then="  ")
        if status != detail:
            wrap(detail)
        write_status(status)
        write_library_summary()
        back_to_shortcuts()
        sys.exit(0)

    after = (OPTIONS.get("after") or "").lower()
    large = any(os.path.getsize(p) > LARGE_BYTES for p in files)
    media_only = all(kind_of(p) in ("video", "image") for p in files)
    if after.startswith("save to photos"):
        if media_only and not large:
            saved = [to_library(p, keep_original=True) for p in files]
            write_list(files)
            write_status("PHOTOS")
            finish_run(saved, "Saving to Photos…")
            back_to_shortcuts()
            sys.exit(0)
        note("Not saved to Photos automatically (%s): use the share button in the preview."
             % ("over 50 MB" if large else "not a photo or video"))

    if after.startswith("keep in files"):
        saved = [to_library(p) for p in files]
        write_status("FILES")
        folder = os.path.dirname(saved[0])
        finish_run(saved, "Opening the folder in Files…")
        global _handed_off
        _handed_off = True
        a_shell("open " + files_link(folder))
        sys.exit(0)

    if len(files) == 1 or large:
        shown = [to_library(p) for p in files]
        write_status("VIEW")
        finish_run(shown, "Opening the preview. If an older one is still open, tap Done on "
                          "it: a-Shell shows one preview at a time.")
        show_in_ashell(max(shown, key=os.path.getsize))
        sys.exit(0)

    saved = [to_library(p, keep_original=True) for p in files]
    write_list(files)
    write_status("OK")
    finish_run(saved, "Showing them in Shortcuts…")
    back_to_shortcuts()
    sys.exit(0)


def write_list(files):
    with open(LIST_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(os.path.basename(p) for p in files))


def finish_run(saved, next_step):
    """The summary at the end of a successful run, then the bookkeeping."""
    total = sum(os.path.getsize(p) for p in saved if os.path.exists(p))
    folder = os.path.relpath(os.path.dirname(saved[0]), VISIBLE_DIR)
    say()
    rule()
    say("✓ %s · %s" % ("1 file" if len(saved) == 1 else "%d files" % len(saved), short_size(total)))
    for line in NOTES:
        wrap(line)
    wrap("In Files › a-Shell › AnyDL › %s" % folder)
    wrap(next_step)
    title = os.path.splitext(os.path.basename(saved[0]))[0]
    title = re.sub(r" \(\d+\)$", "", title)       # copy number, not part of the name
    if len(saved) > 1:
        title += " and %d more" % (len(saved) - 1)
    record_history(title, len(saved), os.path.dirname(saved[0]))
    write_library_summary()


# ---------------------------------------------------------------- library

def kind_of(path):
    ext = ext_of(path)
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in IMAGE_EXT:
        return "image"
    return "file"


def unique_path(folder, name):
    stem, ext = os.path.splitext(name)
    dest = os.path.join(folder, name)
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(folder, "%s (%d)%s" % (stem, n, ext))
        n += 1
    return dest


def to_library(src, keep_original=False):
    """Move (or copy) a download into its type folder in the library."""
    folder = os.path.join(VISIBLE_DIR, TYPE_FOLDERS[kind_of(src)])
    os.makedirs(folder, exist_ok=True)
    dest = unique_path(folder, os.path.basename(src))
    if keep_original:
        shutil.copy2(src, dest)
    else:
        shutil.move(src, dest)
    os.utime(dest)      # "Keep downloads" counts from the download, not the upload
    return dest


def files_link(path):
    """A link that opens a folder in the Files app."""
    return "shareddocuments://" + urllib.parse.quote(os.path.realpath(path))


def migrate_library():
    """Sort downloads from before 3.0, which sat loose in the AnyDL folder."""
    if not os.path.isdir(VISIBLE_DIR):
        return
    keep = set(TYPE_FOLDERS.values()) | {PLAYLISTS_FOLDER}
    for name in os.listdir(VISIBLE_DIR):
        path = os.path.join(VISIBLE_DIR, name)
        if name.startswith(".") or name in keep or name == "cookies.txt":
            continue
        try:
            if os.path.isfile(path):
                folder = os.path.join(VISIBLE_DIR, TYPE_FOLDERS[kind_of(path)])
            else:
                folder = os.path.join(VISIBLE_DIR, PLAYLISTS_FOLDER)   # 2.8 playlists
            os.makedirs(folder, exist_ok=True)
            shutil.move(path, unique_path(folder, name))
        except OSError:
            pass


def library_files(older_than_days=None):
    found = []
    if not os.path.isdir(VISIBLE_DIR):
        return found
    cutoff = time.time() - older_than_days * 86400 if older_than_days else None
    for root, _dirs, names in os.walk(VISIBLE_DIR):
        for name in names:
            if name.startswith(".") or (root == VISIBLE_DIR and name == "cookies.txt"):
                continue
            path = os.path.join(root, name)
            try:
                if cutoff is None or os.path.getmtime(path) < cutoff:
                    found.append(path)
            except OSError:
                pass
    return found


def delete_files(paths):
    """Delete files and any playlist folders left empty. Returns (count, bytes)."""
    count = size = 0
    for path in paths:
        try:
            size += os.path.getsize(path)
            os.remove(path)
            count += 1
        except OSError:
            pass
    playlists = os.path.join(VISIBLE_DIR, PLAYLISTS_FOLDER)
    if os.path.isdir(playlists):
        for name in os.listdir(playlists):
            folder = os.path.join(playlists, name)
            if os.path.isdir(folder) and not os.listdir(folder):
                try:
                    os.rmdir(folder)
                except OSError:
                    pass
    return count, size


def prune_library():
    """Delete downloads older than the Keep downloads setting allows."""
    days = KEEP_DAYS.get((OPTIONS.get("keep") or "").lower())
    if days:
        count, size = delete_files(library_files(older_than_days=days))
        if count:
            say("Removed %d download%s older than %s (%s)." % (
                count, "" if count == 1 else "s", OPTIONS.get("keep"), human_size(size)))


def human_size(size):
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return ("%d %s" % (size, unit)) if unit == "bytes" else ("%.1f %s" % (size, unit))
        size /= 1024.0


def write_library_summary():
    files = library_files()
    size = sum(os.path.getsize(p) for p in files if os.path.exists(p))
    summary = ("%d file%s · %s" % (len(files), "" if len(files) == 1 else "s", human_size(size))
               if files else "No downloads yet")
    os.makedirs(VISIBLE_DIR, exist_ok=True)
    for folder in list(TYPE_FOLDERS.values()) + [PLAYLISTS_FOLDER]:
        os.makedirs(os.path.join(VISIBLE_DIR, folder), exist_ok=True)
    signed_in = "cookies.txt found" if os.path.exists(COOKIES_FILE) else "Not set up"
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        f.write(files_link(VISIBLE_DIR) + "\n" + summary + "\n" + signed_in)


def clear_library(which):
    old = "old" in which.lower()
    count, size = delete_files(library_files(older_than_days=7 if old else None))
    what = "older than a week" if old else ""
    message = ("Deleted %d download%s %s(%s)." % (count, "" if count == 1 else "s",
                                                   what + " " if what else "", human_size(size))
               if count else "There was nothing to delete.")
    with open(MESSAGE_FILE, "w", encoding="utf-8") as f:
        f.write(message)
    say(message)


# ---------------------------------------------------------------- history

def load_history():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            entries = json.load(f)
        return entries if isinstance(entries, list) else []
    except (OSError, ValueError):
        return []


def record_history(title, count, folder):
    if not JOB.get("url"):
        return
    entries = load_history()
    entries.insert(0, {"title": title, "url": JOB["url"], "mode": JOB.get("mode", "video"),
                       "count": count, "when": time.time(), "folder": folder})
    entries = entries[:HISTORY_LIMIT]
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f)
    except OSError:
        return
    write_history_lists(entries)


def write_history_lists(entries):
    labels = []
    for n, e in enumerate(entries, 1):
        when = time.strftime("%d %b", time.localtime(e.get("when", 0))).lstrip("0")
        labels.append("%d. %s · %s · %s" % (n, (e.get("title") or "Download")[:60],
                                            (e.get("mode") or "video").capitalize(), when))
    with open(HISTORY_LIST_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(labels))
    with open(HISTORY_LINKS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(e.get("url", "") for e in entries))


def history_entry(lines):
    m = re.search(r"(\d+)", " ".join(lines))
    entries = load_history()
    if not m or not 1 <= int(m.group(1)) <= len(entries):
        raise Failed("That download is no longer in the history.")
    return entries[int(m.group(1)) - 1]


def cleanup_previous(keep_candidates=False):
    """Delete the copies left in this folder for the shortcut to fetch, and
    the previous run's status files. Downloads in the library stay; the
    Keep downloads setting decides how long (see prune_library)."""
    if os.path.exists(LIST_FILE):
        try:
            with open(LIST_FILE, encoding="utf-8") as f:
                for line in f.read().splitlines():
                    name = os.path.basename(line.strip())
                    path = os.path.join(BASE, name)
                    if name and not name.startswith("anydl") and os.path.isfile(path):
                        os.remove(path)
        except OSError:
            pass
    leftovers = [LIST_FILE, LARGE_FILE, PREVIOUS_FILE, CHOICES_FILE, MESSAGE_FILE,
                 OPEN_FILE, NUMBER_FILE]
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
    bar = Progress(kind_of(dest).replace("image", "photo").capitalize())
    with open(dest, "wb") as f:
        while True:
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            bar.update(done, total or None)
    bar.finish(done)
    if total and done < total:
        raise Failed("The download stopped early (%d of %d bytes)." % (done, total))
    if done == 0:
        raise Failed("The server sent an empty file.")
    return dest


def direct_download(url, folder, resp=None, referer=None, show_name=True):
    if resp is None:
        resp = open_url(url, referer=referer)
    with resp:
        name = name_from_response(resp, url)
        if show_name:
            say(name[:width() - 1])
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
    say("First time: installing %s. This can take a minute…" % package)
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
    say("Updating the download tools (weekly)…")
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


def video_formats(quality, fps=None, codec=None):
    """yt-dlp format choices for the Video quality, Frame rate and Video
    format settings, best first, as [(format, merge into)].

    Quality means the short side of the picture, so an upright video (TikTok,
    Shorts) of 720x1280 counts as 720p. yt-dlp's filters cannot take the
    smaller of two fields, so wide and upright formats get their own filter.
    "Most compatible" prefers H.264 (avc1), which plays everywhere, including
    Photos; YouTube only offers it up to 1080p. "Highest quality" takes any
    codec (VP9, AV1). When nothing meets the limits: without a frame-rate
    match the frame rate is let go; without a size match the smallest
    available is taken.
    """
    limit = quality_height(quality)
    cap = fps_limit(fps)
    any_codec = "highest" in (codec or "").lower()
    if not limit and not cap and not any_codec:
        return VIDEO_FORMATS
    sides = (("[aspect_ratio>=?1][height<=?%d]" % limit,     # wide, or size unknown
              "[aspect_ratio<1][width<=?%d]" % limit)        # upright
             if limit else ("",))

    def alternatives(pieces, rate):
        return "/".join(piece.format(side + rate) for piece in pieces for side in sides)

    if any_codec:
        merged_pieces = ("bv*{0}+ba[ext=m4a]", "bv*{0}+ba", "b{0}")
    else:
        merged_pieces = ("bv*{0}[vcodec^=avc1]+ba[ext=m4a]", "b{0}[ext=mp4]", "bv*{0}+ba", "b{0}")
    single_pieces = ("b{0}[ext=mp4]", "b{0}")
    rates = (["[fps<=?%d]" % cap] if cap else []) + [""]
    tail = "/w" if limit else "/b"
    merged = "/".join(alternatives(merged_pieces, r) for r in rates) + tail
    single = "/".join(alternatives(single_pieces, r) for r in rates) + tail
    return [(merged, "mp4"), (single, None)]


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
    text = re.sub(r"^\[[\w:.-]+\]\s*(?:[\w.-]+:\s+)?", "", text.strip())   # "[twitter] 123: "
    text = text.strip()
    if (re.search(r"NSFW|authenticat|log ?in|sign in|cookies|age.restricted|private", text, re.I)
            and not BOT_CHECK.search(text)):
        text += " (This post needs a logged-in account, and AnyDL has no login.)"
    return text


def looks_unmerged(files):
    """yt-dlp leaves name.f123.mp4 + name.f456.m4a behind when it cannot merge."""
    return any(re.search(r"\.f[\w-]+\.\w+$", os.path.basename(p)) for p in files)


CODEC_NAMES = {"avc1": "H.264", "avc3": "H.264", "h264": "H.264", "hev1": "HEVC", "hvc1": "HEVC",
               "h265": "HEVC", "hevc": "HEVC", "vp9": "VP9", "vp09": "VP9", "av01": "AV1"}
SUBTITLE_EXT = {"vtt", "srt", "ass", "ttml", "srv1", "srv2", "srv3", "json3", "lrc"}

STEP_MESSAGES = {
    "Merger": "Joining video and sound…",
    "EmbedSubtitle": "Adding subtitles…",
    "ExtractAudio": "Converting to MP3…",
    "EmbedThumbnail": "Adding the cover image…",
}


class QuietLog:
    """yt-dlp's messages, kept out of the terminal; AnyDL shows its own."""

    def __init__(self):
        self.warnings = []
        self.errors = []

    def debug(self, msg):
        pass

    info = debug

    def warning(self, msg):
        self.warnings.append(msg)

    def error(self, msg):
        self.errors.append(msg)


def ytdlp_hooks(audio):
    """Progress and step hooks that draw AnyDL's own progress lines."""
    bars = {}
    seen = {"title": None, "steps": set()}

    def show_title(info):
        title = info.get("title")
        index = info.get("playlist_index")
        key = (title, index)
        if title and key != seen["title"]:
            seen["title"] = key
            count = info.get("n_entries") or info.get("playlist_count")
            prefix = ("%s/%s " % (index, count)) if index and count else ""
            say((prefix + nice_title(title, ""))[:width() - 1] or prefix.strip())

    def before_download(info, incomplete=False):
        # yt-dlp asks this before each video, so the title comes first.
        if not incomplete:
            show_title(info)
        return None

    def progress(d):
        info = d.get("info_dict") or {}
        show_title(info)
        name = d.get("filename") or d.get("tmpfilename") or ""
        if ext_of(name) in SUBTITLE_EXT:
            label = "Subs"
        elif info.get("vcodec") == "none":
            label = "Sound" if not audio else "Audio"
        elif info.get("acodec") == "none":
            label = "Video"
        else:
            label = "Audio" if audio else "Video"
        bar = bars.get(name)
        if bar is None:
            bar = bars[name] = Progress(label)
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        if d.get("status") == "downloading":
            bar.update(d.get("downloaded_bytes") or 0, total)
        elif d.get("status") == "finished":
            bar.finish(d.get("downloaded_bytes") or d.get("total_bytes") or bar.done)

    def step(d):
        message = STEP_MESSAGES.get(d.get("postprocessor"))
        if d.get("status") == "started" and message and message not in seen["steps"]:
            seen["steps"].add(message)
            say(message)

    return progress, step, before_download


def is_youtube(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host.endswith(("youtube.com", "youtu.be", "youtube-nocookie.com"))


def cookie_file():
    """The user's cookies.txt, if there is one that looks like the right kind."""
    try:
        with open(COOKIES_FILE, encoding="utf-8", errors="replace") as f:
            head = f.read(4096)
    except OSError:
        return None
    if "\t" in head or "Netscape HTTP Cookie File" in head:
        return COOKIES_FILE
    note("cookies.txt is not in the right format (Netscape cookies.txt), so it was not used.")
    return None


def refresh_ytdlp_after_bot_check():
    """YouTube's bot checks change often and yt-dlp's fixes reach its newest
    (pre-release) builds first, so update to those, at most every 6 hours."""
    try:
        with open(BOT_FIX_STAMP) as f:
            if time.time() - float(f.read().strip() or 0) < 6 * 3600:
                return False
    except (OSError, ValueError):
        pass
    say("Updating yt-dlp to its newest build…")
    ok = _pip(["--upgrade", "--pre", "yt-dlp"])
    try:
        with open(BOT_FIX_STAMP, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass
    return ok


def try_ytdlp(url, folder, audio=False, referer=None, options=None, playlist=0):
    """Download with yt-dlp. playlist > 0 downloads that many playlist items."""
    options = options or OPTIONS
    yt_dlp = ensure("yt_dlp", "yt-dlp", extras=("yt-dlp-ejs", "yt-dlp-apple-webkit-jsi"))
    formats = (AUDIO_FORMATS if audio else
               video_formats(options.get("quality"), options.get("fps"), options.get("codec")))
    ffmpeg = yt_dlp is not None and have_ffmpeg()
    if yt_dlp is not None and not ffmpeg and not audio:
        # Without ffmpeg, separate video and sound streams cannot be joined,
        # which limits some sites (YouTube above 360p) to lower quality.
        formats = [f for f in formats if not f[1]] or formats
        note("ffmpeg is not available, so this may be lower quality than you chose.")
    mp3 = audio and (options.get("audio") or "").lower() == "mp3"
    if mp3 and not ffmpeg:
        note("ffmpeg is not available, so the audio kept its original format.")
        mp3 = False
    language = SUBTITLE_LANGUAGES.get((options.get("subtitles") or "").lower())
    subtitles = bool(language) and not audio
    if subtitles and not ffmpeg:
        note("Subtitles: ffmpeg is not available, so they could not be added.")
        subtitles = False
    outtmpl = os.path.join(folder, NAME_TEMPLATE)
    error = None
    cookies = cookie_file()
    if cookies:
        note("Signed in with your cookies.txt.")
    fallbacks = [list(c) for c in YOUTUBE_FALLBACK_CLIENTS] if is_youtube(url) else []
    clients = None
    attempts = [(fmt, merge, cover) for fmt, merge in formats for cover in ((True, False) if mp3 else (False,))]

    i = 0
    while i < len(attempts):
        fmt, merge, cover = attempts[i]
        empty(folder)
        if yt_dlp is None:
            args = ["-f", fmt, "-o", outtmpl, "--no-warnings", "--windows-filenames",
                    "--concurrent-fragments", "4"]
            args += (["--yes-playlist", "--playlist-end", str(playlist), "--ignore-errors"]
                     if playlist else ["--no-playlist"])
            if merge:
                args += ["--merge-output-format", merge]
            if subtitles:
                args += ["--write-subs", "--write-auto-subs", "--sub-langs",
                         "%s(-(?!orig).*)?" % language, "--embed-subs"]
            if referer:
                args += ["--referer", referer]
            if cookies:
                args += ["--cookies", cookies]
            if clients:
                args += ["--extractor-args", "youtube:player_client=%s" % ",".join(clients)]
            py = sys.executable or "python3"
            if not _run_tool(["yt-dlp", [py, "-m", "yt_dlp"]], args + [url]):
                error = "yt-dlp could not download this link."
        else:
            log = QuietLog()
            progress_hook, step_hook, title_hook = ytdlp_hooks(audio)
            opts = {
                "format": fmt,
                "outtmpl": outtmpl,
                "noplaylist": not playlist,
                "quiet": True,
                "noprogress": True,
                "logger": log,
                "progress_hooks": [progress_hook],
                "postprocessor_hooks": [step_hook],
                "match_filter": title_hook,
                "retries": 3,
                "fragment_retries": 5,
                "concurrent_fragment_downloads": 4,
                "windowsfilenames": True,
                "postprocessors": [],
            }
            if playlist:
                opts["playlistend"] = playlist
                opts["ignoreerrors"] = True     # one broken video should not stop the rest
            if merge:
                opts["merge_output_format"] = merge
            if mp3:
                opts["postprocessors"] += mp3_postprocessors(cover)
                opts["writethumbnail"] = cover
            if subtitles:
                # "en" and regional variants ("en-GB"), but not YouTube's raw
                # "en-orig", which would add the same subtitles twice. The
                # track is marked as the default one for Apple's players.
                opts.update(writesubtitles=True, writeautomaticsub=True,
                            subtitleslangs=["%s(-(?!orig).*)?" % language],
                            postprocessor_args={"embedsubtitle": ["-disposition:s:0", "default"]})
                opts["postprocessors"].append(
                    {"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})
            if referer:
                opts["http_headers"] = {"Referer": referer}
            if cookies:
                opts["cookiefile"] = cookies
            if clients:
                opts["extractor_args"] = {"youtube": {"player_client": clients}}
            try:
                stop_solver_navigation()
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url) or {}
                if not audio and not playlist and info.get("width") and info.get("height"):
                    fps = (" · %d fps" % round(info["fps"])) if info.get("fps") else ""
                    codec = CODEC_NAMES.get((info.get("vcodec") or "").split(".")[0], "")
                    note("%dp%s%s" % (min(info["width"], info["height"]), fps,
                                      (" · " + codec) if codec else ""))
                if subtitles and not playlist:
                    wanted = options.get("subtitles")
                    if info.get("requested_subtitles"):
                        note("Subtitles: %s added. Turn them on with the captions button "
                             "while the video plays." % wanted)
                    else:
                        note("Subtitles: this video has no %s subtitles%s. Tip: iOS 27 can "
                             "make its own; tap the captions button while it plays." % (
                                 wanted, " that YouTube lets downloaders get"
                                 if "youtube" in (info.get("extractor") or "").lower() else ""))
            except Exception as e:
                error = clean_error(e)
                if BOT_CHECK.search(error) and fallbacks:
                    # Another kind of YouTube player often gets through.
                    clients = fallbacks.pop(0)
                    say("YouTube bot check: trying %d of %d…" % (
                        len(YOUTUBE_FALLBACK_CLIENTS) - len(fallbacks), len(YOUTUBE_FALLBACK_CLIENTS)))
                    continue
                if BOT_CHECK.search(error):
                    refresh_ytdlp_after_bot_check()
                    break
                if subtitles and "subtitle" in error.lower():
                    # Subtitles are a bonus; never let them stop the download.
                    say("The subtitles failed; downloading without them.")
                    note("Subtitles: %s could not be downloaded (%s)." % (
                        options.get("subtitles"), friendly_error(error).rstrip(".")))
                    subtitles = False
                    continue
                if "Unsupported URL" in error or "DRM" in error or "No video could be found" in error:
                    break
                i += 1
                continue
        files = collect(folder)
        # Leftover cover images and subtitle files are not downloads.
        if mp3 or audio:
            files = [f for f in files if ext_of(f) not in IMAGE_EXT] or files
        files = [f for f in files if ext_of(f) not in SUBTITLE_EXT] or files
        if mp3 and files and not all(f.lower().endswith(".mp3") for f in files):
            error = "The audio could not be converted to MP3."
            i += 1
            continue
        if files and not looks_unmerged(files):
            return tidy_media_names(files)
        if files:
            error = "The video and sound could not be joined (ffmpeg is missing)."
        i += 1
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
    if cookie_file():
        opts["cookiefile"] = COOKIES_FILE
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
        json.dump({"url": url, "mode": mode, "title": title, "options": dict(options),
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
    say("%d from %s" % (amount, title))
    files = try_ytdlp(job["url"], new_folder("playlist"), audio=(job.get("mode") == "audio"),
                      options=job.get("options"), playlist=amount)
    folder = os.path.join(VISIBLE_DIR, PLAYLISTS_FOLDER, safe_name(title, "Playlist"))
    n = 2
    base = folder
    while os.path.exists(folder):
        folder = "%s (%d)" % (base, n)
        n += 1
    os.makedirs(folder)
    for src in files:
        dest = os.path.join(folder, os.path.basename(src))
        shutil.move(src, dest)
        os.utime(dest)
    what = "video" if job.get("mode") == "video" else "track"
    what += "" if len(files) == 1 else "s"
    missing = amount - len(files)
    note = (" %d could not be downloaded." % missing) if missing > 0 else ""
    with open(MESSAGE_FILE, "w", encoding="utf-8") as f:
        f.write("Saved %d %s in Files › On My iPhone › a-Shell › AnyDL › Playlists › %s.%s"
                % (len(files), what, os.path.basename(folder), note))
    with open(OPEN_FILE, "w", encoding="utf-8") as f:
        f.write(files_link(folder))
    JOB.update(url=job["url"], mode=job.get("mode", "video"))
    record_history(os.path.basename(folder), len(files), folder)
    write_library_summary()
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
    config.set(("output",), "mode", "null")       # AnyDL shows its own summary
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
            sizes = []
            for option in (video.get("formats") or video.get("variants") or []):
                link = option.get("url") or ""
                m = re.search(r"/(\d+)x(\d+)/", link)
                if m and ".mp4" in link:
                    sizes.append((min(int(m.group(1)), int(m.group(2))), link))
            if sizes:
                found.append(("video", sizes))
            elif video.get("url"):
                found.append(("video", video["url"]))
        for photo in media.get("photos") or []:
            if photo.get("url"):
                found.append(("image", photo["url"]))
        if found:
            return source, found
    return post, found


def pick_size(sizes, quality):
    """From [(short side, link)], the largest within the quality setting, or
    else the smallest; the largest of all for Best."""
    sizes = sorted(sizes)
    limit = quality_height(quality)
    if not limit:
        return sizes[-1][1]
    fitting = [s for s in sizes if s[0] <= limit]
    return (fitting[-1] if fitting else sizes[0])[1]


def try_fxtwitter(url, folder, kinds, quality=None):
    post_id = x_status_id(url)
    if not post_id:
        raise Failed("Not an X post.")
    post, media = fxtwitter_media(post_id)
    items = [link if isinstance(link, str) else pick_size(link, quality)
             for kind, link in media if kind in kinds][:MAX_ITEMS]
    if not items:
        raise FxAnswer("No %s found in this post." % ("video" if "video" in kinds else "images"))
    author = post.get("author") or {}
    base = media_name(author.get("name") or author.get("screen_name") or "",
                      post.get("text") or "", "Twitter", post.get("id") or post_id)
    say(base[:width() - 1])
    for link in items:
        m = re.search(r"/(\d+)x(\d+)/", link)
        if m:
            note("%dp · H.264" % min(int(m.group(1)), int(m.group(2))))
            break
    files = []
    for n, link in enumerate(items, 1):
        path = direct_download(link, folder, show_name=False)
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
        json.dump({"page": url, "items": pool, "mode": mode}, f)
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
    JOB.update(url=data.get("page"), mode=data.get("mode") or "file")
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
    lines = [l.lstrip("\ufeff") for l in lines]
    for line in lines:
        m = re.match(r"^([a-z]+)=(.*)$", line)
        if m:
            options[m.group(1)] = m.group(2).strip()
        else:
            payload.append(line)
    if not payload:
        return None, [], options
    mode = payload[0].lower()
    if mode in ("pick", "playlist", "again", "clear"):
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
        say("This is a playlist. Counting…")
        ask_playlist_count(mode, url, options)
    if mode in ("video", "audio"):
        say("Looking up the %s…" % ("audio" if mode == "audio" else "video"))
        try:
            return try_ytdlp(url, new_folder("ytdlp"), audio=(mode == "audio"), options=options)
        except Failed as e:
            tool_error = str(e)
            wrap(first_sentence(friendly_error(str(e))))
    elif mode == "gallery":
        say("Looking up the images…")
        try:
            return try_gallerydl(url, new_folder("gallery"))
        except Failed as e:
            tool_error = str(e)
            wrap(first_sentence(friendly_error(str(e))))

    if mode in ("video", "gallery") and x_status_id(url):
        say("Trying another way (FxTwitter)…")
        try:
            kinds = ("video",) if mode == "video" else ("image",)
            return try_fxtwitter(url, new_folder("fxtwitter"), kinds, options.get("quality"))
        except Failed as e:
            wrap(first_sentence(friendly_error(str(e))))
            # Show FxTwitter's reason only when it is definite; otherwise
            # the downloader's own error says more.
            if isinstance(e, FxAnswer) or not tool_error:
                tool_error = str(e)

    if tool_error and is_youtube(url):
        raise Failed(tool_error)        # a YouTube page has nothing else to find
    say("Looking through the page…")
    try:
        return scan_page(page_url, page, mode)
    except Failed as e:
        wrap(first_sentence(friendly_error(str(e))))
        if tool_error and "Unsupported URL" not in tool_error:
            raise Failed(tool_error)
        if page is None and probe_error:
            raise Failed("Could not open the link: %s" % probe_error)
        what = {"video": "No video", "audio": "No audio", "gallery": "No images", "file": "No files"}[mode]
        raise Failed("%s found at that link." % what)


def main():
    global OPTIONS
    os.makedirs(BASE, exist_ok=True)
    os.chdir(BASE)
    write_status("The download did not finish. Run the shortcut again and wait for a-Shell to return.")
    mode, args, options = read_job()
    OPTIONS = options
    cleanup_previous(keep_candidates=(mode in ("pick", "playlist")))
    titles = {"video": "Video", "audio": "Audio", "gallery": "Gallery", "file": "File",
              "pick": "Your picks", "playlist": "Playlist", "again": "Download again",
              "clear": "Clear downloads"}
    host = ""
    if args and mode in MODES:
        host = (urllib.parse.urlsplit(args[0]).hostname or "").replace("www.", "")
    start_screen(titles.get(mode, "Download"), host)
    migrate_library()
    try:
        if mode == "clear":
            clear_library(" ".join(args))
            write_status("CLEARED")
            rule()
            write_library_summary()
            back_to_shortcuts()
            sys.exit(0)
        prune_library()
        if mode == "again":
            entry = history_entry(args)
            mode, args = entry.get("mode") or "video", [entry["url"]]
            if mode not in MODES:
                mode = "video"
            say(entry.get("title", "")[:width() - 1])
        if mode == "pick":
            files = publish(run_pick(args))
        elif mode == "playlist":
            run_playlist(args)
            shutil.rmtree(TMP, ignore_errors=True)
            write_status("SAVED")
            say()
            rule()
            with open(MESSAGE_FILE, encoding="utf-8") as f:
                wrap("✓ " + f.read(), indent="", then="  ")
            back_to_shortcuts()
            sys.exit(0)
        else:
            if not args:
                finish(error="No link was given.")
            JOB.update(url=args[0], mode=mode)
            check_for_update(options)
            weekly_update()
            files = publish(run(mode, args[0], options))
    except NeedPick:
        shutil.rmtree(TMP, ignore_errors=True)
        write_status("PICK")
        say("Several items found: choose in Shortcuts.")
        back_to_shortcuts()
        sys.exit(0)
    except NeedPlaylistCount:
        shutil.rmtree(TMP, ignore_errors=True)
        write_status("PLAYLIST")
        say("Choose how many in Shortcuts.")
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
