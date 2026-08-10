# Arbor specification

## 1. Purpose

Arbor is a small tool for sharing and versioning heterogeneous files during infectious disease responses.
It stores numbered *revisions* of named *assets* within a *grove* on a configured *storage backend*.
It is not a workflow engine, database, data catalog, or general-purpose cloud filesystem.

The words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

## 2. Model

Arbor organizes data on a storage backend as groves, assets, and revisions.
A storage backend is a configured storage namespace: either an Azure Blob container and blob-name prefix, or a local filesystem directory used for testing.
It is not a named resource stored inside Arbor, and Arbor does not create or list storage backends.
Arbor initializes the configured namespace with a top-level manifest but does not provision an Azure account or container.
A storage backend contains groves and an append-only grove log.
A grove contains assets and an append-only asset log.
An asset contains revisions numbered from zero and an append-only revision log.
A revision is a non-empty set of files, identified within the set by their relative paths.

```text
storage backend
  grove log
  grove
    asset
      revision 0 = {path: bytes, ...}
      revision 1 = {path: bytes, ...}
      ...
      revision log
    asset log
```

Groves, assets, and revisions have no user metadata.
Arbor does not interpret file contents or give special meaning to files such as `README.md` or `METADATA.json`.
Uploaders MAY include such files in a revision.

### 2.1 Identity

Users supply grove and asset IDs.
Each MUST:

- contain 1 to 80 characters;
- match `[A-Za-z0-9][A-Za-z0-9._-]*`; and
- be unique among its siblings (groves within a storage backend and assets within a grove).

Creating an existing grove MUST fail.
A grove ID is its current name within the storage backend and MAY change through the rename operation.
Renaming does not create a new grove or change its assets.
An asset comes into existence when revision 0 and the corresponding asset-creation event are committed; an asset cannot be created empty.
An asset ID is its current name within the grove and MAY change through the rename operation.
Renaming does not create a new asset or change its revisions.

The next revision of an asset MUST have number `n + 1`, where `n` is the greatest revision number ever committed for that asset, including destroyed revisions.
Committed revision numbers MUST NOT be skipped or reused.
A failed upload does not create a revision.

### 2.2 Versioning, amendment, and destruction

To publish a new version of an asset, a user uploads the next revision; files are not implicitly carried forward from an earlier revision.
The public API MUST also allow a committed, non-destroyed revision to be amended by replacing its complete set of paths and bytes without allocating a new revision number.
An amendment MUST satisfy the same file and path validation rules as an upload and MUST append an amendment event to the asset's revision log.
Multiple amendments of one revision are allowed, and each MUST append a distinct event.
Amendment history records when amendments occurred but does not retain earlier payloads.
An amendment does not change the revision number, the original upload time, or which revision number is latest.

The public API MUST allow a committed revision to be destroyed.
Destruction removes that revision's payload and appends a destruction event to its asset's revision log.
It MUST NOT remove or alter the earlier upload event, and a destroyed revision's number MUST NOT be reused.
A revision that has already been destroyed MUST NOT be destroyed again.
A destroyed revision MUST NOT be amended.

Unless explicitly requested otherwise, revision listings include only revisions whose payloads have not been destroyed.
"Latest revision" means the non-destroyed revision with the greatest number, not a revision selected by a timestamp or by inspecting its files.
If an asset has no non-destroyed revisions, asking for its latest revision MUST fail with revision not found; the asset itself continues to exist.

## 3. Files

A revision contains at least one regular file.
Its logical paths MUST:

- use `/` separators and be relative and non-empty;
- contain no empty, `.` or `..` component or NUL character; and
- be unique within the revision.

Directories are implicit.
Uploads MUST reject symbolic links, device files, sockets, and other special files.
A round-trip upload and download MUST preserve every logical path and byte.

## 4. Logs and time

Each asset has one append-only revision log.
A committed revision has exactly one upload event recording its revision number and the time at which the upload committed:

```json
{
  "event": "uploaded",
  "revision": 1,
  "uploaded_at": "2026-08-10T18:30:00.123456Z"
}
```

Each revision amendment has exactly one event recording the revision number and the time at which the amendment committed:

```json
{
  "event": "amended",
  "revision": 1,
  "amended_at": "2026-08-10T18:45:00.123456Z"
}
```

A destroyed revision has exactly one later destruction event:

```json
{
  "event": "destroyed",
  "revision": 1,
  "destroyed_at": "2026-08-10T19:00:00.123456Z"
}
```

These are the only fields in revision-log events.
In particular, the log does not record downloads, actors, attempts, failures, file details, or user metadata.

