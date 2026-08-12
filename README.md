# cfa-arbor

## Overview

CFA/Predict/ARB data management

## Overview and design principles

arbor is a lightweight tool for sharing data.
Version 1 wraps a local filesystem directory with some simple conventions that will help ARB stay organized.

As an ARB analyst, I'm working in the context of some response (say, `2026-ebola`).
There are a few different things I want to do:

1. Pull a data file, like some mobility data, from the internet.
   I will use this in many analyses.
   It might never change.
   I upload this file.
2. Pull a data file, like daily case data, that changes on some basis, either *ad hoc* or regular.
   I will use this in downstream analyses.
3. Generate a result, like simulation trajectories.
   It was expensive to make this, so I want to share it.
   It will enable other analysts' downstream analyses.
   I upload this file.
   When I run another analysis later, I'll upload a revision.

arbor abstracts over the storage backend where data is stored, and uses a simple hierarchy to make data discoverable and shareable:

1. The *arbor* is the abstraction over the storage backend where the data physically live.
   Version 1 uses a local directory; remote backends such as Azure Blob are future work.
   An arbor consists of groves.
2. A *grove* is a collection of related pieces of data.
   We would use one grove per response.
   A grove can be renamed without changing its assets.
3. An *asset* is a data set or product.
4. Each asset is made up of *revisions*, which are the actual payload of files associated with the asset.
   A revision can be amended in place when its payload needs correction.

arbor tries to keep things really, really simple:

- The layout within the storage backend is transparent to a human.
  You could look in the blob storage yourself and understand the layout, without arbor.
- arbor keeps a little bit of metadata about when revisions are uploaded, amended, or destroyed, and when groves and assets are created or renamed.
  Otherwise, whatever metadata you want to include as part of a revision, is up to you.
  Including a `README.txt` or `metadata.json` in every revision is maybe wise, but arbor won't force you to do that.
- No arbor-specific permissions or restrictions.
  Whatever you could touch without arbor, you can touch with arbor.
- If you know the grove ID (e.g., `"2026-ebola"`) and the asset ID (`"friction-surface"`), and your storage backend is configured, then that's all you need to know to get the relevant data.

## A nominal walkthrough of functionality

*Actual APIs are subject to change!*

```python
# Configure a backend without touching the filesystem
arbor = arbor.LocalArbor("/path/to/backend")

# Create its storage:
arbor.init()
# connect to existing storage with `arbor.connect()`
# Connection checks only the top-level manifest; use `arbor.validate()` when you want a recursive integrity check.

# See what groves there are in this storage backend
arbor.list_grove_ids()

# Pick your grove
my_grove = arbor.grove("2026-ebola")

# See what assets are in a grove
my_grove.list_asset_ids()

# Pick out an asset
my_asset = my_grove.asset("friction-surface")

# Download the latest revision of the asset locally
my_grove.asset("friction-surface").save("/path/to/local/dir/")

# Upload a new revision of an asset
my_grove.asset("daily-cases").upload("/path/to/local/dir/")

# Amend the latest revision in place
my_grove.asset("daily-cases").amend("/path/to/local/dir/")

# Destroy a revision (which you noticed just after uploading had an error)
my_asset.get_rev_ids()
my_asset.burn(5)

# Rename a grove or asset
my_grove.rename("2026-bundibugyo")`
my_asset.rename("daily-case-counts")`
```

Perform the same operations through a small command-line interface that delegates to the Python API.

See [`docs/spec.md`](docs/spec.md) for more details.

## Command-line configuration

The CLI reads a project-local configuration such as:

```toml
[backend]
type = "local"
path = ".arbor"
```

The path is resolved relative to `arbor.toml`.
The CLI selects its configuration from `--config PATH`, then `ARBOR_CONFIG`, then the nearest `arbor.toml` found by searching upward from the working directory.
It reports the paths searched if none is found and never creates a missing configuration file.

```console
$ arbor status
$ arbor init
$ arbor grove-create 2026-ebola
$ arbor upload 2026-ebola daily-cases ./data
$ arbor revisions 2026-ebola daily-cases
```

Configuration discovery is CLI-only; the Python API always receives backend configuration explicitly.

## Future versions

Some useful behavior is deferred:

- remote storage backends such as Azure Blob
- loading a revision directly into memory, especially when it contains multiple files
- concurrency control for overlapping operations

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
