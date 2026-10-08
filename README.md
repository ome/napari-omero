# napari-omero

[![License](https://img.shields.io/pypi/l/napari-omero.svg?color=green)](https://github.com/ome/napari-omero/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/napari-omero.svg?color=green)](https://pypi.org/project/napari-omero)
[![Python Version](https://img.shields.io/pypi/pyversions/napari-omero.svg?color=green)](https://python.org)
[![CI](https://github.com/ome/napari-omero/actions/workflows/ci.yml/badge.svg)](https://github.com/ome/napari-omero/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ome/napari-omero/branch/main/graph/badge.svg)](https://codecov.io/gh/ome/napari-omero)
[![conda-forge](https://img.shields.io/conda/vn/conda-forge/napari-omero)](https://anaconda.org/conda-forge/napari-omero)

This package provides interoperability between the
[OMERO](https://www.openmicroscopy.org/omero/) image management platform, and
[napari](https://github.com/napari/napari): a fast, multi-dimensional image
viewer for python.

It provides a GUI interface for browsing an OMERO instance from within napari,
as well as command line interface extensions for both OMERO and napari CLIs.

![demo](https://github.com/ome/napari-omero/blob/main/demo.gif?raw=true)

## Features

- GUI interface to browse remote OMERO data, with thumbnail previews.
- Load remote nD images from an OMERO server into napari
  - Planes are loading on demand as sliders are moved ("lazy loading").
  - Loading of pyramidal images as napari multiscale layers
  - OMERO rendering settings (contrast limits, colormaps, active channels, current
  Z/T position) are applied in napari
- Load ROIs from OMERO server into napari as `Shapes` or `Points`
- Upload napari annotation Layers (`Labels`, `Shapes` and `Points`) to OMERO.
- Session management (login memory)

> [!NOTE]
> The user experience when working with remote images, particularly large multiscale (pyramidal) ones, like whole slide images, can be significantly improved by enabling the experimental asynchronous mode (n the GUI in `Preferences > Experimental > Render Images Asynchronously` or with the environmental variable `NAPARI_ASYNC=1`).

### as a napari dock widget

To launch napari with the OMERO browser added, [install](#installation) this
package and run:

```bash
napari-omero
```

The OMERO browser widget can also be manually added to the napari viewer using the Plugins menu
or programmatically using:

```python
import napari

viewer = napari.Viewer()
viewer.window.add_plugin_dock_widget('napari-omero')

napari.run()
```

### as a napari reader contribution

This package provides a napari reader contribution that accepts OMERO resources as
"proxy strings" (e.g. `omero://Image:<ID>`) or as [OMERO webclient
URLS](https://help.openmicroscopy.org/urls-to-data.html).

```python
import napari
viewer = napari.Viewer()

# omero object identifier string
viewer.open("omero://Image:1", plugin="napari-omero")

# or URLS: https://help.openmicroscopy.org/urls-to-data.html
viewer.open("http://yourdomain.example.org/omero/webclient/?show=image-314", plugin="napari-omero")
```

these will also work on the napari command line interface, e.g.:

```bash
# quotes are needed if using zsh
napari "omero://Image:1"
# or
napari "http://yourdomain.example.org/omero/webclient/?show=image-314"
```

### as an OMERO CLI plugin

This package also serves as a plugin to the OMERO CLI

```bash
omero napari view Image:1
```

- ROIs created in napari can be saved back to OMERO via a "Save ROIs" button.
- napari viewer console has BlitzGateway 'conn' and 'omero_image' in context.

## installation

`napari-omero` requires Python 3.10 or newer (note: current napari releases
require 3.11+). It depends on `omero-py`, which needs `zeroc-ice` 3.6.
`zeroc-ice` is not available as a prebuilt wheel on PyPI, so the easiest way to
get it is from conda-forge.

### from conda-forge (conda or pixi)

Everything, including `omero-py` and `zeroc-ice`, is available from the
`conda-forge` channel. To install the plugin, napari and a Qt backend into an
existing conda environment:

```sh
conda install -c conda-forge napari-omero pyside6
```

Or, with [pixi](https://pixi.sh), install it as a standalone app. This puts the
`napari-omero` and `napari` commands on your PATH, and you don't have to manage
an environment:

```sh
pixi global install napari-omero --with pyside6 --expose napari-omero --expose napari
```

Upgrade later with `pixi global update napari-omero`.

### from PyPI (uv or pip)

`napari-omero` is on PyPI, but `zeroc-ice` (needed by `omero-py`) is only
published there as source code, which is hard to build. [Glencoe Software
provides prebuilt `zeroc-ice` wheels](https://www.glencoesoftware.com/blog/2023/12/08/ice-binaries-for-omero.html) for **Python 3.10 to 3.12**. Point the
installer at the link for your platform:

| Platform | `--find-links` URL |
| --- | --- |
| macOS (Intel and Apple Silicon) | `https://github.com/glencoesoftware/zeroc-ice-py-macos-universal2/releases/expanded_assets/20240131` |
| Linux x86_64 | `https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/expanded_assets/20240202` |
| Linux aarch64 | `https://github.com/glencoesoftware/zeroc-ice-py-linux-aarch64/releases/expanded_assets/20240620` |
| Windows x86_64 | `https://github.com/glencoesoftware/zeroc-ice-py-win-x86_64/releases/expanded_assets/20240325` |

With [uv](https://docs.astral.sh/uv/), install it as a standalone app. This puts
the `napari-omero` and `napari` commands on your PATH:

```sh
uv tool install --python 3.12 "napari-omero[all]" --with-executables-from napari \
    --find-links <URL for your platform>
```

Upgrade later with `uv tool upgrade napari-omero`.

Or install it into an existing Python 3.10–3.12 environment with pip:

```sh
pip install "napari-omero[all]" --find-links <URL for your platform>
```

`[all]` is the same as `napari[all]`, which includes a Qt backend (PyQt6).

## issues

| ❗  | This is alpha software & some things will be broken or sub-optimal!  |
| --- | -------------------------------------------------------------------- |

- experimental & definitely still buggy!  [Bug
  reports](https://github.com/ome/napari-omero/issues/new) are welcome!
- remote loading can be very slow still... though this is not strictly an issue
  of this plugin.  Datasets are wrapped as delayed dask stacks, and remote data
  fetching time can be significant.  Enabling [asynchronous
  rendering](https://napari.org/stable/guides/rendering.html#asynchronous-slicing) in
  napari improves the subjective performance... but remote data loading
  will likely always be a limitation here.
  To try asyncronous loading, start the program with `NAPARI_ASYNC=1 napari-omero`
  or look in the Preferences on the Experimental tab.
  Also, keep an eye on the [napari progressive loading implementation progress](https://github.com/napari/napari/issues/5561).
- For plugin developers: As napari-OMERO provides images as lazily-loaded [dask arrays](https://docs.dask.org/en/stable/array.html),
  napari-plugins need to account for this when retrieving data from napari layers.
  Keep in mind that forwarding the data to processing steps in plugins may lead to signficant loading
  and processing times.

## contributing

Contributions are welcome! First clone the repo:

```bash
git clone https://github.com/ome/napari-omero.git
cd napari-omero
```

The development environment is configured in `pyproject.toml` for both
[pixi](https://pixi.sh) and [uv](https://docs.astral.sh/uv/). Either way you get
an editable install with the test dependencies and a Qt backend: PyQt6 with uv
(as PyPI users get) and PySide6 with pixi (as conda-forge users get).

**pixi** gets `omero-py` and `zeroc-ice` from conda-forge, so it
works with any supported Python version:

```bash
pixi run test             # creates the environment on first use, then runs pytest
pixi run napari           # or: pixi shell
```

**uv** uses [Glencoe Software's prebuilt `zeroc-ice`
wheels](https://github.com/glencoesoftware?q=zeroc-ice-py), which exist for
Python 3.10 to 3.12 only, so the repo pins 3.12 in `.python-version`:

```bash
uv run pytest             # creates .venv on first use
uv run napari
```

**conda + pip** also still works:

```bash
conda create -n napari-omero -c conda-forge python=3.12 omero-py
conda activate napari-omero
pip install -e ".[dev]"   # quotes are needed on zsh
```

To maintain good code quality, this repo uses
[ruff](https://github.com/astral-sh/ruff),
[mypy](https://github.com/python/mypy).

The checks are configured in `.pre-commit-config.yaml` and run with
[prek](https://github.com/j178/prek). It is included in the uv and pixi dev environments. To run the
checks automatically on every commit:

```bash
uv run prek install       # or: pixi run prek install
uv run prek run --all-files   # run all checks once by hand
```

The original OMERO data loader and CLI extension was created by [Will
Moore](https://github.com/will-moore).

The napari reader plugin and GUI browser was created by [Talley
Lambert](https://github.com/tlambert03/)

## release

To push a release to PyPI, one of the maintainers needs to do, for example:
```sh
git tag -a v0.2.0 -m v0.2.0
git push upstream --follow-tags
```
Then, the workflow should handle everything!
