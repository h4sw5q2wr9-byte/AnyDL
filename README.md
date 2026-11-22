# AnyDL

**Download whatever a link points to, straight from the iOS share sheet.**

AnyDL is a shortcut for iPhone and iPad. Share a link to it, pick what you
want, and it downloads the video, audio, images or file and opens it in Quick
Look, ready to save to Photos or Files.

[**Download the latest release**](../../releases/latest) · [**Set up in 2 minutes**](#set-up)

## Features

| | Mode | What it gets |
| --- | --- | --- |
| <img src="icons/video.png" width="32" alt=""> | **Download Video** | Videos, GIFs and clips from the sites [yt-dlp](https://github.com/yt-dlp/yt-dlp) supports, or any video found on the page. |
| <img src="icons/audio.png" width="32" alt=""> | **Download Audio** | Music, or just the sound of a video. |
| <img src="icons/gallery.png" width="32" alt=""> | **Download Gallery** | Images, albums and photo posts through [gallery-dl](https://github.com/mikf/gallery-dl), or the images on the page. |
| <img src="icons/file.png" width="32" alt=""> | **Download File** | Documents, archives and other files linked on a page. |
| <img src="icons/tools.png" width="32" alt=""> | **Media tools** | Compress or trim a video, make a GIF, extract the audio, convert an image. |
| <img src="icons/library.png" width="32" alt=""> | **My downloads** | Your downloads sorted into folders, and recent downloads to get again. |
| <img src="icons/settings.png" width="32" alt=""> | **Settings** | Quality, frame rate, subtitles, MP3, what happens after a download, storage. |

- **Direct links just work.** If the link is already a file, it is downloaded
  whichever mode you pick.
- **Pick from a list.** When a page offers several matching items, you choose
  one or more from a native list.
- **Readable file names.** Media is saved as `uploader - short title`, without
  hashtags, links or emoji.
- **Honest errors.** If a download fails, the alert shows the downloader's own
  message.
- **Your choice of quality.** Best, 4K, 1440p, 1080p, 720p, 480p, 360p or
  240p, a frame-rate limit, or ask every time. Audio can be saved as MP3
  with its cover image, and videos can get built-in subtitles.
- **Playlists, channels and profiles.** Download all, or choose how many,
  up to 100; they are saved together in a folder in the Files app.
- **An organized library.** Everything lands in Files, sorted into Videos,
  Audio, Photos, Files and Playlists, with a list of recent downloads.
- **Stays current.** The downloaders update themselves once a week, and
  AnyDL tells you when a new version of itself is out.
- **Better X support.** When X hides a post's video from logged-out
  visitors, AnyDL gets it through [FxTwitter](https://github.com/FxEmbed/FxEmbed).

## Set up

It takes about two minutes, once.

1. **Install [a-Shell](https://apps.apple.com/app/a-shell/id1473805438)** from
   the App Store and **open it once**. It must be the full **a-Shell** app;
   **a-Shell mini** does not work. AnyDL runs its downloader inside it.
2. **Add AnyDL.** On your iPhone or iPad, open the
   [latest release](../../releases/latest), tap **AnyDL.shortcut**, and tap
   **Add Shortcut**. Keep the name **AnyDL**; a-Shell uses it to hand results
   back.
3. **Run it once.** A welcome page explains the basics. Tap
   **I have a-Shell, let's go**.
4. **Tap "Always Allow" every time you are asked.** The first few runs, iOS
   asks whether AnyDL may send files to a-Shell, get files from it, and open
   Shortcuts. "Always Allow" means it never asks again; "Allow Once" means it
   asks every time, and "Don't Allow" stops AnyDL from working.
5. **Give the first download a minute or two.** It installs the download
   tools inside a-Shell. After that, downloads start right away.

Requires iOS or iPadOS 15 or later.

## Use

Start AnyDL in any of these ways:

- Share a link or a Safari page to **AnyDL** from the share sheet.
- Copy a link, then run AnyDL. It reads the clipboard.
- Run AnyDL with nothing copied and paste the link when asked.

Choose what to download. a-Shell opens, downloads, and shows the result in
Quick Look right there; use the share button to save it to Photos, Files, or
anywhere else. To skip the preview, set **After download** to
**Save to Photos** or **Keep in Files**.

When one download produces several files, such as a gallery, AnyDL switches
back to Shortcuts and previews them there, so you can swipe through them. If
one of them is over 50 MB, the largest opens in a-Shell instead, because
Shortcuts cannot reliably receive large files from a-Shell.

### My downloads

Everything AnyDL downloads is kept in the Files app under
**On My iPhone › a-Shell › AnyDL**, sorted into folders:

| Folder | What goes there |
| --- | --- |
| Videos | Videos and GIF videos |
| Audio | Music and sound |
| Photos | Images |
| Files | Documents, archives and everything else |
| Playlists | One folder per playlist, channel or profile |

**My downloads** in the menu opens these folders and lists your recent
downloads, so you can download one again or open its original link. How
long downloads are kept is up to you (Settings › Keep downloads), and
Settings › Clear downloads frees the space at once.

### Media tools

These use iOS's own video and image actions, so they are fast and need no
a-Shell. Share a photo or video to AnyDL to start here, or pick one from
Photos or Files.

| Tool | What it does |
| --- | --- |
| Compress video | Makes a video smaller: 540p, 720p, 1080p, or HEVC for the smallest file at the same sharpness. Shows the size before and after. |
| Trim | Cuts a video or song shorter, with iOS's trim screen. |
| Make a GIF | Turns a video into an animated GIF. |
| Extract audio | Saves the sound of a video as M4A. |
| Convert image | To JPEG, PNG or HEIF. |

Each result can be previewed, saved to Photos or Files, or shared.

### Settings

Each row in **Settings** shows its current value.

| Setting | Options |
| --- | --- |
| Video quality | Best (default), 4K, 1440p, 1080p, 720p, 480p, 360p (Data saver), 240p, Ask each time |
| Frame rate | Any (default), Up to 60 fps, Up to 30 fps |
| Video format | Most compatible (default; H.264, plays everywhere), Highest quality (also VP9 and AV1) |
| Audio format | Original (default), MP3 with cover image |
| Subtitles | Off (default), or one of 15 languages, built into the video |
| After download | Preview (default), Save to Photos, Keep in Files |
| Keep downloads | Forever (default), 1 month, 1 week, 1 day |
| Clear downloads | Delete everything, or downloads older than a week |
| Updates | Check now, and automatic checks on or off |

Quality means the short side of the picture, so an upright 720x1280 video
is 720p. If a video has no such size, the closest smaller one is used, and
a-Shell shows what you got. YouTube offers H.264 only up to 1080p, so for
YouTube 1440p and 4K choose **Highest quality**.

Above 360p, sites such as YouTube send video and sound separately, and
joining them needs ffmpeg, which the full a-Shell app includes. Without it,
AnyDL says so and downloads the best single file. MP3 and subtitles need
ffmpeg too.

### Playlists

Share a playlist, channel or profile (YouTube, TikTok, SoundCloud, Vimeo and
other sites yt-dlp supports) and choose **Download Video** or
**Download Audio**. Choose all, or type how many, then AnyDL saves them in
**AnyDL › Playlists › (playlist name)**. From Files you can select them all
and save them to Photos at once.

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
- **Save to Photos up to 50 MB.** Bigger downloads open in a preview, where
  the share button saves them.
- **Subtitles** are only added when the video has them in that language.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| An error says an action needs an app that isn't installed | Install the full [a-Shell](https://apps.apple.com/app/a-shell/id1473805438) app (not a-Shell mini) and open it once. |
| An error asks to open a-Shell | Open a-Shell once, then run AnyDL again. |
| It keeps asking for permission | Choose **Always Allow** instead of Allow Once. If you chose Don't Allow, open the Shortcuts app, tap **⋯** on AnyDL, then the **ⓘ** button, and under **Privacy** reset AnyDL's permissions. |
| The first run is slow | It is installing the downloaders. Leave a-Shell open until it is done. |
| I see an older video, or "the file doesn't exist" | a-Shell shows one preview at a time. Tap **Done** on the old preview; the new download is in Files › On My iPhone › a-Shell › AnyDL. |
| Subtitles do not show | While the video plays, tap the captions button and choose the language. a-Shell's summary says whether they were added; YouTube sometimes keeps subtitles from downloaders. iOS 27 can also make its own subtitles from the same button. |
| Every quality setting looks the same | a-Shell shows the resolution you got ("Quality: 720p"). Some videos only come in one or two sizes; AnyDL then takes the closest one. |
| "The download did not finish" | The downloader stopped unexpectedly. Run it again. |
| Results never come back to Shortcuts | Make sure the shortcut is still named **AnyDL**. |
| I closed the preview too early | Find the download in Files › On My iPhone › a-Shell › AnyDL. |
| An alert with a downloader error | The message comes from yt-dlp or gallery-dl and usually names the cause, such as a login requirement. |
| A site stopped working | Sites change often. The downloaders update weekly; to force it, run `pip install -U yt-dlp gallery-dl` in a-Shell. |
| I want to see the welcome page again | Settings › Help & setup guide. |
| The AnyDL folder takes too much space | Settings › Clear downloads, or set Keep downloads to a shorter time. |
| A compressed video is not smaller | It was already small or already compressed. Try a smaller size, or HEVC. |

### YouTube says I'm a bot

Sometimes YouTube answers "Sign in to confirm you're not a bot". It decides
this mostly from the network you are on, so it is not about you. AnyDL
already tries three other kinds of YouTube player when this happens, and
updates its download tools to the newest version. If it still fails:

1. **Wait a few minutes** and try again.
2. **Switch networks**: from Wi-Fi to mobile data or the other way round.
3. **Turn off any VPN.**
4. **Sign in with a cookies.txt** if it keeps happening. AnyDL then downloads
   as a signed-in YouTube user, which the bot check almost always lets
   through:
   1. On a computer, open a **private (incognito) window** and sign in to
      YouTube. Use a **second Google account**: YouTube may limit accounts it
      sees downloading.
   2. Export the YouTube cookies as **cookies.txt** with a browser extension
      such as *Get cookies.txt LOCALLY* (Chrome) or *cookies.txt* (Firefox),
      then close the private window without signing out.
   3. Copy the file to your iPhone (AirDrop or iCloud Drive) and put it in
      **Files › On My iPhone › a-Shell › AnyDL**, named `cookies.txt`.

   Settings › YouTube sign-in then shows "cookies.txt found", and each
   download's summary says "Signed in with your cookies.txt". Cookies stay on
   your iPhone; delete the file to stop. They expire after a while, so if
   the bot check comes back, export them again.

## Privacy

AnyDL runs entirely on your device. It has no server, no analytics and no
account. It contacts:

- the site you are downloading from;
- PyPI, to install and update the downloaders;
- GitHub, once a day and when you tap Check now, to see whether a new AnyDL
  release is out (switch the daily check off in Settings);
- FxTwitter's public API (`api.fxtwitter.com`), only when X will not hand
  over a post's media; it receives that post's id.

If you add a `cookies.txt` for YouTube sign-in, it is only read by yt-dlp on
your iPhone and sent to the sites it belongs to, like a browser would.

## Build from source

The shortcut is written in [Cherri](https://cherrilang.org), a language that
compiles to Shortcuts.

| File | What it is |
| --- | --- |
| `AnyDL.shortcut` | The signed shortcut. |
| `anydl.py` | The downloader that runs in a-Shell. |
| `AnyDL.cherri.in` | Shortcut source. |
| `welcome.html` | The first-run welcome page, embedded into the shortcut. |
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
