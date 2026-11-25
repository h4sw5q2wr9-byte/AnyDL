"""Tests for anydl.py, the downloader that runs in a-Shell.

They run offline: downloads come from a local web site (see conftest.py),
and tests that need yt-dlp only use its format selection, not the network.
"""
import json
import os
import time

import pytest

from conftest import run_job

try:
    import yt_dlp
except ImportError:          # pragma: no cover
    yt_dlp = None
needs_ytdlp = pytest.mark.skipif(yt_dlp is None, reason="yt-dlp is not installed")


# ---------------------------------------------------------------- job file

def test_job_mode_link_and_settings(anydl):
    (anydl.base / "anydl_job.txt").write_text(
        "audio\nhttps://example.com/x?a=1&b=2\nquality=720p\naudio=MP3\n\nquality=480p\n")
    mode, args, options = anydl.read_job()
    assert mode == "audio"
    assert args == ["https://example.com/x?a=1&b=2"]
    assert options["quality"] == "480p"          # the last value wins
    assert options["audio"] == "MP3"
    assert options["after"] == "Preview"         # defaults fill the rest


@pytest.mark.parametrize("mode", ["pick", "playlist", "again", "clear"])
def test_job_special_modes_keep_their_lines(anydl, mode):
    (anydl.base / "anydl_job.txt").write_text("%s\n1. a.pdf  (file)\n2\nkeep=1 day\n" % mode)
    got_mode, args, options = anydl.read_job()
    assert got_mode == mode
    assert args == ["1. a.pdf  (file)", "2"]
    assert options["keep"] == "1 day"


def test_job_without_mode_is_a_video(anydl):
    (anydl.base / "anydl_job.txt").write_text("look at https://youtu.be/abc please\n")
    assert anydl.read_job()[:2] == ("video", ["https://youtu.be/abc"])


def test_job_with_a_byte_order_mark(anydl):
    (anydl.base / "anydl_job.txt").write_text("﻿quality=720p\nvideo\nhttps://e.com/v\n")
    mode, args, options = anydl.read_job()
    assert (mode, args, options["quality"]) == ("video", ["https://e.com/v"], "720p")


# ---------------------------------------------------------------- settings

@pytest.mark.parametrize("setting,height", [
    ("Best", None), ("4K (2160p)", 2160), ("1440p", 1440), ("1080p", 1080), ("720p", 720),
    ("480p", 480), ("360p (Data saver)", 360), ("Data saver", 360), ("240p", 240),
    ("Ask each time", None), ("", None), (None, None),
])
def test_quality_height(anydl, setting, height):
    assert anydl.quality_height(setting) == height


@pytest.mark.parametrize("setting,fps", [("Any", None), ("Up to 60 fps", 60), ("Up to 30 fps", 30), (None, None)])
def test_fps_limit(anydl, setting, fps):
    assert anydl.fps_limit(setting) == fps


def test_every_subtitle_language_in_the_shortcut_is_known(anydl):
    source = (anydl_root() / "AnyDL.cherri.in").read_text()
    listed = source.split('@languages = list(')[1].split(')')[0]
    names = [n.strip().strip('"') for n in listed.split(",")]
    assert names[0] == "Off"
    for name in names[1:]:
        assert name.lower() in anydl.SUBTITLE_LANGUAGES, name


def anydl_root():
    import pathlib
    return pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- formats

def youtube_like(upright=False):
    formats = []
    for h in (2160, 1440, 1080, 720, 480, 360, 240):
        w = h * 16 // 9
        width, height = (h, w) if upright else (w, h)
        for fps in ((30, 60) if h >= 720 else (30,)):
            if h <= 1080:
                formats.append(dict(format_id="avc%d-%d" % (h, fps), ext="mp4", vcodec="avc1.64",
                                    acodec="none", width=width, height=height, fps=fps,
                                    tbr=h * fps / 10, url="https://e/a%d%d" % (h, fps), protocol="https"))
            formats.append(dict(format_id="vp9-%d-%d" % (h, fps), ext="webm", vcodec="vp9",
                                acodec="none", width=width, height=height, fps=fps,
                                tbr=h * fps / 12, url="https://e/v%d%d" % (h, fps), protocol="https"))
    formats += [
        dict(format_id="m4a", ext="m4a", vcodec="none", acodec="mp4a.40.2", abr=128, tbr=128,
             url="https://e/m", protocol="https"),
        dict(format_id="muxed360", ext="mp4", vcodec="avc1.42", acodec="mp4a.40.2",
             width=360 if upright else 640, height=640 if upright else 360, fps=30, tbr=600,
             url="https://e/18", protocol="https"),
    ]
    return {"id": "x", "title": "t", "formats": formats, "extractor": "youtube",
            "extractor_key": "Youtube", "webpage_url": "https://e"}