Each grove has one append-only asset log.
Creating an asset records its initial ID and creation time:

```json
{
  "event": "created",
  "asset_id": "weekly-cases",
  "created_at": "2026-08-10T18:30:00.123456Z"
}
```

Renaming that asset records both names and the rename time:

```json
{
  "event": "renamed",
  "old_asset_id": "weekly-cases",
  "asset_id": "daily-cases",
  "renamed_at": "2026-08-11T13:00:00.123456Z"
}
```

These are the only fields in asset-log events.
A rename MUST fail if the old ID does not identify a current asset or the new ID is already in use.
After a rename commits, the old ID no longer resolves the asset and the new ID does.
Replaying the asset log in append order MUST determine each asset's current ID.

The storage backend has one append-only grove log.
Creating and renaming groves use events analogous to those in the asset log:

```json
{
  "event": "created",
  "grove_id": "2026-ebola",
  "created_at": "2026-08-10T17:00:00.123456Z"
}
```

```json
{
  "event": "renamed",
  "old_grove_id": "2026-ebola",
  "grove_id": "2026-filovirus",
  "renamed_at": "2026-08-11T14:00:00.123456Z"
}
```

These are the only fields in grove-log events.
A grove rename MUST fail if the old ID does not identify a current grove or the new ID is already in use.
After a rename commits, the old ID no longer resolves the grove and the new ID does.
Replaying the grove log in append order MUST determine each grove's current ID.

All event times MUST be generated by Arbor, represent UTC, and use RFC 3339 with a `Z` suffix.
Log listings MUST use append order.
Timestamps do not establish a total order and MAY be equal.

Existing log events MUST NOT be updated or deleted through the public API.
The guarantee applies only to operations performed through Arbor.

An upload is committed, and therefore visible for an existing asset, if and only if its upload event has been appended to the asset's revision log and its asset manifest exists.
The upload event is the revision's commit marker.
An amendment is committed when its amendment event is appended; the replacement payload and event MUST appear as one logical operation to public listings and downloads.
Revision destruction is committed when its destruction event is appended; after that event, the revision MUST be unavailable for listing or download and its payload MUST be removed from storage.
Asset creation is committed when its creation event is appended to the grove's asset log after revision 0 is committed; revision 0 and its asset MUST appear together in public listings.
An asset rename is committed when its rename event is appended to the grove's asset log.
A grove is committed when its creation event is appended to the storage backend's grove log.
A grove rename is committed when its rename event is appended to the storage backend's grove log.

## 5. Required operations

The public Python API and command-line interface MUST both provide these capabilities:

- create, list, and rename groves on a storage backend;
- create an asset by uploading revision 0;
- list assets in a grove;
- upload the next revision of an asset;
- list an asset's revisions in increasing numeric order;
- list a revision's file paths without downloading it;
- download a specified revision, or the latest revision resolved before the transfer begins;
- amend a specified revision;
- destroy a specified revision;
- rename an asset;
- list an asset's revision log in append order;
- list the grove's asset log in append order; and
- list the storage backend's grove log in append order.

Grove and asset listings MUST use lexicographic ID order unless the caller requests another supported order.

A download MUST retrieve every file in the selected revision and reproduce its paths below the destination.
It MUST fail rather than overwrite a local path unless the caller explicitly permits local overwrite.

An upload MUST validate and store the complete file set, then append its upload event last.
Appending the event MUST commit the revision.
An implementation MAY use a per-asset upload lock, but the initial implementation need not guarantee simultaneous uploads to one asset.

Amendment MUST validate and stage the complete replacement file set before changing the visible revision.
An incomplete amendment MUST leave the previous payload and revision log unchanged.
Destruction MUST append its destruction event and remove all files in the selected revision as one logical operation.
Once either step begins, Arbor MUST NOT return that revision from a new listing or download; interrupted destruction MAY require retry or cleanup to remove remaining payload files.
Incomplete uploads and asset or grove renames MUST be invisible to listings and downloads.
Retrying a failed upload MUST NOT alter a committed revision.
Retrying a failed amendment MUST either preserve the previous payload or converge on one completely amended payload with exactly one new amendment event.
Retrying a failed destruction MUST finish removal without adding a second event.
Retrying a failed asset or grove rename MUST converge on either the state before the operation or the completely committed state.

## 6. Storage

