# pdfium-Spike: Rastern mit pypdfium2 statt PyMuPDF (Phase 1)

Stand 2026-11-26. Ziel: PyMuPDF/MuPDF (AGPL/Artifex, letzter roter Lizenzpunkt, siehe [`licence-audit.md`](licence-audit.md)) wird nur noch zum
**Rastern** gebraucht (`services/render.py`, `belegtool_compress/compress.py`). Ersatz-Kandidat: **pypdfium2 5.15.2**
(PyPI-Metadaten: `License: BSD-3-Clause, Apache-2.0, dependency licenses`; Wheel `py3-none-win_amd64` enthält `pypdfium2_raw/pdfium.dll`
(7,8 MB) und `dist-info/licenses/BUILD_LICENSES/*` mit pdfium (BSD-3), pdfium-binaries (MIT), FreeType, HarfBuzz, ICU, lcms, libjpeg-turbo, OpenJPEG,
libpng, libtiff, zlib, abseil, agg23, simdutf u. a.; pdfium-Build `159.0.8149.0` im hier getesteten Linux-Wheel).

Messwerkzeug: [`scripts/raster_compare.py`](../scripts/raster_compare.py) (PyMuPDF = Orakel, nur Dev). Es erzeugt die Testfälle selbst (Text, Vektor,
realistischer Farb-/Graustufen-Scan als JPEG, CMYK-JPEG, 16-bit-PNG, Transparenz, Annotationen + Formularfelder, `/Rotate` 90/180/270, MediaBox-Offset,
CropBox (+ gedreht), UserUnit 2, gebrochene Seitengröße, riesige MediaBox 200x200 in, verschlüsselt mit leerem Passwort, beschädigte xref) und misst bei
50/100/150/300 DPI. Lauf: `python scripts/raster_compare.py` (Exit 1 bei hartem Fail). Umgebung dieses Laufs: Linux, 4 vCPU, geteilter Host
(Zeitmessungen verrauscht: Best-of-11, abwechselnd gemessen).

## Entscheidung: GO (mit dokumentierten Abweichungen)

| Kriterium | Ergebnis | Urteil |
|---|---|---|
| (a) Pixelmaße identisch (±1 px) | in **allen** Fällen/DPI **exakt gleich** (inkl. Rotation, CropBox, MediaBox-Offset, gebrochene Größe, Pixelbudget-Deckelung auf 8000x8000). Beide runden `ceil(Punkt * DPI / 72)`. | erfüllt |
| (b) Pixelabweichung | Roh-MAD auf dichten Textseiten **3,3-5,9** (Ziel 3), realistischer Scan 1,2-3,4 (Ziel 6), reiner Rauschbild-Stresstest bis 7,5 (Downscale-Aliasing, informativ). Erklärung: reine Glyph-Antialiasing-/Gamma-Unterschiede (mittlere Helligkeit gleich auf 0,4/255, kein Versatz, optisch identisch - siehe unten). Nach Gauß-Glättung (r=1,5, entfernt AA, behält Struktur) **alle Fälle ≤ 3 (Text)/≤ 6 (Scan)** bis auf zwei Grenzfälle (CropBox 50 DPI 3,48; CropBox+Rotate 300 DPI 3,17; Subpixel-Ursprung der Crop-Box). Keine sichtbaren Defekte: Annotationen und Formularfelder werden gezeichnet, keine schwarzen Seiten, Rotation korrekt, bester Versatz 0 (max. 1 px bei MediaBox-Offset/16-bit-PNG). | **Abweichung klein + erklärt**, im Test dokumentierbar (Roh-Schwelle wird dort als `AA`-Toleranz formuliert, Struktur-Schwelle hart) |
| (c) JPEG-Größe der Kompressionsvarianten | alle Fälle innerhalb **±7 %** (Ziel 15 %); pdfium meist 3-6 % kleiner | erfüllt |
| (d) Geschwindigkeit je Seite | Median **≈ 1,0x** von fitz (1,01-1,06x in drei Läufen); Einzelfälle 0,64-0,84x (kleine Seite mit ~2x hochskaliertem Bild bei 150 DPI, Farbscan bei 100/150 DPI); bei 300 DPI bis 1,5x schneller | Median erfüllt, **1 von 9 Fällen knapp unter 0,7x** (absolut +4-6 ms je Seite) - dokumentiert |
| (e) Thread-Sicherheit | pdfium ist nicht thread-sicher: ein prozessweiter **Prioritäts-Lock** (Vordergrund vor Hintergrund) um jeden Aufruf; 8 Threads x 200 Seiten = 1600 Renderings, **0 Abweichungen** (Byte-Gleichheit gegen Einzelthread-Referenz). Gemessen durch den **ausgelieferten** Code (`belegtool_compress.raster`): Vordergrundseite 9-16 ms allein, **Median 16-30 ms / p95 25-42 ms bei 4 rasternden Hintergrund-Threads** (Ziel <= 2x + 1 Seite). Ein einfacher `threading.Lock` (ohne Priorität) erreichte das **nicht** (Median 63 ms bei 12,7 ms allein = 5x); ein Prioritäts-Lock, der nur je Aufruf vordrängt, ebenfalls nicht ganz (Median 29,6 vs. Grenze 26,9 ms, weil eine Seite aus open+size+render besteht und Hintergrundarbeit dazwischen kam). Erst eine **Foreground-Session mit Vorrang bis `close()`** hält die Hintergrundarbeit zwischen den Aufrufen draußen (Median 16-17 ms). | erfüllt (nur mit Prioritäts-Lock) |
| (f) Speicher | 1000 Seiten, Dokument je Aufruf geschlossen: RSS 0,0 MB Wachstum (250 -> 1000) | erfüllt |