def pick(info, spec, merge):
    import copy
    opts = {"quiet": True, "no_warnings": True, "simulate": True, "format": spec}
    if merge:
        opts["merge_output_format"] = merge
    with yt_dlp.YoutubeDL(opts) as ydl:
        result = ydl.process_ie_result(copy.deepcopy(info), download=False)
    return result["format_id"], min(result["width"], result["height"]), result.get("fps")


@needs_ytdlp
@pytest.mark.parametrize("upright", [False, True])
@pytest.mark.parametrize("quality,codec,short_side", [
    ("Best", "Most compatible", 1080), ("1080p", "Most compatible", 1080),
    ("720p", "Most compatible", 720), ("480p", "Most compatible", 480),
    ("360p (Data saver)", "Most compatible", 360), ("240p", "Most compatible", 240),
    ("Best", "Highest quality", 2160), ("4K (2160p)", "Highest quality", 2160),
    ("1440p", "Highest quality", 1440), ("4K (2160p)", "Most compatible", 1080),
])
def test_quality_picks_the_right_size(anydl, upright, quality, codec, short_side):
    (spec, merge), _ = anydl.video_formats(quality, "Any", codec)
    assert pick(youtube_like(upright), spec, merge)[1] == short_side


@needs_ytdlp
def test_frame_rate_limit(anydl):
    (spec, merge), _ = anydl.video_formats("720p", "Up to 30 fps", "Most compatible")
    assert pick(youtube_like(), spec, merge)[2] == 30
    (spec, merge), _ = anydl.video_formats("720p", "Any", "Most compatible")
    assert pick(youtube_like(), spec, merge)[2] == 60


@needs_ytdlp
def test_without_ffmpeg_a_single_file_is_used(anydl):
    for quality in ("Best", "720p", "240p"):
        _, (spec, merge) = anydl.video_formats(quality, "Any", "Most compatible")
        assert merge is None
        assert pick(youtube_like(), spec, merge)[0] == "muxed360"


def test_x_fallback_size_follows_quality(anydl):
    sizes = [(270, "a/480x270/x.mp4"), (360, "b/640x360/x.mp4"), (720, "c/1280x720/x.mp4"),
             (1080, "d/1920x1080/x.mp4"), (2160, "e/3840x2160/x.mp4")]
    assert anydl.pick_size(sizes, "Best").startswith("e/")
    assert anydl.pick_size(sizes, "1080p").startswith("d/")
    assert anydl.pick_size(sizes, "480p").startswith("b/")
    assert anydl.pick_size(sizes, "240p").startswith("a/")    # nothing small enough: smallest


# ---------------------------------------------------------------- names

@pytest.mark.parametrize("raw,clean", [
    ("my%20clip.mp4", "my clip.mp4"),
    ("a/b\\c:d?.zip", "a b c d.zip"),
    ("....", "download"),
    ("日本語のタイトル.mp4", "日本語のタイトル.mp4"),
    ("report (final) v2.pdf", "report (final) v2.pdf"),
])
def test_safe_name(anydl, raw, clean):
    assert anydl.safe_name(raw) == clean


def test_media_names(anydl):
    assert anydl.media_name("scout2015", "Scramble up ur name & I’ll try 😍 #fyp #pets",
                            "TikTok", "1") == "scout2015 - Scramble up ur name I'll try"
    assert anydl.media_name("NASA", "NASA - Watch https://t.co/x #Artemis", "Twitter", "1") == "NASA - Watch"
    assert anydl.media_name("some_user", "#fyp #viral 😍", "TikTok", "73000") == "some_user - TikTok 73000"
    long = anydl.media_name("Ch", "A Long Video Title Goes Here (Official Video) (4K Remaster)", "Youtube", "x")
    assert long.count("(") == long.count(")")
    assert len(long) <= 60


