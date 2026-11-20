# Changelog

## 2.4

- Fixed large videos not appearing after download. a-Shell's "Get File"
  fails for large files (on iOS 27.2 it crashes Shortcuts outright, see
  [a-Shell issue #1138](https://github.com/holzschu/a-shell/issues/1138)).
  Downloads over 50 MB now skip it: they are saved to
  On My iPhone › a-Shell › AnyDL in the Files app and shown in a-Shell's own
  preview, which has the same share button.
- The downloader now switches back to Shortcuts itself, and does so even if
  it fails unexpectedly.

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
