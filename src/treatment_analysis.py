import pandas as pd


def analyser_traitements_historiques(df):
    """
    Analyse les traitements réellement renseignés dans
    l'historique pour chaque résultat SITR.
    """

    donnees = df.copy()

    donnees = donnees[
        donnees["Traitement"].notna()
    ].copy()

    donnees["Résultat"] = (
        donnees["Résultat"]
        .astype(str)
        .str.strip()
    )

    donnees["Traitement"] = (
        donnees["Traitement"]
        .astype(str)
        .str.strip()
    )

    analyse = (
        donnees
        .groupby(["Résultat", "Traitement"])
        .size()
        .reset_index(name="Nombre de cas")
    )

    total_par_rejet = (
        analyse
        .groupby("Résultat")["Nombre de cas"]
        .transform("sum")
    )

    analyse["Pourcentage"] = (
        analyse["Nombre de cas"]
        / total_par_rejet
        * 100
    ).round(1)

    return analyse.sort_values(
        ["Résultat", "Nombre de cas"],
        ascending=[True, False]
    )


def mesurer_regularite_traitement(df):
    """
    Pour chaque rejet, mesure la proportion représentée
    par son traitement historique le plus fréquent.

    Cette fonction sert à identifier les candidats à
    l'automatisation par règle.
    """

    analyse = analyser_traitements_historiques(df)

    if analyse.empty:
        return analyse

    principal = (
        analyse
        .sort_values(
            ["Résultat", "Nombre de cas"],
            ascending=[True, False]
        )
        .groupby("Résultat")
        .first()
        .reset_index()
    )

    principal = principal.rename(
        columns={
            "Traitement": "Traitement principal",
            "Nombre de cas": "Nombre",
            "Pourcentage": "Taux traitement principal (%)"
        }
    )

    return principal.sort_values(
        "Taux traitement principal (%)",
        ascending=False
    )