**Nebenbefunde (alle in Phase 2 abgefangen und per Test gesichert):**

1. **`/UserUnit` wird von pdfium ignoriert** (Seite 2x so groß in Punkten, aber gleiche Pixelzahl; fitz/Acrobat skalieren). Abhilfe: Skala `dpi * UserUnit / 72`
   selbst anwenden (UserUnit je Dokument einmal gelesen und gecacht). Ohne das wären UserUnit-Seiten 2x zu klein gerastert.
2. **Natives Graustufen-Rendern von pdfium (`grayscale=True`) ist schlechter** als RGB-Render + PIL-`L` (Roh-MAD 9,1 gegen 4,9 auf Text): wir rendern daher
   immer RGB und konvertieren mit Pillow (`"L"`, ITU-R 601). Das ist ohnehin der bisherige Codepfad (`.convert(pil_mode)`).
3. **MuPDFs natives `csGRAY` hellt gesättigte Farben auf** (reines Rot 129/255, Grün 220, Blau 69 statt Luminanz 76/150/29). pdfium + Pillow-`L` liefert die
   echte Luminanz: farbige Elemente (Stempel, rote Schrift) werden in den **Graustufen-Varianten (`jpg`, `png`) etwas dunkler/kontrastreicher** als bisher.
   Auf weißem Papier ist das für die Lesbarkeit günstiger, aber ein sichtbarer Unterschied bei farbigen Flächen. Die Methode `jpg_color` ist nicht betroffen.
4. Skalierung: pdfium streckt die Seite auf die ganzzahlige Bitmap-Größe (`ceil`), fitz rendert mit exakter Skala. Ergebnis: bis ~1 px Versatz am unteren/rechten Rand
   (nur bei nicht ganzzahligen Seitenmaßen); innerhalb der Maßtoleranz (a).
5. Beschädigte xref und leeres Passwort: pdfium rendert beides wie fitz. Nicht-leeres Passwort: pdfium wirft beim Öffnen (wird zu `RasterError`, Seite wird übersprungen).
6. Der Prioritäts-Lock **serialisiert alle pdfium-Aufrufe** (auch die der Kompressions-/Vorschau-Pools): die Hintergrund-Pools bringen damit keine
   Parallelität mehr, nur noch Fairness. Vorher war es mit PyMuPDF ohnehin GIL-begrenzt (~1,2x auf 4 Threads, siehe CLAUDE.md). Echter Multicore-Gewinn
   bleibt ein (zurückgestellter) Prozess-Pool.
