# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
# Datei: tests/conftest.py
import shutil
from pathlib import Path

import pytest

OUTPUT_DIR = Path(__file__).parent / "data" / "output"


@pytest.fixture(autouse=True, scope="session")
def clean_output_dir():
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
