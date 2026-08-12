# Arbor specification

## 1. Purpose and scope

Arbor is a small tool for sharing and versioning heterogeneous files during infectious disease responses.
It stores numbered *revisions* of named *assets* within a *grove* on a configured *storage backend*.
It is not a workflow engine, database, data catalog, or general-purpose cloud filesystem.

Version 1 provides a local-filesystem storage backend, a Python object API, and a thin command-line interface (CLI) over that API.
The public API includes a small abstract `Arbor` contract, implemented by `LocalArbor`; Azure Blob storage and a generalized low-level storage protocol are deferred.

The words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

## 2. Model

A configured local directory is the storage backend.
It contains groves; a grove contains assets; and an asset contains numbered revisions.
A revision is a non-empty set of regular files identified by their relative logical paths.

```text
storage backend/
  manifest.json
  log.jsonl
  grove-id-1/
    manifest.json
    log.jsonl
    asset-id-1/
      manifest.json
      log.jsonl
      0/
        {files...}
      1/
        {files...}
```

Groves, assets, and revisions have no user metadata.
Arbor does not interpret file contents or give special meaning to files such as `README.md` or `metadata.json`.
Users MAY include such files in a revision.

### 2.1 IDs and names

Users supply grove and asset IDs.
Each ID MUST:

- contain 1 to 80 characters;
- match `[A-Za-z0-9][A-Za-z0-9._-]*`; and
- be unique among the current names of its siblings.

The filesystem directory names are authoritative for current grove and asset IDs.
Creating or renaming to a current sibling ID MUST fail with `Conflict`.
Groves and assets MAY be renamed without changing their contents.
After a rename, the old ID no longer resolves the object and the new ID does.

A previously used grove or asset ID MAY be reused.
When the reused ID appears anywhere in the relevant audit log, Arbor MUST emit a Python warning; the CLI MUST render that warning on standard error.
Historical reuse is a warning, not an error.

An asset is created by uploading revision 0; empty assets do not exist.
The next revision number is one greater than the maximum number found in either that asset's revision directories or its upload log events.
Consequently, a number that reached its final revision directory or upload log, including a subsequently destroyed revision, MUST NOT be reused.
A number used only in internal staging MAY be reused.

### 2.2 Upload, amendment, and destruction

Uploading publishes a complete new revision.
Files are not implicitly carried forward from an earlier revision.

The latest revision is the existing revision with the greatest number.
Arbitrary historical correction is not part of version 1.

Amending a revision completely replaces its paths and bytes without allocating a new revision number.
It MUST satisfy the same file and path validation rules as an upload.
Multiple amendments are allowed.
The log records when each amendment occurred but Arbor does not retain earlier payloads.

Destroying a revision removes its complete payload.
Its upload and other earlier log events MUST remain, and its revision number MUST NOT be reused.
After destruction, the greatest remaining revision becomes latest.
If no revisions remain, the asset continues to exist but has no latest revision; download, amendment, and destruction MUST fail with `NotFound`.

Revision listings return existing revisions in increasing numeric order.
Destroyed revisions are absent from the listing.
Downloading without a revision number resolves the latest revision before copying begins.

## 3. Files

A revision is uploaded or amended from a source directory containing at least one regular file.
The source directory itself is not part of the revision; its recursive contents define the logical paths.
Its logical paths MUST:

- use `/` separators and be relative and non-empty;
- contain no empty, `.` or `..` component or NUL character; and
- be unique within the revision.

Directories are implicit.
Uploads and amendments MUST reject symbolic links, device files, sockets, and other special files anywhere below the source directory.
The source and download destination MUST be outside the configured storage-backend directory.
Callers are responsible for not modifying a source directory while Arbor reads it; behavior under concurrent source modification is undefined in version 1.
A round-trip upload and download MUST preserve every logical path and byte.

A download reproduces all paths beneath a new destination directory.
It MUST fail with `Conflict` if the destination already exists.
Version 1 has no overwrite option and no API for loading a revision directly into memory.

## 4. Audit logs and time

Logs record history but, except for revision-number allocation, do not determine current state.
Current grove and asset names and existing revision payloads are determined from their directories.
Log listing MUST use append order.

Each log is a UTF-8 JSON Lines file with exactly one JSON object per line.
Existing lines MUST NOT be updated or deleted through Arbor.
An incomplete trailing line left by abrupt termination is not an event and MAY be truncated during recovery; malformed complete lines MUST NOT be silently discarded.
Every event time MUST be generated by Arbor, represent UTC, and use RFC 3339 with a `Z` suffix.
Timestamps MAY be equal and do not establish a total order.

The arbor-level `log.jsonl` records creation and rename events for groves:

```json
{"event":"created","grove_id":"2026-ebola","created_at":"2026-08-10T17:00:00.123456Z"}
{"event":"renamed","old_grove_id":"2026-ebola","grove_id":"2026-filovirus","renamed_at":"2026-08-11T14:00:00.123456Z"}
```

