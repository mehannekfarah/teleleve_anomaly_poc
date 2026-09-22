import pandas as pd


REQUIRED_COLUMNS = [
    "PDS",
    "Matricule compteur",
    "Scénario",
    "Date action terrain",
    "Date reçu SITR",
]


def load_data(uploaded_file):
    """
    Charge une extraction ACT Métier au format Excel ou CSV.
    """

    try:
        file_name = uploaded_file.name.lower()

        if file_name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)

        elif file_name.endswith(".csv"):
            try:
                df = pd.read_csv(
                    uploaded_file,
                    sep=";",
                    encoding="utf-8-sig"
                )

            except UnicodeDecodeError:
                uploaded_file.seek(0)

                df = pd.read_csv(
                    uploaded_file,
                    sep=";",
                    encoding="latin-1"
                )

        else:
            return None, (
                "Format non supporté. "
                "Utilisez un fichier XLSX ou CSV."
            )

        return df, None

    except Exception as e:
        return None, f"Erreur de lecture du fichier : {e}"


def validate_schema(df):
    """
    Vérifie la présence des colonnes minimales nécessaires
    au traitement d'une extraction ACT Métier.
    """

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        return (
            False,
            "Colonnes manquantes : "
            + ", ".join(missing_columns)
        )

    return True, "Schéma valide."