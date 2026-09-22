import pandas as pd


# ============================================================
# RÈGLES DE TRAITEMENT RETENUES POUR LE POC
# ============================================================

# Ces règles ont été identifiées à partir de l'analyse
# des traitements historiquement renseignés.
#
# Elles constituent le périmètre volontairement limité
# de la première version du prototype.

REGLES_TRAITEMENT = {
    "Ce PDS est déjà associé - Changer le libellé d'intervention":
        "Changement émetteur",

    "Fichier fabricant non reçu":
        "IT4US",

    "Aucune trame n'a été trouvée dans la plage horaire autorisée":
        "Vérification terrain à engager",
}


def appliquer_regles_traitement(df):
    """
    Applique les règles métier retenues dans le périmètre du PoC.

    Le champ 'Résultat' est fourni par SITR.

    Lorsque le type de rejet correspond à une règle identifiée,
    le prototype propose un traitement.

    Dans les autres situations, le cas est orienté vers
    un traitement humain.
    """

    resultat = df.copy()

    # --------------------------------------------------------
    # Vérification de la présence de la colonne Résultat
    # --------------------------------------------------------

    if "Résultat" not in resultat.columns:
        raise ValueError(
            "La colonne 'Résultat' est absente du fichier. "
            "Le prototype nécessite une extraction ACT Métier "
            "contenant le résultat fourni par SITR."
        )

    # --------------------------------------------------------
    # Nettoyage léger du résultat
    # --------------------------------------------------------

    resultat["_RESULTAT_NETTOYE"] = (
        resultat["Résultat"]
        .astype("string")
        .str.strip()
    )

    # --------------------------------------------------------
    # Proposition du traitement
    # --------------------------------------------------------

    resultat["Traitement proposé"] = (
        resultat["_RESULTAT_NETTOYE"]
        .map(REGLES_TRAITEMENT)
    )

    # --------------------------------------------------------
    # Mode de décision
    # --------------------------------------------------------

    resultat["Mode de décision"] = "Traitement humain"

    masque_regle = resultat["Traitement proposé"].notna()

    resultat.loc[
        masque_regle,
        "Mode de décision"
    ] = "Règle métier"

    # --------------------------------------------------------
    # Justification
    # --------------------------------------------------------

    resultat["Justification"] = (
        "Aucune règle suffisamment fiable définie "
        "dans le périmètre actuel du PoC."
    )

    resultat.loc[
        masque_regle,
        "Justification"
    ] = (
        "Traitement proposé à partir d'une règle métier "
        "identifiée par l'analyse des données historiques."
    )

    # --------------------------------------------------------
    # Suppression de la colonne technique
    # --------------------------------------------------------

    resultat = resultat.drop(
        columns=["_RESULTAT_NETTOYE"]
    )

    return resultat