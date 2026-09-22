from pathlib import Path

from src.data_loader import load_data, validate_schema
from src.preprocessing import clean_data
from src.feature_engineering import create_features


class LocalFile:
    """
    Petit adaptateur permettant de tester notre fonction load_data
    avec un fichier présent sur l'ordinateur.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name
        self.file = open(self.path, "rb")

    def read(self, *args):
        return self.file.read(*args)

    def seek(self, *args):
        return self.file.seek(*args)

    def tell(self):
        return self.file.tell()

    def close(self):
        return self.file.close()


# =========================
# TEST DU FICHIER SEPTEMBRE
# =========================

fichier = LocalFile("data/raw/act_metier_septembre.csv")

df, erreur = load_data(fichier)

if erreur:
    print("ERREUR :", erreur)

else:
    # 1. Chargement
    print("Chargement réussi !")
    print("Nombre de lignes :", df.shape[0])
    print("Nombre de colonnes :", df.shape[1])

    # 2. Validation du schéma
    valide, message = validate_schema(df)

    print("Validation :", valide)
    print("Message :", message)

    # 3. Nettoyage + création des features
    if valide:
        df_clean = clean_data(df)
        df_features = create_features(df_clean)

        print("\n--- TEST DU PIPELINE ---")

        print("Lignes avant nettoyage :", len(df))
        print("Lignes après nettoyage :", len(df_clean))

        print("\nNouvelles variables :")

        print(
            df_features[
                [
                    "Date action terrain",
                    "Date reçu SITR",
                    "Date traitement",
                    "delai_action_reception",
                    "delai_reception_traitement"
                ]
            ].head(10)
        )

    # 4. Colonnes disponibles
    print("\nColonnes trouvées :")

    for colonne in df.columns:
        print("-", colonne)


fichier.close()