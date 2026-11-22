# AnyDL

**Download whatever a link points to, straight from the iOS share sheet.**

AnyDL is a shortcut for iPhone and iPad. Share a link to it, pick what you
want, and it downloads the video, audio, images or file and opens it in Quick
Look, ready to save to Photos or Files.

[**Download the latest release**](../../releases/latest)

## Features

| | Mode | What it gets |
| --- | --- | --- |
| <img src="icons/video.png" width="32" alt=""> | **Download Video** | Videos, GIFs and clips from the sites [yt-dlp](https://github.com/yt-dlp/yt-dlp) supports, or any video found on the page. |
| <img src="icons/audio.png" width="32" alt=""> | **Download Audio** | Music, or just the sound of a video. |
| <img src="icons/gallery.png" width="32" alt=""> | **Download Gallery** | Images, albums and photo posts through [gallery-dl](https://github.com/mikf/gallery-dl), or the images on the page. |
| <img src="icons/file.png" width="32" alt=""> | **Download File** | Documents, archives and other files linked on a page. |

- **Direct links just work.** If the link is already a file, it is downloaded
  whichever mode you pick.
- **Pick from a list.** When a page offers several matching items, you choose
  one or more from a native list.
- **Readable file names.** Media is saved as `uploader - short title`, without
  hashtags, links or emoji.
- **Honest errors.** If a download fails, the alert shows the downloader's own
  message.
- **Stays current.** The downloaders update themselves once a week.
- **Better X support.** When X hides a post's video from logged-out
  visitors, AnyDL gets it through [FxTwitter](https://github.com/FxEmbed/FxEmbed).

## Requirements

- iOS or iPadOS 15 or later.
- [a-Shell](https://apps.apple.com/app/a-shell/id1473805438), the full app.
  a-Shell mini is not enough.

## Install

1. Install a-Shell from the App Store and open it once.
2. On your iPhone or iPad, download `AnyDL.shortcut` from the
   [latest release](../../releases/latest).
3. Open the file and tap **Add Shortcut**. Keep the name **AnyDL**: a-Shell
   uses it to hand results back to the shortcut.

The first download installs yt-dlp and gallery-dl inside a-Shell, which takes
a minute or two. After that it starts immediately.

## Use

Start AnyDL in any of these ways:

- Share a link or a Safari page to **AnyDL** from the share sheet.
- Copy a link, then run AnyDL. It reads the clipboard.
- Run AnyDL with nothing copied and paste the link when asked.

Choose a mode from the menu. a-Shell opens, downloads, and shows the result
in Quick Look right there; use the share button to save it to Photos, Files,
or anywhere else. Downloads are also kept in the Files app under
**On My iPhone › a-Shell › AnyDL**.

When one download produces several files, such as a gallery, AnyDL switches
back to Shortcuts and previews them there, so you can swipe through them. If
one of them is over 50 MB, the largest opens in a-Shell instead, because
Shortcuts cannot reliably receive large files from a-Shell; the rest are in
the AnyDL folder.

## How it works

```
Share sheet ──► AnyDL shortcut ──► a-Shell runs anydl.py ──► Quick Look
                   menu, lists        direct file
                                      yt-dlp / gallery-dl
                                      page scan
```

The shortcut is only the front end. It hands a small Python script,
[`anydl.py`](anydl.py), and the link to a-Shell. The script first checks
whether the link itself is a file. If not, it runs the downloader for the
chosen mode, and falls back to scanning the page for matching media.

The shortcut never waits for a-Shell, so nothing is left running. a-Shell
shows a single download itself. When there is something to show in Shortcuts
(a choice, an error, several files), the script starts AnyDL again with the
input `anydl-return`, and that run reads the results from a few small text
files.

## Limitations

- **No logins.** Posts that require a signed-in account cannot be
  downloaded. On X, the FxTwitter fallback covers most of these, but not
  posts from private accounts.
- **No DRM.** Protected streams from services such as Netflix or Spotify are
  not supported, and never will be.
- **Not every site.** Some sites deliver video in ways that leave nothing to
  download.
- **One download at a time.** Files from the previous run are cleared when
  the next one starts, including large files in the AnyDL folder, so save
  what you want to keep.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| The first run is slow | It is installing the downloaders. Leave a-Shell open until it switches back. |
| "The download did not finish" | The downloader stopped unexpectedly. Run it again. |
| Results never come back to Shortcuts | Make sure the shortcut is still named **AnyDL**. |
| I closed the preview too early | Find the download in Files › On My iPhone › a-Shell › AnyDL. |
| An alert with a downloader error | The message comes from yt-dlp or gallery-dl and usually names the cause, such as a login requirement. |
| A site stopped working | Sites change often. The downloaders update weekly; to force it, run `pip install -U yt-dlp gallery-dl` in a-Shell. |

## Privacy

AnyDL runs entirely on your device. It has no server, no analytics and no
account. It contacts the site you are downloading from, PyPI to install and
update the downloaders, and, only when X will not hand over a post's media,
FxTwitter's public API (`api.fxtwitter.com`), which receives that post's id.

## Build from source

The shortcut is written in [Cherri](https://cherrilang.org), a language that
compiles to Shortcuts.

| File | What it is |
| --- | --- |
| `AnyDL.shortcut` | The signed shortcut. |
| `anydl.py` | The downloader that runs in a-Shell. |
| `AnyDL.cherri.in` | Shortcut source. |
| `AnyDL.cherri` | Generated: the source with `anydl.py` and the icons embedded. |
| `build.py` | Regenerates `AnyDL.cherri`. |
| `icons/` | Menu icons. |
| `tools/` | Scripts that compile and sign through the Cherri playground. |

```sh
python3 build.py
node tools/compile.js AnyDL.cherri unsigned.shortcut
node tools/sign.js unsigned.shortcut AnyDL AnyDL.shortcut
```

The scripts in `tools/` need Node.js with
[Playwright](https://playwright.dev). You can also paste `AnyDL.cherri` into
the [Cherri playground](https://playground.cherrilang.org), press build, and
choose **Sign Shortcut**.

To publish a release, update `CHANGELOG.md` and the version in `anydl.py`,
rebuild, then push a tag such as `v2.3`. The release workflow attaches the
shortcut.

## Responsible use

Only download content you have the right to download. Respect copyright and
the terms of the sites you use. AnyDL is provided as is, without warranty.

## Credits

AnyDL stands on the work of others:

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) and
  [gallery-dl](https://github.com/mikf/gallery-dl) do the downloading.
- [a-Shell](https://github.com/holzschu/a-shell) runs Python on iOS.
- [Cherri](https://github.com/electrikmilk/cherri) compiles the shortcut, and
  [HubSign](https://routinehub.co) signs it.
- Icons are from [Lucide](https://lucide.dev), under the ISC license. See
  [`icons/LUCIDE-LICENSE`](icons/LUCIDE-LICENSE).
- [FxTwitter](https://github.com/FxEmbed/FxEmbed) provides the X fallback.
- Inspired by [SW-DLT](https://github.com/net00-1/SW-DLT).

AnyDL is an independent project and is not affiliated with any of them.

## License

[MIT](LICENSE)
