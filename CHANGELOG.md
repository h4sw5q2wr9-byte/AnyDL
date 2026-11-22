# Changelog

## 3.0

The first release with a full redesign: a menu with icons, media tools, an
organized library, and many more settings. (2.8 was never released; its
changes are included here.)

**New**

- **Media tools**: compress a video (540p, 720p, 1080p or HEVC, showing the
  size before and after), trim, make a GIF, extract the audio, convert an
  image. They use iOS's own actions. Share a photo or video to AnyDL to
  start there.
- **My downloads**: downloads are sorted into Videos, Audio, Photos, Files
  and Playlists in Files, with a list of recent downloads to download again
  or open the original link.
- **Settings** as a list with icons, each row showing its current value:
  video quality (Best, 4K, 1440p, 1080p, 720p, 480p, 360p Data saver, 240p,
  Ask each time), frame rate, video format (most compatible or highest
  quality), audio format (original or MP3 with cover image), subtitles in 15
  languages, after download (preview, save to Photos, keep in Files), how
  long to keep downloads, clear downloads, updates with Check now, and help.
- **Playlists, channels and profiles**: download all, or type how many, up to
  100, into their own folder.
- **Update check**: once a day, and on demand from Settings.
- A welcome page on first run with the setup steps and a link to a-Shell.
- **A tidy a-Shell screen**: it is cleared at the start of each download,
  shows short steps and one progress line per stream with a smooth
  countdown, and ends with a summary: size, resolution, frame rate, codec,
  whether subtitles were added, and where the file is.
- **Clear error messages** for common problems (YouTube bot check, private,
  age-restricted, unavailable or blocked videos, too many requests, no
  connection, no storage), with the technical detail underneath.
- Streaming sites download four pieces at a time.

**Fixed**

- The quality setting now works for upright videos (TikTok, Shorts), and
  for X videos from the FxTwitter fallback.
- Leaving Settings returns to the main menu.
- Subtitles that fail to download no longer stop the video.
- Subtitles are marked as the default track and no longer added twice for
  YouTube ("en" and "en-orig").

## 2.8 (not released)

- **Settings**, a new menu item: video quality (Best, 1080p, 720p, 480p,
  Data saver or Ask each time), audio format (Original or MP3 with cover
  image), and the update check.
- **Playlists, channels and profiles**: download all, or type how many (up
  to 100). They are saved in their own folder in the Files app, with a
  button to open it.
- Leaving Settings returns to the main menu.
- A welcome page on first run with the setup steps, including a link to get
  a-Shell; it opens again from Settings › Help & setup guide.
- X videos from the FxTwitter fallback follow the quality setting too.
- The previous download is kept one run longer, so an open preview of it
  never loses its file.
- The quality setting now works for upright videos (TikTok, Shorts) too:
  "720p" means the short side of the picture. a-Shell shows the resolution
  you got.
- **Update check**: once a day AnyDL looks for a newer release on GitHub and
  offers it once.
- Clearer note when ffmpeg is not available, which limits some videos to
  lower quality, and shorter error messages.

## 2.7

- X posts whose video or images X hides from logged-out visitors, such as
  age-restricted posts, now download through
  [FxTwitter](https://github.com/FxEmbed/FxEmbed)'s public API when yt-dlp or
  gallery-dl cannot get them.

## 2.6

- Downloads now open in a-Shell's own preview, with the same share button,
  instead of switching back to Shortcuts. They are also kept in the Files app
  under On My iPhone › a-Shell › AnyDL. Several files at once still open in
  Shortcuts, which can page through them.
- Fixed large videos not appearing after download. a-Shell's "Get File"
  fails for large files (on iOS 27.2 it crashes Shortcuts outright, see
  [a-Shell issue #1138](https://github.com/holzschu/a-shell/issues/1138)), so
  files over 50 MB never go through it.
- The shortcut no longer waits in the background for a-Shell, so it can no
  longer be left running. When there is something to show in Shortcuts (a
  choice, an error, several files), the downloader starts AnyDL again, even
  if it fails unexpectedly.

## 2.2

- Fixed YouTube downloads opening the YouTube app instead of returning to
  Shortcuts.

## 2.1

- Media files are named `uploader - short title`, without links, hashtags,
  mentions or emoji.
- The menu heading shows only the site name instead of the full link.

## 2.0

- Native menu with four modes: Video, Audio, Gallery and File.
- Items found on a page are chosen from a Shortcuts list.
- Fixed TikTok downloads, and failed downloads now show the downloader's own
  error.

## 1.1

- Fixed the downloaders failing to load right after their first install.

## 1.0

- First version.