Each grove's `log.jsonl` records analogous asset events:

```json
{"event":"created","asset_id":"weekly-cases","created_at":"2026-08-10T18:30:00.123456Z"}
{"event":"renamed","old_asset_id":"weekly-cases","asset_id":"daily-cases","renamed_at":"2026-08-11T13:00:00.123456Z"}
```

Each asset's `log.jsonl` records revision events:

```json
{"event":"uploaded","revision":1,"uploaded_at":"2026-08-10T18:30:00.123456Z"}
{"event":"amended","revision":1,"amended_at":"2026-08-10T18:45:00.123456Z"}
{"event":"destroyed","revision":1,"destroyed_at":"2026-08-10T19:00:00.123456Z"}
```

The displayed fields are the only fields permitted for each event type in schema version 1.
The logs do not record downloads, actors, attempts, failures, file details, or user metadata.
A malformed event or unsupported event type MUST fail with `Invalid` when Arbor reads the affected log.

Because names are determined from directories, a process or power loss between a successful rename and its log append MAY leave the new name in use without a corresponding audit event.
Likewise, an abrupt interruption MAY leave a completed filesystem mutation without its final audit event.
This loss of audit completeness is an accepted version-1 limitation; it MUST NOT cause Arbor to infer a current name from log history.

## 5. Mutation and interruption

Version 1 assumes that users do not run overlapping Arbor mutations against one backend.
Arbor does not provide interprocess locking, mutation serialization, or read serialization.
Behavior during concurrent mutation is undefined.
A read concurrent with a mutation MAY observe either the state before or after that mutation and MAY fail if it occurs during a directory transition.

Arbor MUST stage new payloads within the storage backend so that the final filesystem rename does not cross filesystems.
Each mutation changes the intended filesystem state and then appends its audit event before returning success.
If the backend remains writable, an ordinary exception at any point MUST restore the prior visible state, remove any incomplete trailing log data, and SHOULD remove its staging data.

An *interrupted operation* includes both an ordinary exception and abrupt process or machine termination.
After abrupt termination, temporary staging or backup data MAY remain and an audit event MAY be absent.
Before a later operation accesses an affected resource, Arbor MUST perform bounded cleanup of the relevant staging or backup data sufficient to ensure that:

- internal staging and backup paths are never returned by public listings;
- an upload is either absent or visible as one complete revision, never a partial revision;
- an interrupted amendment exposes either its complete old payload or its complete replacement, never a mixture; and
- an interrupted destruction exposes either the complete revision or no revision.

Recovery need not reproduce the audit event that was lost during abrupt termination.
Retrying an interrupted operation is a new operation; version 1 provides no idempotency keys or exactly-once retry guarantee.
These guarantees assume the underlying filesystem remains internally consistent.
Version 1 does not promise recovery from filesystem corruption or `fsync`-level durability across power loss.

## 6. Required interfaces

The public Python API MUST provide an abstract `Arbor` class and objects representing the local backend, a grove, and an asset.
`LocalArbor` MUST implement `Arbor`.
It MUST provide these capabilities:

- configure, initialize, or connect a backend and create, list, access, and rename groves;
- create an asset by uploading revision 0, and list, access, and rename assets;
- upload the next revision;
- list revision numbers and a revision's file paths;
- download a specified or latest revision;
- amend or destroy a revision;
- list the grove, asset, and revision audit logs; and
- explicitly validate a complete backend or one grove.

Grove and asset listings MUST always use lexicographic ID order.
No alternate listing order is required.

The CLI MUST expose the same version-1 capabilities and MUST be a thin wrapper around the Python object API.
It MUST NOT contain separate storage, validation, or lifecycle logic.
Human-readable output is sufficient; a stable machine-readable output format is not required in version 1.

### 6.1 CLI configuration

Every CLI invocation MUST select a TOML configuration file using the first applicable source:

1. the global `--config PATH` option;
2. the `ARBOR_CONFIG` environment variable; or
3. the nearest `arbor.toml` found by searching from the current working directory upward through its ancestors to the filesystem root.

An explicit or environment-provided relative configuration path is resolved against the current working directory.
If no configuration is found, the CLI MUST fail with `Invalid`, report every `arbor.toml` path searched, and mention both `--config` and `ARBOR_CONFIG`.
An explicit or environment-provided path that does not name a file MUST fail without falling through to the next source.

The version-1 configuration has exactly this shape:

```toml
[backend]
type = "local"
path = ".arbor"
```

The backend path MUST be a non-empty string and is resolved relative to the directory containing the configuration file.
Unknown top-level keys, unknown `[backend]` keys, and unsupported backend types MUST fail with `Invalid`.
The CLI MUST NOT combine multiple configuration files or create a missing `arbor.toml`.

