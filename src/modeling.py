"""
modeling.py — Entraînement du modèle de Machine Learning de TR Assist
Farah MEHANNEK — Mémoire Mastère IA, Développement et Big Data

Ce module :
1. normalise les traitements saisis par les opérateurs (texte libre -> 8 classes) ;
2. construit les variables utilisées par le modèle (ACT Métier + enrichissement ODYSSEE) ;
3. entraîne deux forêts aléatoires :
     - « act »     : variables ACT Métier seules (utilisé si aucun parc n'est chargé) ;
     - « act_ody » : variables ACT Métier + ODYSSEE (utilisé si le parc est chargé) ;
4. enregistre les modèles dans models/modele_hybride.joblib.

Les variables et les paramètres sont identiques à ceux de l'expérimentation
(scripts/experimentation.py, chapitre 6 du mémoire).

Utilisation (depuis la racine du projet) :
    python src/modeling.py
"""
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier


# ============================================================
# PARAMÈTRES
# ============================================================

RNG = 42
SEUIL_PAR_DEFAUT = 0.60

RACINE = Path(__file__).resolve().parents[1]
FICHIER_HISTORIQUE = RACINE / "data" / "processed" / "ACT_Metier_historique_pseudonymise.xlsx"
FICHIER_PARC = RACINE / "data" / "processed" / "Parc_compteur_pseudonymise.csv"
FICHIER_MODELE = RACINE / "models" / "modele_hybride.joblib"

COLONNES_PARC_MODELE = [
    "ID_PDS", "NUMERO_SERIE", "MATRICULE_EQUIPEMENT", "FABRICANT", "DIAMETRE",
    "ANNEE_FABRICATION", "SOLUTION_COMPACTE", "MODE_DE_RELEVE",
]

CODES_DIAMETRE = {
    "A": 15, "B": 20, "D": 30, "E": 40, "F": 50, "G": 60, "H": 80, "I": 100,
    "J": 125, "K": 150, "L": 200, "M": 250, "N": 300, "O": 400, "P": 500,
    "U": 15, "V": 15, "X": 0,
}

CAT_ACT = ["Résultat", "Scénario", "Prémonté", "Processus", "Source", "code_diam"]
NUM_ACT = ["delai_jours", "index_meca", "index_elec", "emetteur_renseigne", "logs_present", "diam_deduit"]
CAT_ODY = ["ody_fabricant"]
NUM_ODY = ["ody_pds_trouve", "ody_compteur_identique", "ody_emetteur_identique", "ody_diam",
           "ody_diam_coherent", "ody_telereleve", "ody_compact", "ody_annee"]


# ============================================================
# NORMALISATION DES TRAITEMENTS (VÉRITÉ TERRAIN)
# ============================================================

def normaliser_traitement(valeur):
    """Regroupe les libellés saisis en texte libre dans les 8 classes du mémoire."""
    if pd.isna(valeur):
        return None
    s = str(valeur).strip().lower()
    if s.startswith("voir nc"):
        return "Vérification terrain (NC)"
    if "chgt émet" in s or "chgt emet" in s:
        return "Changement émetteur"
    if s == "association":
        return "Association"
    if "annul" in s:
        return "Annulation"
    if "it4us" in s:
        return "IT4US"
    if "attente" in s or "attene" in s or s == "at":
        return "Attente clôture intervention"
    if "sop" in s:
        return "Support (SOP)"
    if "correction" in s or "maj" in s or "chgt cptr" in s:
        return "Correction données compteur"
    return "Autre"


# ============================================================
# OUTILS
# ============================================================

def _nid(valeur):
    """Normalise un identifiant (majuscules, sans espaces ni « .0 » ajouté par Excel)."""
    if pd.isna(valeur):
        return None
    v = str(valeur).strip().upper()
    if v in ("", "ABSENT", "NAN", "NONE"):
        return None
    return v[:-2] if v.endswith(".0") else v