def test_x_links(anydl):
    assert anydl.x_status_id("https://x.com/a/status/123?s=12") == "123"
    assert anydl.x_status_id("https://mobile.twitter.com/a/status/456/video/1") == "456"
    assert anydl.x_status_id("https://fixupx.com/a/status/789") == "789"
    assert anydl.x_status_id("https://x.com/home") is None
    assert anydl.x_status_id("https://notx.com/a/status/1") is None


# ---------------------------------------------------------------- messages

@pytest.mark.parametrize("error,start", [
    ("ERROR: [youtube] abc: Sign in to confirm you’re not a bot. Use --cookies", "YouTube thinks this is a bot"),
    ("HTTP Error 429: Too Many Requests", "The site says there were too many requests"),
    ("[youtube] x: Private video", "This video is private"),
    ("[youtube] x: Video unavailable", "This video is unavailable"),
    ("[twitter] 1: No video could be found in this tweet", "No video found"),
    ("[Errno 28] No space left on device", "Your iPhone is out of storage"),
    ("something nobody expected", "something nobody expected"),
])
def test_friendly_errors(anydl, error, start):
    assert anydl.friendly_error(anydl.clean_error(error)).startswith(start)


def test_clean_error_strips_command_line_advice(anydl):
    text = anydl.clean_error("ERROR: [youtube] abc: Sign in to confirm you’re not a bot. This helps "
                             "protect our community. Use --cookies-from-browser or --cookies. "
                             "See https://github.com/yt-dlp/yt-dlp/wiki/FAQ")
    assert text == "Sign in to confirm you’re not a bot."


def test_first_sentence(anydl):
    assert anydl.first_sentence("One. Two.") == "One."
    assert anydl.first_sentence("No full stop") == "No full stop"


# ---------------------------------------------------------------- progress

def test_short_time_rounding(anydl):
    assert [anydl.short_time(s) for s in (0.2, 7, 12, 59, 61, 130, 700)] == \
        ["1s", "7s", "15s", "60s", "1m 10s", "2m 10s", "12m"]


def test_progress_fits_and_counts_down(anydl, monkeypatch, capsys):
    clock = [1000.0]
    monkeypatch.setattr(anydl.time, "time", lambda: clock[0])
    bar = anydl.Progress("Video")
    total, done, shown = 40_000_000, 0, []
    for step in range(80):                      # uneven bursts: fast, then stalls
        clock[0] += 0.5
        done = min(total, done + (2_000_000 if step % 4 else 0))
        bar.update(done, total)
    bar.finish(done)
    frames = [f.strip() for f in capsys.readouterr().out.split("\r") if "%" in f]
    assert frames and all(len(f) <= 39 for f in frames)
    for frame in frames:
        last = frame.split()[-1]
        if last.endswith("s") and last[:-1].isdigit():
            shown.append(int(last[:-1]))
    assert shown and all(b <= a for a, b in zip(shown, shown[1:])), shown   # never goes up


# ---------------------------------------------------------------- page scan

def test_find_candidates(anydl):
    html = ('<a href="doc.pdf">a</a><a href="/x">page</a><video><source src="clip.mp4"></video>'
            '<img src="pic.jpg"><script>var u="https:\\/\\/cdn.e.com\\/v.m3u8?x=1"</script>'
            '<link href="font.woff2"><script>"https://e.com/f.woff2"</script>')
    found = anydl.find_candidates("https://e.com/p/", html)
    kinds = {url.rsplit("/", 1)[-1].split("?")[0]: kind for kind, url in found}
    assert kinds == {"clip.mp4": "video", "v.m3u8": "stream", "doc.pdf": "file", "pic.jpg": "image"}
    assert found[0][0] in ("video", "stream")             # best first


# ---------------------------------------------------------------- library

def test_files_are_sorted_into_folders(anydl, tmp_path):
    for name in ("a.mp4", "b.mp3", "c.jpg", "d.pdf"):
        (tmp_path / name).write_bytes(b"x")
        anydl.to_library(str(tmp_path / name))
    assert sorted(p.relative_to(anydl.library).as_posix() for p in anydl.library.rglob("*.*")) == \
        ["Audio/b.mp3", "Files/d.pdf", "Photos/c.jpg", "Videos/a.mp4"]