7. Nur auf Windows prüfbar: PyInstaller-Bündelung von `pypdfium2_raw/pdfium.dll`, Render unter RDP/Terminalserver, echte Scans (die Scan-Fälle hier sind synthetisch).

## Messwerte (Rohausgabe von `scripts/raster_compare.py`)

Legende Urteil: `ok` = unter allen Schwellen; `AA` = Roh-MAD über Schwelle, geglättete (Struktur-)MAD darunter (Antialiasing-Unterschied);
`GRENZE` = geglättete MAD bis 1,2x der Schwelle (dokumentierte Toleranz). `stress_*`/`cropbox_clip` sind informativ (Rauschbild bzw. Crop schneidet
durch Glyphen), ohne harte Schwelle.

fitz 2.1; pypdfium2 5.15.2; pdfium 159.0.8149.0@sourcebuild-toolchained

#### (a)+(b) Pixelmaße und mittlere Abweichung (RGB, 0..255)

| Fall | DPI | fitz | pdfium | MAD roh | MAD geglättet | Urteil |
|---|---|---|---|---|---|---|
| text_a4 | 50 | 414x585 | 414x585 | 5.24 | 1.74 | AA |
| text_a4 | 100 | 827x1170 | 827x1170 | 5.22 | 1.59 | AA |
| text_a4 | 150 | 1240x1755 | 1240x1755 | 4.89 | 1.92 | AA |
| text_a4 | 300 | 2480x3509 | 2480x3509 | 3.45 | 2.37 | AA |
| vector | 50 | 414x585 | 414x585 | 3.40 | 2.30 | AA |
| vector | 100 | 827x1170 | 827x1170 | 2.48 | 1.73 | ok |
| vector | 150 | 1240x1755 | 1240x1755 | 2.48 | 2.04 | ok |
| vector | 300 | 2480x3509 | 2480x3509 | 1.02 | 0.98 | ok |
| scan_color_jpeg | 50 | 414x585 | 414x585 | 3.35 | 1.15 | ok |
| scan_color_jpeg | 100 | 827x1170 | 827x1170 | 1.15 | 0.85 | ok |
| scan_color_jpeg | 150 | 1240x1755 | 1240x1755 | 0.79 | 0.72 | ok |
| scan_color_jpeg | 300 | 2480x3509 | 2480x3509 | 0.27 | 0.18 | ok |
| stress_noise_jpeg | 50 | 414x585 | 414x585 | 7.46 | 4.02 | AA |
| stress_noise_jpeg | 100 | 827x1170 | 827x1170 | 6.28 | 4.88 | AA |
| stress_noise_jpeg | 150 | 1240x1755 | 1240x1755 | 4.22 | 3.58 | ok |
| stress_noise_jpeg | 300 | 2480x3509 | 2480x3509 | 3.84 | 2.50 | ok |
| scan_gray_jpeg | 50 | 414x585 | 414x585 | 3.37 | 1.15 | ok |
| scan_gray_jpeg | 100 | 827x1170 | 827x1170 | 1.14 | 0.85 | ok |
| scan_gray_jpeg | 150 | 1240x1755 | 1240x1755 | 0.78 | 0.72 | ok |
| scan_gray_jpeg | 300 | 2480x3509 | 2480x3509 | 0.24 | 0.17 | ok |
| image_cmyk_jpeg | 50 | 414x585 | 414x585 | 5.51 | 3.11 | ok |
| image_cmyk_jpeg | 100 | 827x1170 | 827x1170 | 4.59 | 3.66 | ok |
| image_cmyk_jpeg | 150 | 1240x1755 | 1240x1755 | 3.48 | 3.17 | ok |
| image_cmyk_jpeg | 300 | 2480x3509 | 2480x3509 | 2.70 | 1.97 | ok |
| image_16bit_png | 50 | 278x278 | 278x278 | 1.18 | 1.17 | ok |
| image_16bit_png | 100 | 556x556 | 556x556 | 0.40 | 0.40 | ok |
| image_16bit_png | 150 | 834x834 | 834x834 | 0.60 | 0.60 | ok |
| image_16bit_png | 300 | 1667x1667 | 1667x1667 | 0.02 | 0.02 | ok |
| transparency | 50 | 414x585 | 414x585 | 1.19 | 0.91 | ok |
| transparency | 100 | 827x1170 | 827x1170 | 0.75 | 0.47 | ok |
| transparency | 150 | 1240x1755 | 1240x1755 | 0.62 | 0.48 | ok |
| transparency | 300 | 2480x3509 | 2480x3509 | 0.50 | 0.47 | ok |
| annot_forms | 50 | 414x585 | 414x585 | 5.88 | 1.99 | AA |
| annot_forms | 100 | 827x1170 | 827x1170 | 5.52 | 1.76 | AA |
| annot_forms | 150 | 1240x1755 | 1240x1755 | 4.99 | 2.06 | AA |
| annot_forms | 300 | 2480x3509 | 2480x3509 | 3.56 | 2.48 | AA |
| rotate_90 | 50 | 585x414 | 585x414 | 6.86 | 2.10 | AA |
| rotate_90 | 100 | 1170x827 | 1170x827 | 7.42 | 2.35 | AA |
| rotate_90 | 150 | 1755x1240 | 1755x1240 | 5.23 | 2.21 | AA |
| rotate_90 | 300 | 3509x2480 | 3509x2480 | 4.00 | 2.76 | AA |
| rotate_180 | 50 | 414x585 | 414x585 | 8.33 | 2.62 | AA |
| rotate_180 | 100 | 827x1170 | 827x1170 | 6.73 | 2.31 | AA |
| rotate_180 | 150 | 1240x1755 | 1240x1755 | 4.94 | 2.07 | AA |
| rotate_180 | 300 | 2480x3509 | 2480x3509 | 3.84 | 2.67 | AA |
| rotate_270 | 50 | 585x414 | 585x414 | 9.96 | 2.58 | AA |
| rotate_270 | 100 | 1170x827 | 1170x827 | 8.04 | 2.53 | AA |
| rotate_270 | 150 | 1755x1240 | 1755x1240 | 5.30 | 2.27 | AA |
| rotate_270 | 300 | 3509x2480 | 3509x2480 | 4.24 | 3.00 | AA |
| mediabox_offset | 50 | 414x585 | 414x585 | 3.82 | 1.30 | AA |
| mediabox_offset | 100 | 827x1170 | 827x1170 | 4.38 | 1.40 | AA |
| mediabox_offset | 150 | 1240x1755 | 1240x1755 | 4.27 | 1.72 | AA |
| mediabox_offset | 300 | 2480x3509 | 2480x3509 | 2.78 | 1.93 | ok |
| cropbox | 50 | 348x487 | 348x487 | 9.87 | 3.48 | GRENZE |
| cropbox | 100 | 695x973 | 695x973 | 7.81 | 2.42 | AA |
| cropbox | 150 | 1042x1459 | 1042x1459 | 5.90 | 2.33 | AA |
| cropbox | 300 | 2084x2917 | 2084x2917 | 4.03 | 2.75 | AA |
| cropbox_clip | 50 | 244x348 | 244x348 | 15.77 | 5.09 | AA |
| cropbox_clip | 100 | 487x695 | 487x695 | 13.50 | 3.79 | AA |
| cropbox_clip | 150 | 730x1042 | 730x1042 | 8.07 | 2.78 | AA |
| cropbox_clip | 300 | 1459x2084 | 1459x2084 | 7.32 | 5.01 | AA |
| cropbox_rot90 | 50 | 487x348 | 487x348 | 9.79 | 2.87 | AA |
| cropbox_rot90 | 100 | 973x695 | 973x695 | 9.35 | 2.38 | AA |
| cropbox_rot90 | 150 | 1459x1042 | 1459x1042 | 6.67 | 2.42 | AA |
| cropbox_rot90 | 300 | 2917x2084 | 2917x2084 | 4.65 | 3.17 | GRENZE |
| userunit_2 | 50 | 827x1170 | 827x1170 | 5.22 | 1.59 | AA |
| userunit_2 | 100 | 1653x2339 | 1653x2339 | 2.90 | 1.47 | ok |
| userunit_2 | 150 | 2480x3509 | 2480x3509 | 3.45 | 2.37 | AA |
| userunit_2 | 300 | 4959x7017 | 4959x7017 | 2.64 | 2.47 | ok |
| fractional_size | 50 | 414x585 | 414x585 | 5.16 | 1.86 | AA |
| fractional_size | 100 | 827x1170 | 827x1170 | 5.20 | 1.69 | AA |
| fractional_size | 150 | 1241x1754 | 1241x1754 | 3.26 | 1.22 | AA |
| fractional_size | 300 | 2481x3508 | 2481x3508 | 2.65 | 1.82 | ok |
| huge_mediabox | 150 | 8000x8000 | 8000x8000 | 0.01 | 0.00 | ok |
| encrypted_empty_pw | 50 | 414x585 | 414x585 | 5.24 | 1.74 | AA |
| encrypted_empty_pw | 100 | 827x1170 | 827x1170 | 5.22 | 1.59 | AA |
| encrypted_empty_pw | 150 | 1240x1755 | 1240x1755 | 4.89 | 1.92 | AA |
| encrypted_empty_pw | 300 | 2480x3509 | 2480x3509 | 3.45 | 2.37 | AA |
| broken_xref | 50 | 414x585 | 414x585 | 5.24 | 1.74 | AA |
| broken_xref | 100 | 827x1170 | 827x1170 | 5.22 | 1.59 | AA |
| broken_xref | 150 | 1240x1755 | 1240x1755 | 4.89 | 1.92 | AA |
| broken_xref | 300 | 2480x3509 | 2480x3509 | 3.45 | 2.37 | AA |

