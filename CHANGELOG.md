# Changelog

## 3.4

**Fixed**

- A message from an earlier download, such as "No web link was found", could
  appear again later, for example when opening Media tools. Each result is
  now shown once and then marked as seen.
- A download never starts without a web link.

## 3.3

**Fixed**

- Sharing a video from Photos still did not open the video tools: iOS hands
  it over as a link to the file on the phone (file:///…/IMG_1234.MOV),
  which AnyDL took for a download link. Only web links (http and https)
  are downloaded now, so a shared video opens Video tools, a photo Photo
  tools and audio Audio tools.
- When iOS does not say what kind of file was shared, Media tools opens
  and the tool you pick uses the shared file.
- A shared file the tools cannot edit gets a message saying so.
- Download a link checks that what you pasted is a web link.
- "No web link was found" is shown as a message again, then the menu.

## 3.2

**Fixed**

- Sharing a video from Photos still started a download that ended with
  "No link was given". A link that is only a file name, such as
  IMG_1234.MOV, is no longer taken for a link, and shared files are
  recognised by their file extension: a video opens Video tools (Compress
  video at the top), a photo Photo tools, audio Audio tools.
- Anything else without a link opens the AnyDL menu instead of an error.
- When a download fails, AnyDL says why and then opens its menu, instead of
  ending, so you can try something else right away.

## 3.1

**Fixed**

- Sharing a video from Photos to AnyDL opened the download menu instead of
  the video tools: the video's name, such as IMG_1234.MOV, was read as a
  link (.mov is a web domain). AnyDL now checks what was shared first, so a
  shared video opens Video tools with Compress video at the top, and a
  shared photo or audio file opens its tools the same way.
- Sharing several videos at once uses the first one.
- Sharing a file the tools cannot edit, such as a PDF, now says so.

## 3.0

The first release with a full redesign: a menu with icons, media tools, an
organized library, and many more settings. (2.8 was never released; its
changes are included here.)

**New**

- **Short menus with submenus** and Back everywhere: with a link, Video,
  Audio, Images, File and More; without one, Download a link, Media tools,
  My downloads and Settings. No menu has more than seven rows.
- **Media tools** in three groups, using iOS's own actions:
  - Video: compress (540p, 720p, 1080p or HEVC), trim, change speed, rotate,
    make a GIF, extract audio.
  - Photo: compress (JPEG or HEIF, never enlarging), resize, convert, remove
    background, remove location and camera info, rotate or flip.
  - Audio: trim, convert (M4A or AIFF), change speed.
  Share a file to AnyDL to open the right group. Results show the size
  before and after and can be saved, shared or edited further.
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
- **YouTube bot check**: when YouTube answers "Sign in to confirm you're not
  a bot", AnyDL tries three other kinds of YouTube player, then updates
  yt-dlp to its newest build. Optional **YouTube sign-in** with a
  cookies.txt in the AnyDL folder, with a row in Settings and a guide.

**Fixed**

- The quality setting now works for upright videos (TikTok, Shorts), and
  for X videos from the FxTwitter fallback.
- Leaving Settings returns to the main menu.
- Subtitles that fail to download no longer stop the video.
- Choosing a photo for a video tool caused "Encode Media failed … Photo
  Media". Photos pickers now only show the right kind, and files are
  checked by type first, with a clear message instead of an error.
- Settings failed with "Numerical argument out of domain" when the AnyDL
  folder information was written by an older version; it is now read
  without assuming how many lines it has.
- Slow media tools show a notification while they work.
- Subtitles are marked as the default track and no longer added twice for
  YouTube ("en" and "en-orig").
- Compress video › HEVC 4K used a size name Shortcuts does not know.
- A file without a file extension is no longer passed to a media tool.
- A playlist with one video no longer offers "All 1 videos".
- A test suite (104 tests) checks the downloader offline and the shortcut's
  menus, and runs on every push.

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