def test_same_name_gets_a_number(anydl, tmp_path):
    for _ in range(3):
        (tmp_path / "a.mp4").write_bytes(b"x")
        anydl.to_library(str(tmp_path / "a.mp4"))
    assert sorted(p.name for p in (anydl.library / "Videos").iterdir()) == ["a (2).mp4", "a (3).mp4", "a.mp4"]


def test_old_downloads_are_moved_into_folders(anydl):
    anydl.library.mkdir(parents=True)
    (anydl.library / "old clip.mp4").write_bytes(b"x")
    (anydl.library / "old song.mp3").write_bytes(b"x")
    (anydl.library / "old-playlist").mkdir()
    (anydl.library / "old-playlist" / "a.mp4").write_bytes(b"x")
    (anydl.library / "cookies.txt").write_text("# Netscape HTTP Cookie File\n")
    anydl.migrate_library()
    assert (anydl.library / "Videos" / "old clip.mp4").exists()
    assert (anydl.library / "Audio" / "old song.mp3").exists()
    assert (anydl.library / "Playlists" / "old-playlist" / "a.mp4").exists()
    assert (anydl.library / "cookies.txt").exists()       # never moved


def test_keep_downloads_and_clear(anydl):
    videos = anydl.library / "Videos"
    videos.mkdir(parents=True)
    old, new = videos / "old.mp4", videos / "new.mp4"
    old.write_bytes(b"x" * 10)
    new.write_bytes(b"x" * 10)
    (anydl.library / "cookies.txt").write_text("# Netscape HTTP Cookie File\n")
    three_days_ago = time.time() - 3 * 86400
    os.utime(old, (three_days_ago, three_days_ago))
    anydl.OPTIONS = dict(anydl.DEFAULT_OPTIONS, keep="1 day")
    anydl.prune_library()
    assert not old.exists() and new.exists()
    anydl.clear_library("all")
    assert not new.exists()
    assert (anydl.library / "cookies.txt").exists()       # never cleared
    assert "Deleted 1 download" in (anydl.base / "anydl_message.txt").read_text()


def test_library_summary_lines(anydl):
    anydl.write_library_summary()
    lines = (anydl.base / "anydl_library.txt").read_text().split("\n")
    assert lines[0].startswith("shareddocuments://")
    assert lines[1] == "No downloads yet"
    assert lines[2] == "Not set up"
    (anydl.library / "cookies.txt").write_text("# Netscape HTTP Cookie File\n")
    (anydl.library / "Videos" / "a.mp4").write_bytes(b"x" * 2048)
    anydl.write_library_summary()
    lines = (anydl.base / "anydl_library.txt").read_text().split("\n")
    assert lines[1] == "1 file · 2.0 KB" and lines[2] == "cookies.txt found"


def test_cookie_file_format_check(anydl):
    anydl.library.mkdir(parents=True)
    assert anydl.cookie_file() is None
    (anydl.library / "cookies.txt").write_text("not cookies")
    assert anydl.cookie_file() is None
    (anydl.library / "cookies.txt").write_text(".youtube.com\tTRUE\t/\tTRUE\t0\tSID\tx\n")
    assert anydl.cookie_file() == anydl.COOKIES_FILE


# ---------------------------------------------------------------- history

def test_history(anydl):
    for n in range(35):
        anydl.JOB.update(url="https://e.com/%d" % n, mode="video")
        anydl.record_history("title %d" % n, 1, "/x")
    labels = (anydl.base / "anydl_history.txt").read_text().split("\n")
    links = (anydl.base / "anydl_history_links.txt").read_text().split("\n")
    assert len(labels) == len(links) == anydl.HISTORY_LIMIT
    assert labels[0].startswith("1. title 34 · Video") and links[0] == "https://e.com/34"
    assert anydl.history_entry(["3"])["url"] == "https://e.com/32"
    with pytest.raises(anydl.Failed):
        anydl.history_entry(["99"])


# ---------------------------------------------------------------- update check

class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self, *a):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.mark.parametrize("latest,offered", [("v9.9", "9.9"), ("v3.10", "3.10"), ("v3.0", None), ("v2.7", None)])
def test_update_check(anydl, monkeypatch, latest, offered):
    monkeypatch.setattr(anydl.urllib.request, "urlopen",
                        lambda *a, **k: FakeResponse(json.dumps({"tag_name": latest}).encode()))
    anydl.check_for_update(dict(anydl.DEFAULT_OPTIONS))
    note = anydl.base / "anydl_update.txt"
    assert (note.read_text() if note.exists() else None) == offered
    if offered:                                 # offered once, and at most daily
        note.unlink()
        anydl.check_for_update(dict(anydl.DEFAULT_OPTIONS))
        assert not note.exists()


