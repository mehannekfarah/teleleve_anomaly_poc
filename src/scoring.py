"""
scoring.py — Approche hybride de TR Assist : règles métier + Machine Learning + humain
Farah MEHANNEK — Mémoire Mastère IA, Développement et Big Data

Pour chaque rejet ACT Métier :
1. si le motif correspond à une règle métier   -> mode « Règle métier » ;
2. sinon, si le motif a déjà été rencontré dans l'historique d'apprentissage,
   la forêt aléatoire calcule une probabilité pour chaque traitement :
   si la plus élevée atteint le seuil           -> mode « Modèle » ;
3. sinon                                        -> mode « Traitement humain »
   (la suggestion du modèle reste affichée à titre indicatif).
Un motif jamais rencontré dans l'historique n'est jamais confié au modèle :
sans exemple, le modèle n'a rien appris sur ce motif.

Le modèle est entraîné au préalable avec : python src/modeling.py
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

try:                                    # import depuis le paquet src (app.py à la racine)
    from .business_rules import REGLES_TRAITEMENT
    from .modeling import construire_variables, matrice, FICHIER_MODELE, SEUIL_PAR_DEFAUT
except ImportError:                     # import direct (script lancé depuis src/)
    from business_rules import REGLES_TRAITEMENT
    from modeling import construire_variables, matrice, FICHIER_MODELE, SEUIL_PAR_DEFAUT


# Libellés affichés pour les classes du modèle (cohérents avec les règles métier)
LIBELLES = {
    "Vérification terrain (NC)": "Vérification terrain à engager",
    "Changement émetteur": "Changement émetteur",
    "IT4US": "IT4US",
    "Association": "Association",
    "Annulation": "Annulation",
    "Attente clôture intervention": "Attente clôture intervention",
    "Correction données compteur": "Correction données compteur",
    "Support (SOP)": "Support (SOP)",
}

MODE_REGLE = "Règle métier"
MODE_MODELE = "Modèle"
MODE_HUMAIN = "Traitement humain"


def charger_modele(chemin=FICHIER_MODELE):
    """Charge le modèle entraîné. Renvoie None si le fichier n'existe pas encore."""
    chemin = Path(chemin)
    if not chemin.exists():
        return None
    return joblib.load(chemin)


def appliquer_approche_hybride(df, parc=None, modele=None, seuil=SEUIL_PAR_DEFAUT):
    """
    Applique l'approche hybride à une extraction ACT Métier.

    df     : extraction ACT Métier (après chargement et nettoyage)
    parc   : parc ODYSSEE (DataFrame, voir modeling.lire_parc) ou None
    modele : paquet chargé avec charger_modele(), ou None (règles seules)
    seuil  : confiance minimale pour accepter une proposition du modèle (0 à 1)

    Colonnes ajoutées :
      Traitement proposé, Mode de décision, Confiance (%),
      Suggestion du modèle, Justification
    """
    if "Résultat" not in df.columns:
        raise ValueError(
            "La colonne 'Résultat' est absente du fichier. "
            "Le prototype nécessite une extraction ACT Métier contenant le résultat fourni par SITR."
        )

    res = df.copy()
    motif = res["Résultat"].astype(str).str.strip()

    # ---------------------------------------------------- 1. Règles métier
    traitement_regle = motif.map(REGLES_TRAITEMENT)
    masque_regle = traitement_regle.notna()

    res["Traitement proposé"] = traitement_regle
    res["Mode de décision"] = MODE_HUMAIN
    res["Confiance (%)"] = np.nan
    res["Suggestion du modèle"] = None
    res["Justification"] = "Aucune règle ni proposition suffisamment fiable : analyse par l'opérateur."

    res.loc[masque_regle, "Mode de décision"] = MODE_REGLE
    res.loc[masque_regle, "Confiance (%)"] = 100.0
    res.loc[masque_regle, "Justification"] = (
        "Traitement proposé à partir d'une règle métier identifiée par l'analyse des données historiques."
    )

    # ---------------------------------------------------- 2. Modèle de Machine Learning
    a_traiter = ~masque_regle
    if modele is not None:
        connus = set(modele.get("motifs_connus", []))
        inconnu = a_traiter & ~motif.isin(connus)
        res.loc[inconnu, "Justification"] = (
            "Motif de rejet jamais rencontré dans l'historique d'apprentissage : "
            "aucune proposition possible, analyse par l'opérateur."
        )
        a_traiter = a_traiter & motif.isin(connus)
    if modele is not None and a_traiter.any():
        avec_ody = parc is not None and len(parc) > 0
        cle = "act_ody" if avec_ody else "act"
        m = modele[cle]["modele"]
        colonnes = modele[cle]["colonnes"]

        variables = construire_variables(res.loc[a_traiter], parc if avec_ody else None)
        X = matrice(variables, avec_ody=avec_ody, colonnes=colonnes)
        proba = m.predict_proba(X.values)
        idx_max = proba.argmax(axis=1)
        confiance = proba.max(axis=1)
        classe = np.array(m.classes_)[idx_max]
        libelle = [LIBELLES.get(c, c) for c in classe]

        index = res.index[a_traiter]
        res.loc[index, "Confiance (%)"] = np.round(confiance * 100, 1)
        res.loc[index, "Suggestion du modèle"] = libelle

        source = "ACT Métier + parc ODYSSEE" if avec_ody else "ACT Métier seul (parc non chargé)"
        accepte = confiance >= seuil
        idx_ok, idx_ko = index[accepte], index[~accepte]

        res.loc[idx_ok, "Traitement proposé"] = np.array(libelle, dtype=object)[accepte]
        res.loc[idx_ok, "Mode de décision"] = MODE_MODELE
        res.loc[idx_ok, "Justification"] = [
            f"Proposition du modèle de Machine Learning ({source}) avec une confiance de {c:.0%}, "
            f"supérieure au seuil de {seuil:.0%}. À valider par l'opérateur."
            for c in confiance[accepte]
        ]
        res.loc[idx_ko, "Justification"] = [
            f"Confiance du modèle insuffisante ({c:.0%} < {seuil:.0%}) : analyse par l'opérateur. "
            f"Suggestion indicative : {l}."
            for c, l in zip(confiance[~accepte], np.array(libelle, dtype=object)[~accepte])
        ]

    return res


def synthese_decisions(res):
    """Petit tableau récapitulatif : nombre et part des rejets par mode de décision."""
    ordre = [MODE_REGLE, MODE_MODELE, MODE_HUMAIN]
    s = res["Mode de décision"].value_counts().reindex(ordre, fill_value=0)
    return pd.DataFrame({
        "Mode de décision": s.index,
        "Nombre de rejets": s.values,
        "Part (%)": np.round(s.values / max(len(res), 1) * 100, 1),
    })
