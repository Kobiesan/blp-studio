# Changelog

## 0.1.0-beta.1

First public beta for Windows x64.

- BLP1/BLP2, DDS and common raster viewing/conversion.
- Paletted and JPEG BLP1; paletted and DXT1/3/5 BLP2.
- Format controls, alpha handling and selectable mipmaps.
- Recursive batches, lossless BLP optimization and BLP1 header comments.
- Persistent folders/settings, drag-and-drop and viewport zoom/panning.
- Standalone executable with no external conversion backend.

Known limits: ordinary 2D DDS only; BLP1 comments use a private tagged layout;
DXT/JPEG are lossy; existing output files are deliberately not overwritten.
The Windows executable is unsigned.
