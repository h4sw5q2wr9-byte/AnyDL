# Changelog

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
