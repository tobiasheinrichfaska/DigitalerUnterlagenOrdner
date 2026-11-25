# belegtool-compress

Python library for **PDF compression**: render-based variants (`jpg` grayscale, `jpg_color`, `png`) and a
structural variant (`pikepdf`), returned smallest-first, with cooperative cancellation, a per-page pixel
budget against oversized-MediaBox bombs and CPU-fairness primitives for background pools. The import name is
`belegtool_compress`.

Extracted from the DigitalerUnterlagenOrdner (BelegTool) project, which consumes it for its compression
engine. It does not import the host application.

## What it does

- `compress_all_methods(pdf_bytes, dpi, config, cancel)` -> `{method: bytes}`, only candidates smaller than the
  input and with an **unchanged page count** (a variant that lost a page is never offered), smallest first.
- `CompressionConfig` centralises DPI, JPEG quality, PNG level, colour space, max width; `CompressionCancelled`
  is raised through the page loop when `cancel()` returns true.
- Large documents (>= 50 pages) rasterise on a capped, below-normal-priority thread pool (`cpu.py`:
  `worker_count`, `set_current_thread_below_normal`, `SystemCpuSampler`, RDP-aware caps, `BELEG_WORKERS` override).
  Thread parallelism is GIL-limited for PyMuPDF; the value is fairness, not raw throughput.
- `pixels.capped_dpi` clamps the render DPI so a page stays within `MAX_RENDER_PIXELS` (64 MP).

## Install

```
pip install .                      # from this directory
pip install "belegtool-compress @ git+https://github.com/<owner>/belegtool-compress.git@v0.1.0"
pip install -e .[dev] && pytest    # development
```

Dependencies: PyMuPDF, Pillow, pikepdf, pypdf.

## Licensing note - PyMuPDF

PyMuPDF/MuPDF is available under **AGPL-3.0 or an Artifex commercial license**. This package is AGPL-3.0-or-later
and therefore compatible; anyone redistributing it (or a product built on it) outside the AGPL needs their own
Artifex license for PyMuPDF. The commercial license of the main project cannot grant that on Artifex's behalf
(see `docs/licence-audit.md` in the main repository).

## License

AGPL-3.0-or-later, see [LICENSE](LICENSE) and [COPYING](COPYING) (full AGPL text) - the same as the main project. As in the main project
([DigitalerUnterlagenOrdner](https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner)), a
**commercial license** is available for closed-source or proprietary use (contact:
tobias.a.w.heinrich@gmail.com; terms in that repository's `LICENSE_COMMERCIAL.md`). Contributions
are subject to the project's **Contributor License Agreement** (see `CONTRIBUTING.md` of the main
repository): you grant the maintainer a perpetual, worldwide, non-exclusive, royalty-free,
irrevocable right to use, modify and redistribute your contribution under any license, including
commercial licenses.
