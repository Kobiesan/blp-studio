# Contributing

Use Python 3.12 x64 with Tk support. Install requirements-build.txt in a virtual
environment. Run test_blp_studio.py, test_formats.py and test_desktop.py on Windows.
Build using BLPStudio.spec, then run test_release.py with the executable path.

For decoder bugs, include the encoding, dimensions, expected result and exact
error. Share only sample files you have permission to redistribute. Prefer small
synthetic regression images. Keep runtime paths and settings out of commits.

Changes to codecs should test independently decoded output, alpha, mip ranges
and malformed input. Keep conversion non-destructive and cancellation responsive.
