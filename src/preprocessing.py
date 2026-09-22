import pandas as pd


def clean_data(df):
    """
    Nettoie les données de l'extraction ACT Métier.

    - crée une copie des données originales ;
    - supprime les doublons stricts ;
    - convertit les colonnes de dates ;
    - gère les matricules émetteurs manquants.
    """

    df_clean = df.copy()

    # Suppression des doublons strictement identiques
    df_clean = df_clean.drop_duplicates()

    # Conversion des colonnes de dates
    date_cols = [
        "Date action terrain",
        "Date reçu SITR",
        "Date traitement"
    ]

    for col in date_cols:
        if col in df_clean.columns:
            df_clean[col] = pd.to_datetime(
                df_clean[col],
                errors="coerce",
                dayfirst=True
            )

    # Gestion des matricules émetteurs manquants
    if "Matricule émetteur" in df_clean.columns:
        df_clean["Matricule émetteur"] = (
            df_clean["Matricule émetteur"]
            .fillna("ABSENT")
        )

    return df_clean