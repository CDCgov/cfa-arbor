# cfa-arbor

arbor is a lightweight tool for sharing data.
It enforces some simple storage conventions and abstracts over file systems, which should make it easier to collaborate.

## Use case and design principles

Imagine you're working on a simulation project.
You might want to:

1. Pull a raw data file from the internet and cache it in a canonical place.
1. Cache intermediate files so that every collaborator doesn't need to regenerate them.
1. Share results in a canonical way, so that collaborators know where to find the "latest" results.

arbor abstracts over the storage backend where data is stored, and uses a simple hierarchy to make data discoverable and shareable:

1. A *grove* is a collection of related pieces of data, like a project.
1. An *asset* is a data set or product.
1. Each asset is made up of *versions*, which are the actual payload of files associated with the asset.

arbor tries to keep things really simple:

- The layout within the storage backend is transparent to a human.
  You could look in the storage yourself and understand the layout, without arbor.
- arbor keeps lightweight metadata, like a log of actions and a note about which asset version is the latest one.
- arbor allows every asset (and version of that asset) to have associated metadata.
  It does not enforce any structure on that metadata.
- arbor doesn't enforce any specific permissions or restrictions.
  Whatever you could touch without arbor, you can touch with arbor.
- If you have the grove configured, and you know the asset ID, then that's all you need to know to get the relevant data.

## Related tools

arbor is very similar to [pins](https://rstudio.github.io/pins-python/).
Pins currently supports only single files as its assets.
([I'm asking](https://github.com/rstudio/pins-python/issues/358) to see if that will change.
If so, arbor could probably be replaced.)

Git-like data management, like [lakeFS](https://lakefs.io/), is another approach.

## Overview

The grove front-end model is independent of the filesystem backend.
Configuring arbor is about configuring the backend.
You can use a per-project `arbor.toml` like:

```toml
grove = "/path/to/my-grove"

[filesystem]
protocol = "local"
```

arbor can be called with an explicit config path using `Grove.from_config("/path/to/arbor.toml")`.
If `Grove.from_config()` is called, without an explicit path, arbor uses the config path in the environmental variable `ARBOR_CONFIG`.
If that variable is not present, arbor searches for an `arbor.toml` in the current directory, then upward across directories.

This configuration lets you skip instantiating backend objects manually:

```python
from arbor import Grove

grove = Grove.from_config()

# you can set up a new backend storage environment
grove.setup()

# See what assets are in a grove
grove.list_assets()

# Pick out an asset
asset = grove.asset("friction-surface")

# Download the latest version of the asset locally
asset.download("/download/to/local/path/")

# Upload a new version of an asset
asset.upload("/upload/from/local/path/")

# Rename an asset
asset.rename("motorized-friction-surface")
```

## Command-line configuration

You can perform most of arbor's actions through a CLI:

```console
arbor status
arbor setup
arbor log
arbor validate
arbor list-assets
arbor create ASSET

arbor asset ASSET rename NEW-ID
arbor asset ASSET upload SOURCE [--metadata METADATA]
arbor asset ASSET list-versions
arbor asset ASSET latest-version
arbor asset ASSET list-data [--version VERSION]
arbor asset ASSET metadata [--version VERSION]
arbor asset ASSET mode [--version VERSION]
arbor asset ASSET download DEST [--version VERSION]
arbor asset ASSET validate [--version VERSION]
```

## File structure

The backend file structure is meant to be transparent to a human:

```
grove-root
  manifest.json
  log.jsonl
  assets/
    asset-id1/
      manifest.json
      versions/
        version-id1/
          manifest.json  # including asset metadata
          data/
            data-file1.txt
```

## Azure Blob support

Ensure that the optional dependencies are installed.

```toml
grove = "path/to/grove-root"

[filesystem]
protocol = "abfs"
account_name = "my-storage-account-name"
```

## Future functionality

Some useful behavior is deferred:

- uploads/downloads for multiple files
- remote storage backends such as Azure Blob
- concurrency control
- destroying and amending versions
- download overwrite
- loading a revision directly into memory, especially when it contains multiple files

## Admins

- Scott Olesen (CDC/CFA) <ulp7@cdc.gov>

## Disclaimers

### General Disclaimer

This repository was created for use by CDC programs to collaborate on public health related projects in support of the [CDC mission](https://www.cdc.gov/about/cdc/index.html).
GitHub is not hosted by the CDC, but is a third party website used by CDC and its partners to share information and collaborate on software.
CDC use of GitHub does not imply an endorsement of any one particular service, product, or enterprise.

### Public Domain Standard Notice

This repository constitutes a work of the United States Government and is not subject to domestic copyright protection under 17 USC § 105.
This repository is in the public domain within the United States, and copyright and related rights in the work worldwide are waived through the [CC0 1.0 Universal public domain dedication](https://creativecommons.org/publicdomain/zero/1.0/).
All contributions to this repository will be released under the CC0 dedication.
By submitting a pull request you are agreeing to comply with this waiver of copyright interest.

### License Standard Notice

This repository is licensed under Apache-2.0 or later.

This source code in this repository is free: you can redistribute it and/or modify it under the terms of the Apache License, Version 2.0, or (at your option) any later version.

This source code in this repository is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the Apache Software License for more details.

You should have received a copy of the Apache Software License along with this program.
If not, see http://www.apache.org/licenses/LICENSE-2.0.html

The source code forked from other open source projects will inherit its license.

### Privacy Standard Notice

This repository contains only non-sensitive, publicly available data and information.
All material and community participation is covered by the [Disclaimer](https://github.com/CDCgov/template/blob/master/DISCLAIMER.md) and [Code of Conduct](https://github.com/CDCgov/template/blob/master/code-of-conduct.md).
For more information about CDC's privacy policy, please visit [http://www.cdc.gov/other/privacy.html](https://www.cdc.gov/other/privacy.html).

### Contributing Standard Notice

Anyone is encouraged to contribute to the repository by [forking](https://help.github.com/articles/fork-a-repo) and submitting a pull request.
(If you are new to GitHub, you might start with a [basic tutorial](https://help.github.com/articles/set-up-git).)
By contributing to this project, you grant a world-wide, royalty-free, perpetual, irrevocable, non-exclusive, transferable license to all users under the terms of the [Apache Software License v2](http://www.apache.org/licenses/LICENSE-2.0.html) or later.

All comments, messages, pull requests, and other submissions received through CDC including this GitHub page may be subject to applicable federal law, including but not limited to the Federal Records Act, and may be archived.
Learn more at <http://www.cdc.gov/other/privacy.html>.

### Records Management Standard Notice

This repository is not a source of government records but is a copy to increase collaboration and collaborative potential.
All government records will be published through the [CDC web site](http://www.cdc.gov).
