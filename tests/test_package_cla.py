"""The three separable packages carry the CLA verbatim (so it travels with them on extraction, see EXTRACTION.md).

Source of truth: the "Contributor License Agreement" section of the main repo's CONTRIBUTING.md. Each package has its own
CONTRIBUTING.md containing that section character for character, and its README points to it. Wording is a legal text -
it must never be paraphrased; this test fails on any drift.
"""
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ["datev-dokab", "belegtool-archives", "belegtool-compress"]
HEADING = "## Contributor License Agreement"


def cla_section(text: str) -> str:
    text = text.replace("\r\n", "\n")
    assert HEADING in text, "CLA heading missing"
    body = text.split(HEADING, 1)[1]
    end = body.find("\n## ")
    return (HEADING + (body if end < 0 else body[:end])).strip()


MAIN = cla_section((ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8"))


def test_main_cla_is_the_expected_text():
    # Guards the guard: if the main wording is edited on purpose, this and the three package copies must be updated together.
    assert "By contributing, you accept these terms." in MAIN
    assert "non-exclusive" in MAIN and "Tobias Heinrich" in MAIN
    assert len(hashlib.sha256(MAIN.encode("utf-8")).hexdigest()) == 64


@pytest.mark.parametrize("pkg", PACKAGES)
def test_package_contributing_has_identical_cla(pkg):
    f = ROOT / "packages" / pkg / "CONTRIBUTING.md"
    assert f.is_file(), f"{f} missing"
    mine = cla_section(f.read_text(encoding="utf-8"))
    assert hashlib.sha256(mine.encode("utf-8")).hexdigest() == hashlib.sha256(MAIN.encode("utf-8")).hexdigest()
    assert mine == MAIN


@pytest.mark.parametrize("pkg", PACKAGES)
def test_package_readme_points_to_its_own_contributing(pkg):
    readme = (ROOT / "packages" / pkg / "README.md").read_text(encoding="utf-8")
    assert "[`CONTRIBUTING.md`](CONTRIBUTING.md)" in readme


@pytest.mark.parametrize("pkg", PACKAGES)
def test_package_license_files_setting_untouched(pkg):
    # The task said: leave pyproject license-files as is (the CONTRIBUTING.md is deliberately not a licence file).
    py = (ROOT / "packages" / pkg / "pyproject.toml").read_text(encoding="utf-8")
    assert "CONTRIBUTING" not in py
