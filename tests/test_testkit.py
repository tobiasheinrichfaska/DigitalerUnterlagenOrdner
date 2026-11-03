"""The human-tester kit (scripts/testkit + scripts/build_testkit.py): the Markdown subset,
the test-case model, the real manual_tests sources and the sample-file catalog.

The sample tests run each file through the app's own code, because a manual test is only
as good as its sample: a "compressible scan" the app cannot shrink, or a "too deep" archive
the importer happily opens, would send a tester looking for a bug that is not there.
"""

import json

import pytest

from formats.compress_pdf_bytes import compress_all_methods
from scripts import build_testkit
from scripts.testkit import cases, page
from scripts.testkit.markdown import inline, to_html
from scripts.testkit.samples import SAMPLES, TOO_DEEP_LEVELS
from universal_importer import extract_email_to_structure, extract_zip_to_structure
from universal_importer.archives import _ARCHIVE_MAX_DEPTH

CASE = """## MT-07: Zwei Dokumente zusammenführen

Kurze Einleitung.

**Ab Version:** 3.10.0

**Beispieldateien:** `a.pdf`, `b.zip`

**Voraussetzungen:** Beide Dateien sind importiert.

**Schritte (A – Auswahl):**
1. Ersten Eintrag anklicken.
2. Zweiten mit **Strg+Klick** markieren.

**Erwartet (A):**
- Beide sind markiert.

**Hinweis:** Nur im selben Ordner.
"""


def _area(body=CASE, filename="02_baum.md"):
    return cases.parse_area(filename, f"# 02 — Baum bearbeiten\n\nEinleitung des Bereichs.\n\n---\n\n{body}")


# --- Markdown subset -------------------------------------------------------------------

def test_inline_markup():
    assert inline("**fett** und *kursiv* und `code`") == "<strong>fett</strong> und <em>kursiv</em> und <code>code</code>"


def test_inline_bold_may_wrap_a_code_span():
    assert inline("**Datei `x.pdf`**") == "<strong>Datei <code>x.pdf</code></strong>"


def test_inline_keeps_markers_inside_code_and_escapes_html():
    assert inline("`**a*b**` <b>") == "<code>**a*b**</code> &lt;b&gt;"


def test_inline_file_name_patterns_are_not_emphasis():
    assert inline("Typ PDF (*.pdf) oder a_b_c") == "Typ PDF (*.pdf) oder a_b_c"


def test_inline_links():
    assert inline("[Text](https://example.com/a)") == '<a href="https://example.com/a">Text</a>'
    assert inline("siehe https://example.com/a.") == 'siehe <a href="https://example.com/a">https://example.com/a</a>.'


def test_ordered_list_with_nested_bullets_and_continuation():
    html = to_html("1. Eins\n   weiter\n2. Zwei:\n   - a\n   - b\n")
    assert html == "<ol><li>Eins weiter</li><li>Zwei:<ul><li>a</li><li>b</li></ul></li></ol>"


def test_ordered_list_keeps_its_start_number():
    assert to_html("5. Fünf\n6. Sechs") == '<ol start="5"><li>Fünf</li><li>Sechs</li></ol>'


def test_list_then_table_are_separate_blocks():
    html = to_html("1. Schritt\n\n| A | B |\n|---|---|\n| 1 | 2 |\n")
    assert html == ("<ol><li>Schritt</li></ol>\n"
                    "<table><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td>1</td><td>2</td></tr></tbody></table>")


def test_blockquote_and_fenced_code():
    assert to_html("> **Achtung:** Text") == "<blockquote><p><strong>Achtung:</strong> Text</p></blockquote>"
    assert to_html("```\nwinget <x>\n```") == "<pre><code>winget &lt;x&gt;</code></pre>"


# --- test-case model ---------------------------------------------------------------------

def test_parse_area_and_case():
    area = _area()
    assert (area.number, area.slug, area.title) == ("02", "baum", "Baum bearbeiten")
    assert area.intro == "Einleitung des Bereichs."
    (case,) = area.cases
    assert (case.id, case.title, case.since) == ("MT-07", "Zwei Dokumente zusammenführen", "3.10.0")
    assert case.samples == ("a.pdf", "b.zip")
    assert case.intro == "Kurze Einleitung."
    assert [(s.kind, s.qualifier) for s in case.sections] == [
        ("voraussetzungen", ""), ("schritte", "A – Auswahl"), ("erwartet", "A"), ("hinweis", "")]
    assert case.sections[1].body == "1. Ersten Eintrag anklicken.\n2. Zweiten mit **Strg+Klick** markieren."


