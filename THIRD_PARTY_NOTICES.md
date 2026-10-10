# Third-party notices

The MIT license in LICENSE covers BLP Studio's own code and documentation.
Third-party libraries retain their upstream licenses; full notices are in
licenses/. The application artwork is described separately in ASSETS.md.

The portable executable bundles Python 3.12, Tcl/Tk 8.6 and Pillow 12.3.0.
PyInstaller 6.22.3 supplies the executable bootloader under its distribution
exception. Pillow includes compiled image-library components; their notices
are preserved even for formats not exposed in BLP Studio's interface.

| Component | Notice |
|---|---|
| Python | Python-LICENSE.txt (PSF license and included notices) |
| Pillow | Pillow-LICENSE.txt (MIT-CMU) |
| Tcl / Tk | Tcl-LICENSE.txt / Tk-LICENSE.txt |
| PyInstaller | PyInstaller-LICENSE.txt (GPL with bootloader distribution exception) |
| libjpeg-turbo / IJG JPEG | libjpeg-turbo-LICENSE.txt / libjpeg-IJG-LICENSE.txt |
| zlib-ng | zlib-ng-LICENSE.txt |
| libtiff | libtiff-LICENSE.txt |
| Little CMS | LittleCMS-LICENSE.txt |
| OpenJPEG | OpenJPEG-LICENSE.txt |
| FreeType | FreeType-LICENSE.txt (FreeType License option) |
| WebP | WebP-LICENSE.txt / WebP-PATENTS.txt |
| AVIF / dav1d / AOM | AVIF-LICENSE.txt / dav1d-LICENSE.txt / AOM-LICENSE.txt / AOM-PATENTS.txt |
| OpenSSL | OpenSSL-LICENSE.txt |

This software uses the FreeType project. License source URLs are recorded in
licenses/SOURCES.json. Some dependencies appear through Pillow/Python imports
rather than a user-facing feature. Build environments can change which native
libraries are bundled; maintainers should review notices when updating them.

BLP Lab and BLP2PNG are not bundled and are not required. BLP Lab's feature list
informed the functionality; its executable and source code are not included.
