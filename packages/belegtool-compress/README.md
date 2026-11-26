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
  pdfium is not thread safe, so every rasterizer call runs under one process-wide **priority lock**; the pool
  gives fairness (an interactive page overtakes background work), not raw throughput.
- `raster.py` is the rasterizer port: `raster.open_pdf(bytes)` -> `page_count` / `page_size(i)` / `render(i, dpi, gray)`.
  The production backend is **pypdfium2** (BSD-3-Clause / Apache-2.0, bundled pdfium); `BELEG_RASTER` selects a
  backend (`pdfium` is the default, other backends can be registered with `raster.register_backend`).
  `/UserUnit` is honoured, grey = RGB render + Pillow luminance, pages are drawn with annotations and form fields on white.
- `pixels.capped_dpi` / `capped_dpi_for_size` clamp the render DPI so a page stays within `MAX_RENDER_PIXELS` (64 MP).

## Install

```
pip install .                      # from this directory
pip install "belegtool-compress @ git+https://github.com/<owner>/belegtool-compress.git@v0.1.0"
pip install -e .[dev] && pytest    # development (dev pulls PyMuPDF, see below)
```

Dependencies: pypdfium2, Pillow, pikepdf, pypdf.

## Licensing note - rasterizer

Rasterizing uses **pypdfium2** (BSD-3-Clause / Apache-2.0; the wheel bundles the pdfium binary under BSD-3-Clause and
permissive third-party licences, listed in the wheel's `dist-info/licenses/`). PyMuPDF/MuPDF (AGPL-3.0 / Artifex
commercial) is **not a dependency** of the library; it is only the optional parity oracle of the tests
(`pip install .[oracle]`, tests skip without it). Measured parity with PyMuPDF: `docs/pdfium-spike.md` in the main repository.

## License

AGPL-3.0-or-later, see [LICENSE](LICENSE) and [COPYING](COPYING) (full AGPL text) - the same as the main project. As in the main project
([DigitalerUnterlagenOrdner](https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner)), a
**commercial license** is available for closed-source or proprietary use (contact:
tobias.a.w.heinrich@gmail.com; terms in that repository's `LICENSE_COMMERCIAL.md`). Contributions
are subject to the project's **Contributor License Agreement** (see `CONTRIBUTING.md` of the main
repository): you grant the maintainer a perpetual, worldwide, non-exclusive, royalty-free,
irrevocable right to use, modify and redistribute your contribution under any license, including
commercial licenses. The full wording of the CLA is part of this package: [`CONTRIBUTING.md`](CONTRIBUTING.md).
