"""Tests du client LinkedIn en lecture seule (scripts/linkedin_cli.py), sans lancer de serveur."""
import pytest

pytest.importorskip("mcp", reason="le paquet mcp n'est pas installé dans cet interpréteur")

import linkedin_cli  # noqa: E402


def test_refuse_les_outils_d_ecriture() -> None:
    for outil in ("connect_with_person", "edit_profile_intro", "edit_profile_about", "add_experience"):
        assert linkedin_cli.outil_autorise(outil) is False


def test_accepte_les_outils_de_lecture() -> None:
    for outil in ("search_people", "get_person_profile", "search_jobs", "get_job_details"):
        assert linkedin_cli.outil_autorise(outil) is True


def test_appeler_ne_touche_pas_au_serveur_pour_un_outil_refuse() -> None:
    import asyncio

    resultat = asyncio.run(linkedin_cli.appeler(None, "connect_with_person", {"linkedin_username": "x"}))  # type: ignore[arg-type]
    assert resultat["ok"] is False
    assert "lecture seule" in resultat["erreur"]


def test_commande_serveur_respecte_la_variable_d_environnement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKEDIN_MCP_COMMAND", "uvx mcp-server-linkedin@latest --verbose")
    assert linkedin_cli.commande_serveur() == ("uvx", ["mcp-server-linkedin@latest", "--verbose"])
