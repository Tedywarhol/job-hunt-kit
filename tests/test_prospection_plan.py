"""Tests des règles pures de la prospection spontanée (scripts/prospection_plan.py).

Entreprises et personnes fictives uniquement : le dépôt est public.
"""
from typing import Any, Dict, Optional

import pytest

from prospection_plan import (
    JOURS_ENVOI,
    LINKEDIN_PAR_JOUR_MAX,
    choisir_sonde,
    construire_elements,
    plan_linkedin,
    plan_mails,
    repartition,
)

AUJOURDHUI = "2026-10-15"


def _personne(role: str, confiance: str, statut: str = "brouillon", canal: str = "mail",
              adresse: Optional[str] = None, date_envoi: str = "") -> Dict[str, Any]:
    return {
        "role": role, "confiance": confiance, "statut": statut, "canal": canal,
        "adresse": adresse or f"{role}@acme-aero.example", "date_envoi": date_envoi,
    }


def _entreprise(slug: str, confiance: str, ville: str = "Lyon", secteur: str = "ia", **extra: Any) -> Dict[str, Any]:
    personnes = [_personne(role, confiance, adresse=f"{role}@{slug}.example") for role in ("directeur", "manager", "chef_projet")]
    return {"slug": slug, "ville": ville, "secteur": secteur, "personnes": personnes, **extra}


def test_repartition_compte_par_zone_et_secteur() -> None:
    entreprises = [_entreprise("a", "sûre", "Lyon", "ia"), _entreprise("b", "sûre", "Lyon", "utilisatrice"),
                   _entreprise("c", "sûre", "Brest", "ia")]
    rep = repartition(entreprises)
    assert rep["zones"]["Lyon"] == (2, 12)
    assert rep["zones"]["Brest"] == (1, 7)
    assert rep["zones"]["Bidart"] == (0, 3)
    assert rep["secteurs"] == {"ia": (2, 50), "utilisatrice": (1, 50)}


def test_la_sonde_est_la_personne_la_moins_exposee() -> None:
    personnes = [_personne("directeur", "devinée"), _personne("chef_projet", "devinée"), _personne("manager", "devinée")]
    assert choisir_sonde(personnes)["role"] == "chef_projet"


def test_pas_de_sonde_quand_toutes_les_adresses_sont_sures() -> None:
    assert choisir_sonde([_personne("manager", "sûre"), _personne("directeur", "citée")]) is None


def test_une_seule_sonde_par_entreprise_a_adresses_devinees() -> None:
    elements = construire_elements([_entreprise("x", "devinée")], AUJOURDHUI)
    assert sorted(e["type"] for e in elements) == ["compagnon", "compagnon", "sonde"]


def test_adresses_sures_partent_directement() -> None:
    elements = construire_elements([_entreprise("x", "sûre")], AUJOURDHUI)
    assert {e["type"] for e in elements} == {"direct"}


def test_seuls_les_brouillons_par_mail_sont_planifies() -> None:
    entreprise = _entreprise("x", "sûre")
    entreprise["personnes"][0]["statut"] = "envoye"
    entreprise["personnes"][1]["canal"] = "linkedin"
    assert len(construire_elements([entreprise], AUJOURDHUI)) == 1


def test_un_compagnon_part_le_lendemain_de_sa_sonde() -> None:
    # Capacité large : seule la règle des 24 h peut retarder les compagnons.
    planning, restants = plan_mails(construire_elements([_entreprise("x", "devinée")], AUJOURDHUI), capacite=10)
    assert [e["type"] for e in planning[0]] == ["sonde"]
    assert sorted(e["type"] for e in planning[1]) == ["compagnon", "compagnon"]
    assert restants == []


def test_les_sondes_passent_avant_les_envois_directs() -> None:
    entreprises = [_entreprise(f"d{i}", "sûre") for i in range(10)] + [_entreprise("s", "devinée")]
    planning, _ = plan_mails(construire_elements(entreprises, AUJOURDHUI))
    assert "sonde" in [e["type"] for e in planning[0]]


def test_la_capacite_quotidienne_est_respectee_et_aucun_mail_ne_se_perd() -> None:
    entreprises = [_entreprise(f"s{i}", "devinée") for i in range(20)] + [_entreprise(f"d{i}", "sûre") for i in range(20)]
    elements = construire_elements(entreprises, AUJOURDHUI)
    planning, restants = plan_mails(elements)
    capacite = -(-len(elements) // JOURS_ENVOI)
    assert all(len(jour) <= capacite for jour in planning)
    assert sum(len(jour) for jour in planning) + len(restants) == len(elements) == 120


def test_sonde_partie_hier_les_compagnons_partent_aujourdhui() -> None:
    entreprise = _entreprise("x", "devinée")
    entreprise["personnes"][2].update(statut="envoye", date_envoi="2026-10-14")
    planning, _ = plan_mails(construire_elements([entreprise], AUJOURDHUI), capacite=10)
    assert len(planning[0]) == 2


def test_sonde_partie_aujourdhui_les_compagnons_attendent_demain() -> None:
    entreprise = _entreprise("x", "devinée")
    entreprise["personnes"][2].update(statut="envoye", date_envoi=AUJOURDHUI)
    planning, _ = plan_mails(construire_elements([entreprise], AUJOURDHUI), capacite=10)
    assert planning[0] == [] and len(planning[1]) == 2


def test_linkedin_reparti_a_parts_egales() -> None:
    planning = plan_linkedin([{"n": i} for i in range(14)])
    assert [len(j) for j in planning] == [2] * 7


def test_linkedin_refuse_un_depassement_du_plafond_quotidien() -> None:
    with pytest.raises(ValueError):
        plan_linkedin([{"n": i} for i in range(LINKEDIN_PAR_JOUR_MAX * JOURS_ENVOI + 1)])


def test_plan_vide() -> None:
    planning, restants = plan_mails([])
    assert restants == [] and all(jour == [] for jour in planning)
    assert len(planning) == JOURS_ENVOI


def test_une_sonde_qui_a_repondu_libere_ses_collegues_des_aujourd_hui() -> None:
    entreprise = _entreprise("x", "devinée")
    entreprise["personnes"][2].update(statut="repondu", date_envoi="2026-10-14")
    planning, _ = plan_mails(construire_elements([entreprise], AUJOURDHUI), capacite=10)
    assert len(planning[0]) == 2