#### (b2) Graustufen (jpg/png-Methoden), 150 DPI

Orakel = fitz RGB->L (gleiche Luminanzformel wie pdfium-RGB->L). Spalte 'nativ' = fitz csGRAY (MuPDF hellt gesättigte Farben auf: Rot 129 statt 76) - nur Information.

| Fall | fitz | pdfium | MAD roh | MAD geglättet | MAD vs. fitz nativ-Gray | Urteil |
|---|---|---|---|---|---|---|
| text_a4 | 1240x1755 | 1240x1755 | 4.89 | 1.92 | 4.89 | AA |
| vector | 1240x1755 | 1240x1755 | 2.53 | 2.07 | 3.63 | ok |
| scan_color_jpeg | 1240x1755 | 1240x1755 | 0.78 | 0.72 | 1.68 | ok |
| stress_noise_jpeg | 1240x1755 | 1240x1755 | 2.70 | 2.39 | 6.42 | ok |
| scan_gray_jpeg | 1240x1755 | 1240x1755 | 0.78 | 0.72 | 0.78 | ok |
| image_cmyk_jpeg | 1240x1755 | 1240x1755 | 2.87 | 2.67 | 3.74 | ok |
| image_16bit_png | 834x834 | 834x834 | 0.60 | 0.60 | 0.60 | ok |
| transparency | 1240x1755 | 1240x1755 | 0.69 | 0.55 | 11.48 | ok |
| annot_forms | 1240x1755 | 1240x1755 | 4.99 | 2.06 | 5.50 | AA |
| rotate_90 | 1755x1240 | 1755x1240 | 5.03 | 2.05 | 5.75 | AA |
| rotate_180 | 1240x1755 | 1240x1755 | 4.77 | 1.93 | 5.55 | AA |
| rotate_270 | 1755x1240 | 1755x1240 | 5.12 | 2.13 | 5.91 | AA |
| mediabox_offset | 1240x1755 | 1240x1755 | 4.27 | 1.72 | 4.27 | AA |
| cropbox | 1042x1459 | 1042x1459 | 5.90 | 2.33 | 5.90 | AA |
| cropbox_clip | 730x1042 | 730x1042 | 8.07 | 2.78 | 8.07 | AA |
| cropbox_rot90 | 1459x1042 | 1459x1042 | 6.67 | 2.42 | 6.67 | AA |
| userunit_2 | 2480x3509 | 2480x3509 | 3.45 | 2.37 | 3.45 | AA |
| fractional_size | 1241x1754 | 1241x1754 | 3.26 | 1.22 | 3.26 | AA |
| encrypted_empty_pw | 1240x1755 | 1240x1755 | 4.89 | 1.92 | 4.89 | AA |
| broken_xref | 1240x1755 | 1240x1755 | 4.89 | 1.92 | 4.89 | AA |