def test_names_are_file_system_safe_and_area_prefixed():
    case = _area().cases[0]
    assert case.folder_name == "MT-07_Zwei-Dokumente-zusammenfuehren"
    assert case.pdf_name == "02_MT-07_Zwei-Dokumente-zusammenfuehren.pdf"


def test_folder_name_drops_a_parenthetical_from_the_title():
    case = _area(CASE.replace("Zwei Dokumente zusammenführen", "Bild importieren (JPG / PNG)")).cases[0]
    assert case.folder_name == "MT-07_Bild-importieren"


def test_slugify_cuts_at_a_word_boundary():
    assert cases.slugify("Größe – ändern/prüfen") == "Groesse-aendern-pruefen"
    assert cases.slugify("eins zwei drei vier", limit=12) == "eins-zwei"


def test_validate_accepts_a_complete_case():
    assert cases.validate([_area()], {"a.pdf", "b.zip"}) == []


@pytest.mark.parametrize("old, new, expected", [
    ("**Erwartet (A):**\n- Beide sind markiert.\n", "", "Abschnitt 'erwartet' fehlt"),
    ("`b.zip`", "`fehlt.zip`", "Beispieldatei 'fehlt.zip' ist nicht im Katalog"),
    ("3.10.0", "3.10", "'Ab Version' ist keine Version X.Y.Z"),
    ("Zwei Dokumente zusammenführen", "Zwei `Dokumente`", "Titel enthält Markdown-Zeichen"),
    ("- Beide sind markiert.", "", "Abschnitt 'erwartet' ist leer"),
])
def test_validate_reports(old, new, expected):
    problems = cases.validate([_area(CASE.replace(old, new))], {"a.pdf", "b.zip"})
    assert any(expected in problem for problem in problems), problems


def test_validate_reports_a_duplicate_id_within_an_area():
    problems = cases.validate([_area(CASE + "\n---\n\n" + CASE)], {"a.pdf", "b.zip"})
    assert any("doppelt" in problem for problem in problems)


def test_unused_samples():
    assert cases.unused_samples([_area()], {"a.pdf", "b.zip", "c.png"}) == ["c.png"]


# --- the real sources --------------------------------------------------------------------

@pytest.fixture(scope="module")
def areas():
    return cases.load_areas(build_testkit.MANUAL)


def test_real_sources_are_valid_and_use_every_sample(areas):
    assert cases.validate(areas, SAMPLES) == []
    assert cases.unused_samples(areas, SAMPLES) == []


def test_every_case_gets_its_own_pdf(areas):
    names = [case.pdf_name for area in areas for case in area.cases]
    assert len(names) == len(set(names))  # test ids repeat across areas — PDF names must not


def test_rendered_pages_have_no_leftover_markup(areas):
    for doc in build_testkit.documents(areas):
        body = doc.html.split("</style>", 1)[1]
        assert "**" not in body, doc.name
        assert "`" not in body, doc.name


def test_case_page_shows_samples_version_and_sections(areas):
    area = next(a for a in areas if a.number == "01")
    case = next(c for c in area.cases if c.id == "MT-06")
    html = page.case_page(area, case, SAMPLES, "9.9.9")
    assert "Zu_tief_verschachtelt.zip" in html and SAMPLES["Zu_tief_verschachtelt.zip"].description in html
    assert "erst ab Version 3.10.0 testbar" in html and "Beschreibt BelegTool 9.9.9" in html
    assert "Erwartetes Ergebnis" in html and "Testprotokoll" in html


def test_kit_on_disk_matches_the_sources(areas):
    """Editing a test without regenerating the kit leaves a tester with an outdated PDF."""
    if not build_testkit.MANIFEST.is_file():
        pytest.skip("Testpaket nicht erzeugt (python scripts/build_testkit.py)")
    docs = build_testkit.documents(areas)
    recorded = json.loads(build_testkit.MANIFEST.read_text(encoding="utf-8"))
    assert recorded == build_testkit.manifest(docs), "Testpaket veraltet: python scripts/build_testkit.py"
    for doc in docs:
        assert doc.pdf.is_file(), doc.pdf
    for area in areas:
        for case in area.cases:
            folder = build_testkit.case_folder(area, case) / build_testkit.SAMPLE_DIR
            on_disk = {p.name for p in folder.iterdir()} if folder.is_dir() else set()
            assert on_disk == set(case.samples), folder