def lire_parc(source):
    """
    Charge le parc ODYSSEE avec les colonnes nécessaires au modèle.
    source : chemin local ou fichier envoyé depuis Streamlit (CSV ou Excel).
    """
    nom = getattr(source, "name", str(source)).lower()
    if hasattr(source, "seek"):
        source.seek(0)
    if nom.endswith((".xlsx", ".xls")):
        parc = pd.read_excel(source, dtype=str)
    else:
        parc = pd.read_csv(source, sep=";", encoding="utf-8-sig", dtype=str, low_memory=False,
                           usecols=lambda c: c in COLONNES_PARC_MODELE)
    for col in COLONNES_PARC_MODELE:
        if col not in parc.columns:
            parc[col] = np.nan
    if hasattr(source, "seek"):
        source.seek(0)
    return parc[COLONNES_PARC_MODELE]


# ============================================================
# CONSTRUCTION DES VARIABLES
# ============================================================

def construire_variables(df_act, parc=None):
    """
    Construit, pour chaque rejet, les variables utilisées par le modèle.
    Ne modifie pas le DataFrame d'entrée. Seules des informations disponibles
    au moment du rejet sont utilisées.
    """
    d = pd.DataFrame(index=df_act.index)

    for col in ["Résultat", "Scénario", "Prémonté", "Processus", "Source"]:
        d[col] = df_act[col].astype(str).str.strip() if col in df_act.columns else "INCONNU"

    pds = df_act["PDS"].apply(_nid) if "PDS" in df_act.columns else pd.Series(None, index=df_act.index)
    pds_ody = pds.apply(lambda p: p[2:] if isinstance(p, str) and p.startswith("98") else p)
    cpt = df_act["Matricule compteur"].apply(_nid) if "Matricule compteur" in df_act.columns else pd.Series(None, index=df_act.index)
    emt = df_act["Matricule émetteur"].apply(_nid) if "Matricule émetteur" in df_act.columns else pd.Series(None, index=df_act.index)

    d["code_diam"] = cpt.apply(lambda m: m[4] if isinstance(m, str) and len(m) >= 5 else "?")
    d["diam_deduit"] = d["code_diam"].map(CODES_DIAMETRE).fillna(0)

    if "Date action terrain" in df_act.columns and "Date reçu SITR" in df_act.columns:
        dt_terrain = pd.to_datetime(df_act["Date action terrain"], errors="coerce", dayfirst=True)
        dt_sitr = pd.to_datetime(df_act["Date reçu SITR"], errors="coerce", dayfirst=True)
        d["delai_jours"] = (dt_sitr - dt_terrain).dt.days.clip(lower=0).fillna(-1)
    else:
        d["delai_jours"] = -1

    d["index_meca"] = df_act["Index mécanique"].notna().astype(int) if "Index mécanique" in df_act.columns else 0
    d["index_elec"] = df_act["Index électronique"].notna().astype(int) if "Index électronique" in df_act.columns else 0
    d["emetteur_renseigne"] = emt.notna().astype(int)
    d["logs_present"] = df_act["Logs"].notna().astype(int) if "Logs" in df_act.columns else 0

    # ---------------- Enrichissement ODYSSEE
    if parc is not None and len(parc) > 0:
        p = parc.copy()
        for col in COLONNES_PARC_MODELE:
            if col not in p.columns:
                p[col] = np.nan
        p["ID_PDS"] = p["ID_PDS"].apply(_nid)
        p["NUMERO_SERIE"] = p["NUMERO_SERIE"].apply(_nid)
        p["MATRICULE_EQUIPEMENT"] = p["MATRICULE_EQUIPEMENT"].apply(_nid)
        p = p.dropna(subset=["ID_PDS"]).drop_duplicates("ID_PDS").set_index("ID_PDS")

        trouve = pds_ody.isin(p.index)
        ody = p.reindex(pds_ody.values)
        ody.index = df_act.index

        d["ody_pds_trouve"] = trouve.astype(int)
        d["ody_compteur_identique"] = (cpt == ody["NUMERO_SERIE"]).astype(int)
        d["ody_emetteur_identique"] = (emt == ody["MATRICULE_EQUIPEMENT"]).astype(int)
        d["ody_diam"] = pd.to_numeric(ody["DIAMETRE"], errors="coerce").fillna(-1)
        d["ody_diam_coherent"] = (d["ody_diam"] == d["diam_deduit"]).astype(int)
        d["ody_telereleve"] = ody["MODE_DE_RELEVE"].fillna("").astype(str).str.contains("Télé").astype(int)
        d["ody_compact"] = (ody["SOLUTION_COMPACTE"] == "Oui").astype(int)
        d["ody_annee"] = pd.to_numeric(ody["ANNEE_FABRICATION"], errors="coerce").fillna(-1)
        d["ody_fabricant"] = ody["FABRICANT"].fillna("NON_TROUVE").astype(str).str.split(" - ").str[0]

    return d