#### (b3) Versatz und Annotationen/Formularfelder (150 DPI)

| Fall | bester Versatz (dy,dx) | Urteil |
|---|---|---|
| text_a4 | (0, 0) | ok |
| vector | (0, 2) | ok |
| scan_color_jpeg | (0, 0) | ok |
| stress_noise_jpeg | (0, 0) | ok |
| scan_gray_jpeg | (0, 0) | ok |
| image_cmyk_jpeg | (0, 0) | ok |
| image_16bit_png | (-1, -1) | ok |
| transparency | (0, 0) | ok |
| annot_forms | (0, 0) | ok |
| rotate_90 | (0, 0) | ok |
| rotate_180 | (0, 0) | ok |
| rotate_270 | (0, 0) | ok |
| mediabox_offset | (-1, 0) | ok |
| cropbox | (0, 0) | ok |
| cropbox_clip | (0, 0) | ok |
| cropbox_rot90 | (0, 0) | ok |
| userunit_2 | (0, 0) | ok |
| fractional_size | (0, 0) | ok |
| encrypted_empty_pw | (0, 0) | ok |
| broken_xref | (0, 0) | ok |

Annotationen/Widgets: Region-MAD (geglättet) fitz vs pdfium = 2.84; pdfium mit vs. ohne Annotationen/Formulare differiert um 2.77 (muss > 0.05 sein)