def test_update_check_off(anydl, monkeypatch):
    monkeypatch.setattr(anydl.urllib.request, "urlopen", lambda *a, **k: pytest.fail("checked"))
    anydl.check_for_update(dict(anydl.DEFAULT_OPTIONS, updates="Off"))


# ---------------------------------------------------------------- whole runs

def test_direct_file_opens_in_the_preview(anydl, site):
    assert run_job(anydl, "video", site + "/clip.mp4") == "VIEW"
    assert (anydl.library / "Videos" / "clip.mp4").stat().st_size == 300_000
    assert anydl.commands[-1].startswith('view "') and anydl.commands[-1].endswith('Videos/clip.mp4"')
    assert "open shortcuts" not in " ".join(anydl.commands)
    history = (anydl.base / "anydl_history.txt").read_text()
    assert history.startswith("1. clip · Video")


def test_save_to_photos_small_and_large(anydl, site):
    assert run_job(anydl, "video", site + "/clip.mp4", "after=Save to Photos") == "PHOTOS"
    assert (anydl.base / "anydl_files.txt").read_text() == "clip.mp4"
    assert (anydl.base / "clip.mp4").exists()                 # a copy for the shortcut
    assert (anydl.library / "Videos" / "clip.mp4").exists()
    assert anydl.commands[-1].startswith("open shortcuts://run-shortcut?name=AnyDL")
    # over 50 MB: opens in the preview instead
    assert run_job(anydl, "video", site + "/big.mp4", "after=Save to Photos") == "VIEW"
    assert not (anydl.base / "clip.mp4").exists()             # the old copy is cleaned up


def test_keep_in_files_opens_the_folder(anydl, site):
    assert run_job(anydl, "file", site + "/doc.pdf", "after=Keep in Files") == "FILES"
    assert anydl.commands[-1].startswith("open shareddocuments://")
    assert anydl.commands[-1].endswith("/Files")


def test_page_with_several_files_then_pick(anydl, site):
    assert run_job(anydl, "file", site + "/files.html") == "PICK"
    choices = (anydl.base / "anydl_choices.txt").read_text().split("\n")
    assert choices == ["1. doc.pdf  (file)", "2. notes.zip  (file)"]
    assert run_job(anydl, "pick", *choices) == "OK"
    assert (anydl.base / "anydl_files.txt").read_text().split("\n") == ["doc.pdf", "notes.zip"]
    assert (anydl.library / "Files" / "doc.pdf").exists()
    assert (anydl.base / "anydl_history.txt").read_text().startswith("1. doc and 1 more · File")


def test_page_with_one_file(anydl, site):
    assert run_job(anydl, "file", site + "/one.html") == "VIEW"
    assert (anydl.library / "Files" / "doc.pdf").exists()


def test_gallery_from_a_page(anydl, site, monkeypatch):
    monkeypatch.setattr(anydl, "try_gallerydl", lambda url, folder: (_ for _ in ()).throw(
        anydl.Failed("gallery-dl does not know this site.")))
    assert run_job(anydl, "gallery", site + "/pics.html") == "PICK"
    assert run_job(anydl, "pick", "1. pic.jpg  (image)", "2. pic2.jpg  (image)") == "OK"
    history = (anydl.base / "anydl_history.txt").read_text()
    assert "· Gallery ·" in history                            # remembers the mode


def test_failures_have_plain_messages(anydl, site):
    assert run_job(anydl, "video", site + "/missing.mp4").startswith("The link leads nowhere")
    assert run_job(anydl, "video", "not a link") == "No link was given."
    assert run_job(anydl, "file", site + "/empty.html") == "No files found at that link."
    assert anydl.commands[-1].startswith("open shortcuts://")


def test_again_and_clear(anydl, site):
    run_job(anydl, "video", site + "/clip.mp4")
    assert run_job(anydl, "again", "1") == "VIEW"
    assert (anydl.library / "Videos" / "clip (2).mp4").exists()
    assert run_job(anydl, "again", "99").startswith("That download is no longer")
    assert run_job(anydl, "clear", "all") == "CLEARED"
    assert not any(anydl.library.rglob("*.mp4"))
    assert (anydl.base / "anydl_library.txt").read_text().split("\n")[1] == "No downloads yet"