def matrice(variables, avec_ody, colonnes=None):
    """
    Transforme les variables en matrice numérique.
    Si « colonnes » est fourni (modèle déjà entraîné), la matrice est alignée
    sur ces colonnes : une catégorie inconnue est simplement ignorée.
    """
    cat = CAT_ACT + (CAT_ODY if avec_ody else [])
    num = NUM_ACT + (NUM_ODY if avec_ody else [])
    X = pd.get_dummies(variables[cat].astype(str), dtype=int)
    X = pd.concat([X, variables[num]], axis=1)
    if colonnes is not None:
        X = X.reindex(columns=colonnes, fill_value=0)
    return X


# ============================================================
# ENTRAÎNEMENT
# ============================================================

def _foret():
    return RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=RNG, n_jobs=-1)


def entrainer(fichier_historique=FICHIER_HISTORIQUE, fichier_parc=FICHIER_PARC, fichier_modele=FICHIER_MODELE):
    """Entraîne les deux forêts aléatoires sur l'historique et les enregistre."""
    print("Chargement de l'historique et du parc...", flush=True)
    hist = pd.read_excel(fichier_historique)
    parc = lire_parc(fichier_parc)

    hist["Classe"] = hist["Traitement"].apply(normaliser_traitement)
    lab = hist[hist["Classe"].notna() & (hist["Classe"] != "Autre")].reset_index(drop=True)
    y = lab["Classe"].to_numpy(dtype=object)

    variables = construire_variables(lab, parc)
    X_act = matrice(variables, avec_ody=False)
    X_ody = matrice(variables, avec_ody=True)

    print(f"Entraînement sur {len(y)} rejets et {len(set(y))} classes de traitement...", flush=True)
    modele_act = _foret().fit(X_act.values, y)
    modele_ody = _foret().fit(X_ody.values, y)

    paquet = {
        "act": {"modele": modele_act, "colonnes": list(X_act.columns)},
        "act_ody": {"modele": modele_ody, "colonnes": list(X_ody.columns)},
        "classes": sorted(set(y)),
        "motifs_connus": sorted(lab["Résultat"].astype(str).str.strip().unique().tolist()),
        "seuil_par_defaut": SEUIL_PAR_DEFAUT,
        "n_exemples": int(len(y)),
        "repartition": pd.Series(y).value_counts().to_dict(),
        "date_entrainement": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "algorithme": "Forêt aléatoire (300 arbres, classes pondérées)",
    }
    Path(fichier_modele).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(paquet, fichier_modele)

    print(f"\n{len(paquet['motifs_connus'])} motifs de rejet connus du modèle.")
    print("Répartition des classes apprises :")
    for classe, n in paquet["repartition"].items():
        print(f"  {classe:<32} {n}")
    print(f"\nTerminé. Modèle enregistré dans : {fichier_modele}")
    return paquet


if __name__ == "__main__":
    entrainer()
