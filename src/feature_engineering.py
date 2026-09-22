import pandas as pd


def nettoyer_identifiant(valeur):
    """
    Normalise un identifiant pour faciliter les comparaisons.
    """
    if pd.isna(valeur):
        return None

    valeur = str(valeur).strip().upper()

    if valeur.endswith(".0"):
        valeur = valeur[:-2]

    return valeur


def extraire_pds_odyssee(pds):
    """
    Transforme le PDS ACT Métier en identifiant utilisable
    pour la recherche dans le parc ODYSSEE.

    Exemple :
    981131738876 -> 1131738876
    """
    pds = nettoyer_identifiant(pds)

    if not pds:
        return None

    if pds.startswith("98"):
        return pds[2:]

    return pds


def extraire_code_diametre(matricule):
    """
    Extrait le 5e caractère du matricule compteur.
    """
    matricule = nettoyer_identifiant(matricule)

    if not matricule or len(matricule) < 5:
        return None

    return matricule[4]


def deduire_diametre(matricule):
    """
    Déduit le diamètre à partir du 5e caractère du matricule
    selon la règle métier existante.
    """

    correspondance = {
        "A": 15,
        "B": 20,
        "D": 30,
        "E": 40,
        "F": 50,
        "G": 60,
        "H": 80,
        "I": 100,
        "J": 125,
        "K": 150,
        "L": 200,
        "M": 250,
        "N": 300,
        "O": 400,
        "P": 500,
        "U": 15,
        "V": 15,
        "X": 0,
    }

    code = extraire_code_diametre(matricule)

    return correspondance.get(code, 0)


def ajouter_variables_metier(df):
    """
    Ajoute les variables utiles à l'analyse des actes métier.
    """

    resultat = df.copy()

    if "PDS" in resultat.columns:
        resultat["PDS_ODYSSEE"] = resultat["PDS"].apply(
            extraire_pds_odyssee
        )

    if "Matricule compteur" in resultat.columns:
        resultat["COMPTEUR_ACT"] = resultat[
            "Matricule compteur"
        ].apply(nettoyer_identifiant)

        resultat["CODE_DIAMETRE"] = resultat[
            "Matricule compteur"
        ].apply(extraire_code_diametre)

        resultat["DIAMETRE_DEDUIT"] = resultat[
            "Matricule compteur"
        ].apply(deduire_diametre)

    return resultat