# Changelog

## [Unreleased]

## [v2.0.0] - 2026-08-24

### Changed

- Use [fsspec](https://github.com/fsspec/filesystem_spec) for the file system API
- **Breaking**: Grove construction takes a file system from fsspec, not a custom `Backend`
- **Breaking**: Change `arbor.toml` format
- **Breaking**: `asset.upload()` and `.download()` replaced by explicit `.upload_file()`, `.upload_dir()`, `.download_file()`, and `.download_dir()`.
  Similar CLI changes.

### Added

- Support for Azure Blob
- Support for directory-mode assets

### Removed

- `grove.connect()`

## [v1.0.0] - 2026-08-19

### Added

- Frontend model: groves, assets, and versions
- Local filesystem backend
- CLI

[unreleased]: https://github.com/cdcent/cfa-arbor/compare/v2.0.0...HEAD
[v2.0.0]: https://github.com/cdcent/cfa-arbor/releases/tag/v2.0.0
[v1.0.0]: https://github.com/cdcent/cfa-arbor/releases/tag/v1.0.0
