# BLP Studio

Standalone texture viewer and converter for Windows x64. First public beta:
**0.1.0-beta.1**. [Download the portable ZIP](https://github.com/Kobiesan/blp-studio/releases).
Extract it and open BLPStudio.exe. No installation or Python setup is required.
The executable is currently unsigned.

Open BLPStudio.exe or Launch.cmd. Portable Windows x64 application with Python,
Pillow, Tcl/Tk and the image codecs bundled. No external converter is needed.

## Viewer

Open textures, browse a folder, or drop files/folders onto the window. Inputs:
BLP1/BLP2, ordinary 2D DDS, PNG, JPEG, BMP and TGA. Ctrl+Left/Right changes files.
Details shows encoding, dimensions, size, alpha and available format metadata.

Zoom changes display size only: 100% means one screen pixel per texture pixel.
Choose 1%-1600%, Fit or 100%, use +/- or the wheel; Ctrl+plus/minus also zooms.
Scrollbars pan magnified textures. Only the visible region is drawn, and the
checkerboard is clipped to the image boundary at every scale.

Mipmap selects a smaller image actually stored in a BLP or DDS. Level 0 is the
original. Conversion always starts from the original, regardless of preview mip.
RGBA shows transparency, RGB hides it, and Alpha displays the alpha channel.
View > Resize window to image is optional.

Last folder and export settings persist in %APPDATA%/BLP Studio/settings.json.
Missing folders are ignored. User settings are not bundled in the application.
Help > Register for BLP files adds this executable to Windows Open With; choose
your default in Windows. The executable and window use the bomber artwork.

## Conversion

Choose an output format and Export options. Convert selected saves one copy;
Convert all exports the loaded list. Folder batch provides input extension
filters, recursive search, a separate output folder and retained directory
structure. Existing outputs are refused; use another name or output directory.
Flattened folder batches detect duplicate output names before starting.

Progress, Cancel and a per-file result log cover conversion jobs. DXT cancellation
is checked between four-row strips. Successful outputs are decoded and checked
before saving, with filename-only .conversion.json receipts.

## BLP Lab 0.5 feature checklist

Based on the supplied BLP Lab 0.5.0 English readme; independently implemented.

| Feature | BLP Studio support |
|---|---|
| BLP1 paletted | Palette trimming and Floyd-Steinberg dithering |
| BLP1 JPEG | Quality 1-100, progressive encoding, shared JPEG headers |
| BLP2 paletted | Palette trimming, dithering, separate alpha plane |
| BLP2 DXTC | Explicit DXT1/3/5, optional dithering |
| DDS true color / DXTC | RGB/RGBA, DXT1/3/5, selectable mip count |
| TGA paletted / true color | Palette trimming/dithering, top-left origin, RLE, cross-row packets |
| PNG settings | Compression 0-9; Adaptive/None/Sub/Up/Average/Paeth filters |
| JPEG settings | Quality 1-100 and progressive encoding |
| BMP saving | RGB or RGBA; alpha uses BITMAPV4 |
| Mipmap generation | Full chain or chosen count; Lanczos or Nearest resizing |
| Alpha handling | Preserve, opaque, remove, auto-remove constant alpha, transparent one-pixel border |
| Batch conversion | Extension filters, subfolders and preserved folder structure |
| Batch BLP optimization | Folder batch > Optimize BLP; progress and size-savings log |
| Single BLP optimization | Optimize BLP saves a lossless repacked copy |
| BLP1 comments | Comments edits unused header slots without changing file size |
| Texture details | BLP/DDS headers and available raster metadata |
| Viewer/navigation | Zoom, stored mips, RGB/alpha/transparency, folders, hotkeys, file drops |
| File association | Optional per-user Open With registration |

Improvements include folder/settings persistence, cancellation, viewport-only
rendering, collision checks, distinct DXT choices and validated conversion receipts.

## Format details

DXT and JPEG are lossy; palettes reduce colors. DXT1 alpha is binary, DXT3 has 16
alpha levels, and DXT5 uses an interpolated alpha palette per block. Paletted BLP
preserves alpha separately. PNG and true-color output preserve pixels unless
alpha processing is selected. JPEG has no alpha.

BLP1 comments use BLP Studio's tagged UTF-8 layout in unused header slots;
interchange with BLP Lab comments is not guaranteed. Capacity depends on mip
count. BLP2 has no equivalent header-comment facility.

Optimization removes gaps, trailing bytes and unused palette entries, verifying
every mip payload and decoded image remain unchanged. Palette trimming is
optional because some consumers expect the full 256-entry palette.

Cube maps, DDS arrays and volume textures are outside the original non-complex
DDS scope. Non-power-of-two BLPs can be exported, but game clients may require
power-of-two textures. BLP dimensions are limited to 16384 pixels per side.

## Command line/source

BLPStudio.exe input.png output.blp --format "BLP2 DXT5" --mipmaps 0

BLPStudio.exe input.blp --inspect

BLPStudio.exe input.blp smaller.blp --operation optimize

BLPStudio.exe input.blp commented.blp --operation comment --comment "Example"

An input alone opens the viewer. Source entry point: blp_studio.py; portable
PyInstaller recipe: BLPStudio.spec. Checks: test_blp_studio.py, test_formats.py
and Windows hidden-window test_desktop.py.

## Building from source

Install Python 3.12 x64 with Tk support and run `./build.ps1` in PowerShell.
The script creates a local virtual environment, installs pinned dependencies,
runs tests, builds the executable and creates a ZIP plus SHA256 checksum in dist/.
To use a specific Python executable: `./build.ps1 -Python 'path/to/python.exe'`.

Manual build: create/activate a virtual environment, install
`requirements-build.txt`, then run `python -m PyInstaller --noconfirm BLPStudio.spec`.
Run `python test_release.py dist/BLPStudio.exe` and
`python package_release.py dist/BLPStudio.exe`. GitHub Actions runs the same checks.

The source is MIT licensed; see LICENSE, THIRD_PARTY_NOTICES.md and ASSETS.md.
Please report bugs through GitHub Issues with the encoding, dimensions, error
message and a small sample you have permission to share. CONTRIBUTING.md describes
the test workflow. Source tests use generated images rather than game assets.

Uses Python, Pillow and Tcl/Tk. Format references:
[Magos BLP1 specification](https://github.com/Kanma/BLPConverter/blob/master/doc/MagosBlpFormat.txt),
[BLPConverter](https://github.com/Kanma/BLPConverter/blob/master/blp.cpp),
[Pillow](https://github.com/python-pillow/Pillow/tree/main/src/PIL).