#### (c) JPEG-Größe der Kompressionsvarianten (150 DPI)

| Fall | Variante | fitz B | pdfium B | Abw. | Urteil |
|---|---|---|---|---|---|
| text_a4 | jpg (grau, q60) | 214035 | 203228 | -5.0 % | ok |
| text_a4 | jpg_color (q75) | 271536 | 258340 | -4.9 % | ok |
| vector | jpg (grau, q60) | 98425 | 98699 | +0.3 % | ok |
| vector | jpg_color (q75) | 129666 | 129449 | -0.2 % | ok |
| scan_color_jpeg | jpg (grau, q60) | 202663 | 202020 | -0.3 % | ok |
| scan_color_jpeg | jpg_color (q75) | 281212 | 279167 | -0.7 % | ok |
| stress_noise_jpeg | jpg (grau, q60) | 160920 | 154349 | -4.1 % | ok |
| stress_noise_jpeg | jpg_color (q75) | 291907 | 291370 | -0.2 % | ok |
| scan_gray_jpeg | jpg (grau, q60) | 199900 | 202285 | +1.2 % | ok |
| scan_gray_jpeg | jpg_color (q75) | 279246 | 277206 | -0.7 % | ok |
| image_cmyk_jpeg | jpg (grau, q60) | 133906 | 137101 | +2.4 % | ok |
| image_cmyk_jpeg | jpg_color (q75) | 255510 | 254967 | -0.2 % | ok |
| image_16bit_png | jpg (grau, q60) | 15233 | 16285 | +6.9 % | ok |
| image_16bit_png | jpg_color (q75) | 21970 | 22993 | +4.7 % | ok |
| transparency | jpg (grau, q60) | 40621 | 39843 | -1.9 % | ok |
| transparency | jpg_color (q75) | 55599 | 54947 | -1.2 % | ok |
| annot_forms | jpg (grau, q60) | 222416 | 211673 | -4.8 % | ok |
| annot_forms | jpg_color (q75) | 290564 | 275647 | -5.1 % | ok |
| rotate_90 | jpg (grau, q60) | 228582 | 214558 | -6.1 % | ok |
| rotate_90 | jpg_color (q75) | 299825 | 284308 | -5.2 % | ok |
| rotate_180 | jpg (grau, q60) | 228289 | 216140 | -5.3 % | ok |
| rotate_180 | jpg_color (q75) | 302051 | 287879 | -4.7 % | ok |
| rotate_270 | jpg (grau, q60) | 233190 | 217143 | -6.9 % | ok |
| rotate_270 | jpg_color (q75) | 306290 | 288117 | -5.9 % | ok |
| mediabox_offset | jpg (grau, q60) | 163440 | 157586 | -3.6 % | ok |
| mediabox_offset | jpg_color (q75) | 207892 | 200911 | -3.4 % | ok |
| cropbox | jpg (grau, q60) | 198547 | 184613 | -7.0 % | ok |
| cropbox | jpg_color (q75) | 251399 | 234321 | -6.8 % | ok |
| cropbox_clip | jpg (grau, q60) | 145705 | 139063 | -4.6 % | ok |
| cropbox_clip | jpg_color (q75) | 184074 | 175830 | -4.5 % | ok |
| cropbox_rot90 | jpg (grau, q60) | 194465 | 186207 | -4.2 % | ok |
| cropbox_rot90 | jpg_color (q75) | 244621 | 235084 | -3.9 % | ok |
| userunit_2 | jpg (grau, q60) | 562738 | 546284 | -2.9 % | ok |
| userunit_2 | jpg_color (q75) | 708789 | 689116 | -2.8 % | ok |
| fractional_size | jpg (grau, q60) | 208596 | 199135 | -4.5 % | ok |
| fractional_size | jpg_color (q75) | 264653 | 252857 | -4.5 % | ok |
| encrypted_empty_pw | jpg (grau, q60) | 214035 | 203228 | -5.0 % | ok |
| encrypted_empty_pw | jpg_color (q75) | 271536 | 258340 | -4.9 % | ok |
| broken_xref | jpg (grau, q60) | 214035 | 203228 | -5.0 % | ok |
| broken_xref | jpg_color (q75) | 271536 | 258340 | -4.9 % | ok |