# --- sample files behave in the app as the tests describe ------------------------------------

@pytest.fixture(scope="module")
def built():
    return {name: sample.build() for name, sample in SAMPLES.items()}


def test_samples_are_reproducible(built):
    for name, sample in SAMPLES.items():
        assert built[name], name
        assert sample.build() == built[name], f"{name} ändert sich von Lauf zu Lauf"


def test_text_pdf_offers_nothing_smaller(built):
    assert compress_all_methods(built["Rechnung_5_Seiten.pdf"]) == {}


def test_colour_scan_offers_smaller_variants(built):
    variants = compress_all_methods(built["Farbscan_Rechnung_3_Seiten.pdf"])
    assert {"jpg", "jpg_color"} <= set(variants)


def _names(structure):
    for entry in structure:
        yield entry["name"]
        yield from _names(entry.get("children", []))


def test_disguised_exe_is_refused_inside_a_mail(built):
    names = list(_names(extract_email_to_structure(built["Mail_mit_getarnter_EXE.eml"])))
    assert any("rechnung.pdf – nicht importierbar" in n and "Windows-Programm" in n for n in names)
    assert "echte_Rechnung.pdf" in names


def test_unsupported_attachment_shows_its_reason(built):
    names = list(_names(extract_email_to_structure(built["Mail_mit_Anhaengen.eml"])))
    assert "Messwerte.xyz – nicht importierbar (Nicht unterstützter Dateityp: .xyz)" in names


def test_archive_subfolders_and_same_named_files(built):
    (rechnungen, vertraege) = extract_zip_to_structure(built["Belege_mit_Unterordnern.zip"])
    assert [(f["name"], [c["name"] for c in f["children"]]) for f in rechnungen["children"]] == [
        ("2024", ["beleg.pdf", "kassenbon.jpg"]), ("2023", ["beleg.pdf"])]
    assert vertraege["name"] == "vertraege"


def test_nesting_stops_exactly_one_level_past_the_limit(built):
    deepest = TOO_DEEP_LEVELS
    names = list(_names(extract_zip_to_structure(built["Zu_tief_verschachtelt.zip"])))
    assert f"ebene_{deepest - 1}.zip" in names and f"beleg_ebene_{deepest - 1}.pdf" in names
    assert f"ebene_{deepest}.zip – nicht importierbar (zu tief verschachtelt)" in names
    assert "beleg_ganz_innen.pdf" not in names


def test_manual_nesting_case_names_the_real_limit():
    # MT-06 tells the tester the limit and the refused level; it must follow the constant.
    text = (build_testkit.MANUAL / "01_import.md").read_text(encoding="utf-8")
    assert f"auf **{_ARCHIVE_MAX_DEPTH} Ebenen** begrenzt" in text
    assert f"`ebene_{TOO_DEEP_LEVELS}.zip – nicht importierbar (zu tief verschachtelt)`" in text


def test_belegtool_samples_carry_their_status_and_tags(built, tmp_path):
    from core.bridge import load_belegtool

    def leaves(name):
        path = tmp_path / name
        path.write_bytes(built[name])
        return {n.name: n for n in load_belegtool(path).root.iter() if not n.is_folder}

    status = leaves("Beispielmappe_mit_Status.belegtool")
    assert (status["Telefon_2025-01.pdf"].status, status["Beleg_rot.pdf"].status,
            status["Beleg_ohne_Status.pdf"].status) == ("erfasst", "vorjahreswert", "")
    assert status["Sammelrechnung_Wartung.pdf"].pdf_length == 4
    tags = leaves("Beispielmappe_mit_Tags.belegtool")
    assert tags["Telefon_2025-01.pdf"].tags == ("Telefon", "Betriebsausgabe")
    many = leaves("Viele_kleine_Belege.belegtool")
    assert len(many) == 26
    # after the round trip the text receipts must still be "nothing smaller", the scans not
    assert compress_all_methods(many["Beleg_01.pdf"].original_data) == {}
    assert compress_all_methods(many["Scan_Kassenbon_A.pdf"].original_data)
