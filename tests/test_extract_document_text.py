"""Tests unitaires pour l'extraction de texte de documents (scripts/extract_document_text.py).

Le PDF est testé avec pypdf mocké (construire un vrai fichier PDF binaire n'apporterait
rien de plus ici : c'est le comportement de extract_pdf — jointure des pages, tolérance
aux pages illisibles — qui est sous test, pas pypdf lui-même). Le DOCX et le texte brut
sont testés avec de vrais fichiers, faciles à construire sans dépendance supplémentaire.
"""
import os
from typing import Any
import unittest.mock as mock

import pytest

from extract_document_text import extract_docx, extract_pdf, extract_text, extract_text_file


def test_extract_text_file_reads_utf8(tmp_path: Any) -> None:
    path = os.path.join(str(tmp_path), "cv.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Data Scientist — Développeur Python\nExpérience chez Acme")
    assert "Data Scientist" in extract_text_file(path)
    assert "Développeur Python" in extract_text_file(path)


def test_extract_docx_reads_paragraphs_and_tables(tmp_path: Any) -> None:
    docx = pytest.importorskip("docx")
    path = os.path.join(str(tmp_path), "cv.docx")
    doc = docx.Document()
    doc.add_paragraph("Jean Dupont — Data Analyst")
    doc.add_paragraph("Expérience : Data Analyst chez Acme (2023-2025)")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Python"
    table.rows[0].cells[1].text = "SQL"
    doc.save(path)

    text = extract_docx(path)
    assert "Jean Dupont" in text
    assert "Data Analyst chez Acme" in text
    assert "Python" in text and "SQL" in text


@mock.patch("pypdf.PdfReader")
def test_extract_pdf_joins_pages(mock_reader: mock.MagicMock) -> None:
    # pypdf est importé localement dans extract_pdf() : on patche pypdf.PdfReader
    # directement (même objet module que celui vu par l'import local à l'appel).
    page1 = mock.MagicMock()
    page1.extract_text.return_value = "Page 1 : profil"
    page2 = mock.MagicMock()
    page2.extract_text.return_value = "Page 2 : expériences"
    mock_reader.return_value.pages = [page1, page2]

    text = extract_pdf("fake.pdf")
    assert "Page 1 : profil" in text
    assert "Page 2 : expériences" in text


@mock.patch("pypdf.PdfReader")
def test_extract_pdf_tolerates_unreadable_page(mock_reader: mock.MagicMock) -> None:
    good_page = mock.MagicMock()
    good_page.extract_text.return_value = "Page lisible"
    bad_page = mock.MagicMock()
    bad_page.extract_text.side_effect = Exception("page corrompue")
    mock_reader.return_value.pages = [good_page, bad_page]

    text = extract_pdf("fake.pdf")
    assert "Page lisible" in text  # une page illisible ne fait pas échouer les autres


def test_extract_text_dispatches_by_extension(tmp_path: Any) -> None:
    path = os.path.join(str(tmp_path), "notes.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# CV\nExpérience pertinente")
    assert "Expérience pertinente" in extract_text(path)


def test_extract_text_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        extract_text("does-not-exist.pdf")


def test_extract_text_unsupported_extension_raises(tmp_path: Any) -> None:
    path = os.path.join(str(tmp_path), "cv.xyz")
    with open(path, "w", encoding="utf-8") as f:
        f.write("contenu")
    with pytest.raises(ValueError, match="non supportée"):
        extract_text(path)


def test_extract_text_empty_content_raises(tmp_path: Any) -> None:
    path = os.path.join(str(tmp_path), "vide.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("   \n  ")
    with pytest.raises(ValueError, match="Aucun texte extrait"):
        extract_text(path)