Arbor MUST use one internal backend protocol with local-filesystem and Azure Blob implementations.
This protocol is an implementation boundary, not a second user-facing API.
The Python API and CLI MUST behave the same for both backends; storage backend configuration selects the implementation.
Both interfaces MUST accept the same storage backend configuration format.
The CLI SHOULD delegate to the Python API rather than duplicate backend logic.

The local-filesystem implementation exists only for testing.
The Azure Blob implementation is the operational backend.

Azure Blob backend configuration MAY be committed to source control and MUST contain only non-secret values, such as the account or service endpoint, container, tenant, and optional blob-name prefix.
Credentials and access tokens MUST NOT be stored in storage backend configuration.
Authentication MUST use the user's external Azure credential context, such as an existing `az login` session.

Backends SHOULD expose a human-inspectable layout equivalent to:

```text
<backend directory or blob prefix>/
  manifest.json
  <grove-id>/
    manifest.json
    assets/
      <asset-id>/
        manifest.json
        revisions/
          <revision>/
            <logical paths>
```

The top-level, grove, and asset `manifest.json` files are system-controlled.
The storage backend's top-level manifest contains its grove log and MUST have exactly this logical content when first created:

```json
{"schema_version": 1, "grove_log": []}
```

The grove manifest contains its asset log, and each asset manifest contains its revision log.
When first created, before any events are appended, their logical content is respectively:

```json
{"schema_version": 1, "asset_log": []}
```

```json
{"schema_version": 1, "revision_log": []}
```

The versions apply independently to the storage backend, grove, and asset storage schemas.
Arbor MUST reject a manifest whose schema version it does not support.
These manifests are not user metadata and MUST NOT contain configuration or fields other than their schema version and specified log in schema version 1.

Implementations MUST ignore stored revision files that have no corresponding log entry.
Storage belonging to an uncommitted revision MAY be replaced or removed during retry or cleanup.

Existing log events MUST NOT be replaced through the public API.
Active committed revision files MAY be replaced only by amending that revision, and MAY be removed only by destroying that revision.
Provider URLs, credentials, container names, ETags, and signed URLs MUST NOT appear in IDs, logical paths, manifests, or log events.

The configured backend is authoritative.
The state of the configured storage backend is the source of truth.

## 7. Errors and integrity

The implementation MUST distinguish at least:

- grove not found;
- asset or revision not found;
- resource already exists or operation already in progress;
- invalid ID or file path;
- destination conflict during download;
- invalid storage backend, grove, or asset manifest or log;
- storage-provider failure.

Errors SHOULD identify the relevant storage backend, grove, asset, revision, or logical path without exposing storage secrets.

## 8. Minimum acceptance criteria

Automated tests MUST show that Arbor can:

1. Configure a temporary local-filesystem storage backend, write its version-1 top-level manifest and grove log, create two groves in it, and reject a duplicate grove ID.
2. Upload single-file revision 0 and multi-file revision 1 of one asset.
3. Preserve all paths and bytes when downloading either revision.
4. Return revision 1 as latest and list revisions as `[0, 1]`.
5. Reject invalid paths, duplicate paths, symbolic links, and empty uploads or amendments.
6. Hide an interrupted upload and reuse its uncommitted revision number.
7. Append exactly one minimal upload event per committed revision and no event for a failed upload or download.
8. Amend a revision, retain its upload and amendment events, expose only its replacement payload, preserve its revision number, and reject amendment of a destroyed revision.
9. Destroy a revision, retain all of its earlier events plus its destruction event, exclude it from listing and download, and allocate the next number after the greatest revision ever committed.
10. Rename an asset, preserve its revisions and revision log, reject a colliding name, and retain creation and rename events in the grove's asset log.
11. Rename a grove, preserve its assets and logs, reject a colliding name, and retain creation and rename events in the storage backend's grove log.
12. Reconstruct listings and current grove and asset names from only the configured storage backend.
13. Perform grove creation and rename, upload, amendment, destruction, asset rename, listing, and download through both the Python API and CLI against a local-filesystem storage backend.
14. Write version-1 top-level, grove, and asset manifests and reject unsupported storage backend, grove, and asset schema versions.

The local-filesystem implementation MUST support the complete automated test suite.
Azure-specific integration tests MAY require an explicitly configured test container and authenticated Azure session.

## 9. Non-goals

The initial implementation does not provide:

- tagging, user metadata, schemas, or queries over file contents;
- aliases, branches, merges, or relationships among assets;
- workflow execution or data transformation;
- download or access auditing;
- authentication or fine-grained authorization;
- deduplication, retention policies, or deletion of groves or whole assets;
- a web interface; or
- direct exposure of a provider's filesystem or object-store API.