The `init` command calls `init()` on the configured backend; every other storage command calls `connect()` before delegating to the object API.
A `status` command MUST display the selected configuration file, backend type, and resolved backend path without connecting.
Configuration discovery belongs only to the CLI and MUST NOT occur when importing Arbor or using its Python object API.

## 7. Local storage

The local layout SHOULD be human-inspectable and equivalent to:

```text
<backend>/
  manifest.json
  grove-log.jsonl
  groves/
    <grove-id>/
      manifest.json
      asset-log.jsonl
      assets/
        <asset-id>/
          manifest.json
          revision-log.jsonl
          revisions/
            <revision>/
              <logical paths>
  .arbor-tmp/
```

The three `manifest.json` files are system-controlled and have exactly this logical content in schema version 1:

```json
{"schema_version": 1}
```

Arbor MUST reject unsupported schema versions with `Invalid`.
Manifests and logs MUST NOT contain backend paths or other machine-specific configuration.
Internal paths such as `.arbor-tmp` MUST NOT appear in public listings.

Importing `arbor` and constructing `LocalArbor(path)` MUST NOT access or validate any backend.
Construction records configuration and produces a disconnected backend object even when the configured path does not exist.
Calling `backend.init()` MUST require a new or empty directory, create the top-level manifest, empty grove log, `groves` directory, and internal staging directory, mark the instance connected, and return that instance.
Calling `backend.connect()` MUST check only that the top-level directory and manifest exist, that the manifest has the required shape, and that its schema version is supported; it then marks and returns the connected instance.
Calling `connect()` on a connected instance MUST return that instance without additional validation.
Calling `init()` on a connected instance MUST fail with `Conflict`.
Other operations on a disconnected backend MUST fail with `Conflict`.
The top-level manifest is sufficient evidence that the path is an Arbor backend; connecting MUST NOT recursively inspect groves, assets, revisions, or logs.

Validation is explicit and potentially expensive.
`backend.validate()` MUST recursively validate the complete backend, while `grove.validate()` MUST validate the selected grove and its assets.
Validation MUST check the expected directory structure, manifests, logs, numeric revision directories, and stored revision file types within its scope.
Normal operations MAY validate the particular manifest, log, or directory they access, but MUST NOT trigger unrelated recursive validation.

The configured local directory is authoritative and is the source of truth.
Users can inspect it without Arbor, although modifying Arbor-controlled files directly may make the backend invalid.

## 8. Errors

The public API has three domain-error categories:

- `Invalid`: malformed IDs, paths, manifests, logs, or payloads;
- `NotFound`: a missing grove, asset, or revision; and
- `Conflict`: an existing current ID or download destination, or an operation forbidden by current state.

These errors SHOULD identify the relevant grove, asset, revision, or path without exposing unrelated filesystem details.
Unexpected operating-system failures MAY propagate with their original exception type.

## 9. Minimum acceptance criteria

Automated tests MUST show that Arbor can:

1. Initialize a temporary backend, create two groves, list them lexicographically, and reject a duplicate current ID.
2. Rename a grove and an asset without changing their contents; record their creation and rename events; and warn when a historical ID is reused.
3. Upload single-file revision 0 and multi-file revision 1, preserving every path and byte on download.
4. List revision paths without downloading and reject an existing download destination.
5. Amend the latest revision by complete replacement while retaining its number and earlier log events.
6. Destroy a revision, omit it from listing and download, and never reuse its number.
7. Reject amendment or destruction of a non-latest revision.
8. Reject invalid IDs and paths, symbolic links, and empty uploads or amendments.
9. Construct a disconnected backend without filesystem access, initialize new storage through `init()`, and connect to existing storage through a shallow, idempotent `connect()`.
10. Detect nested corruption through explicit backend and grove validation and through an operation that accesses the corrupted resource.
11. Fault-inject ordinary exceptions during every mutation and preserve the prior visible state.
12. Simulate process interruption at staging and rename boundaries, then recover to a complete old or new state without mixed or partial payloads.
13. Exercise all required capabilities through both the Python API and CLI.
14. Reject unsupported manifest versions and malformed JSONL events.
15. Select CLI configuration according to the required precedence, discover the nearest ancestor configuration, resolve backend paths relative to it, and explain a failed search.

## 10. Non-goals and deferred work

Version 1 does not provide:

- Azure Blob or other remote storage backends;
- a generalized low-level protocol for remote storage operations;
- defined behavior for overlapping operations within one backend;
- exactly-once retries or complete audit logging across abrupt termination;
- recovery from filesystem corruption or `fsync`-level durability;
- consistent upload or amendment while another process changes the source directory;
- direct in-memory loading of revisions;
- arbitrary historical amendment or destruction;
- alternate listing orders or download overwrite;
- tagging, user metadata, schemas, or queries over file contents;
- workflow execution, relationships among assets, or data transformation;
- authentication, authorization, download auditing, or a web interface; or
- deduplication, retention policies, or deletion of whole groves or assets.