#### (d) Geschwindigkeit je Seite (open+render+PIL+close je Seite, Best-of-11 interleaved, ms)

| Dokument | DPI | fitz | pdfium | pdfium/fitz-Tempo |
|---|---|---|---|---|
| Text+Bild (20 S.) | 100 | 10.9 | 10.2 | 1.07x |
| Text+Bild (20 S.) | 150 | 9.1 | 14.1 | 0.65x |
| Text+Bild (20 S.) | 300 | 49.7 | 40.8 | 1.22x |
| Scan farbig (1 S.) | 100 | 43.3 | 59.3 | 0.73x |
| Scan farbig (1 S.) | 150 | 64.9 | 81.2 | 0.80x |
| Scan farbig (1 S.) | 300 | 190.8 | 129.2 | 1.48x |
| Text dicht (1 S.) | 100 | 4.7 | 4.5 | 1.06x |
| Text dicht (1 S.) | 150 | 7.7 | 8.0 | 0.96x |
| Text dicht (1 S.) | 300 | 69.5 | 60.7 | 1.14x |

Median-Verhältnis 1.06x, schlechtester Fall 0.65x, 1 von 9 Fällen unter 0.7x (Ziel >= 0.7x; hart: Median >= 0.7x und kein Fall < 0.5x, Einzelfälle < 0.7x werden dokumentiert)

#### (e) Thread-Sicherheit mit globalem Lock

8 Threads x 200 Seiten (100 DPI) = 1600 Renderings in 23.9 s; Fehler/Abweichungen: 0
Vordergrund-Seite allein: 16.4 ms; bei 4 Hintergrund-Threads: Median 16.3 ms, p95 25.2 ms; Ziel <= 2x + 1 Seite = 49.3 ms

#### (f) Speicher (1000 Seiten, Dokument je Aufruf geschlossen)

RSS vor: 805 MB; nach 250/500/750/1000: 805 / 805 / 805 / 805 MB
Wachstum zwischen Seite 250 und 1000: 0.0 MB -> ok