def test_every_run_switches_back_or_shows_something(anydl, site, monkeypatch):
    def crash(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(anydl, "run", crash)
    assert run_job(anydl, "video", site + "/clip.mp4").startswith("Unexpected error")
    assert anydl.commands[-1].startswith("open shortcuts://")


def test_screen_is_cleared_and_fits(anydl, site, capsys):
    run_job(anydl, "video", site + "/clip.mp4")
    out = capsys.readouterr().out
    assert out.startswith("\033[2J")
    assert "hideKeyboard" in anydl.commands
    for line in out.replace("\r", "\n").split("\n"):
        assert len(line.rstrip()) <= 40, line


# ---------------------------------------------------------------- YouTube bot check

@needs_ytdlp
def test_bot_check_tries_other_players(anydl, monkeypatch, tmp_path):
    tried = []

    def extract(self, url, *a, **k):
        clients = (self.params.get("extractor_args") or {}).get("youtube", {}).get("player_client")
        tried.append(clients)
        if clients != ["web_embedded", "tv_downgraded"]:
            raise yt_dlp.utils.DownloadError("ERROR: [youtube] a: Sign in to confirm you’re not a bot.")
        folder = os.path.dirname(self.params["outtmpl"]["default"])
        open(os.path.join(folder, "Ch ~~ A video ~~ Youtube ~~ a.mp4"), "wb").write(b"x")
        return {}

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract)
    files = anydl.try_ytdlp("https://www.youtube.com/watch?v=a", str(tmp_path))
    assert tried == [None, ["tv", "web_safari"], ["web_embedded", "tv_downgraded"]]
    assert os.path.basename(files[0]) == "Ch - A video.mp4"


@needs_ytdlp
def test_bot_check_gives_up_with_advice(anydl, monkeypatch, tmp_path):
    def extract(self, url, *a, **k):
        raise yt_dlp.utils.DownloadError("ERROR: [youtube] a: Sign in to confirm you’re not a bot.")
    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract)
    with pytest.raises(anydl.Failed) as failure:
        anydl.try_ytdlp("https://www.youtube.com/watch?v=a", str(tmp_path))
    assert "YouTube sign-in" in anydl.friendly_error(str(failure.value))


# ---------------------------------------------------------------- playlists

@needs_ytdlp
def test_playlist_links(anydl):
    assert anydl.is_playlist_link("https://www.youtube.com/playlist?list=PL0123456789abcdef")
    assert not anydl.is_playlist_link("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL0123456789abcdef")
    assert not anydl.is_playlist_link("https://youtu.be/dQw4w9WgXcQ")
    assert not anydl.is_playlist_link("https://example.com/clip.mp4")


@pytest.mark.parametrize("count,choices", [
    (6, ["All 6 videos", "Choose a number"]),
    (1, ["Download the 1 video"]),
])
def test_playlist_asks_how_many_then_saves_a_folder(anydl, monkeypatch, tmp_path, count, choices):
    url = "https://www.youtube.com/playlist?list=PL0123456789abcdef"
    monkeypatch.setattr(anydl, "is_playlist_link", lambda u: True)
    monkeypatch.setattr(anydl, "playlist_info", lambda u: ("My list", count))
    assert run_job(anydl, "video", url) == "PLAYLIST"
    assert (anydl.base / "anydl_choices.txt").read_text().split("\n") == choices
    asked = {}

    def fake_download(url, folder, audio=False, referer=None, options=None, playlist=0):
        asked["playlist"] = playlist
        made = []
        for n in range(playlist):
            path = os.path.join(folder, "clip %d.mp4" % n)
            open(path, "wb").write(b"x")
            made.append(path)
        return made

    monkeypatch.setattr(anydl, "try_ytdlp", fake_download)
    assert run_job(anydl, "playlist", "99") == "SAVED"           # more than there are: capped
    assert asked["playlist"] == count
    assert len(list((anydl.library / "Playlists" / "My list").iterdir())) == count
    assert "Saved %d" % count in (anydl.base / "anydl_message.txt").read_text()
    assert (anydl.base / "anydl_open.txt").read_text().startswith("shareddocuments://")
