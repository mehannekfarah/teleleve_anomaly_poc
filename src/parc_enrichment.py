import re
from io import BytesIO

import pandas as pd

from openpyxl.styles import (
    Alignment,
    Font,
    PatternFill,
)

from openpyxl.utils import get_column_letter


# ============================================================
# PARAMÈTRES
# ============================================================

TEXTE_COMPTEUR_INCOMPATIBLE = "compteur incompatible"

COLONNES_PARC_UTILES = [
    "ID_PDS",
    "NUMERO_SERIE",
    "DIAMETRE",
    "FABRICANT",
    "MODELE",
]


# ============================================================
# NETTOYAGE
# ============================================================

def nettoyer_identifiant(valeur):
    """
    Nettoie un identifiant provenant d'Excel ou d'un CSV.

    Exemple :
    123456.0 -> 123456
    """

    if pd.isna(valeur):
        return None

    valeur = str(valeur).strip()

    if valeur.endswith(".0"):
        valeur = valeur[:-2]

    if not valeur:
        return None

    return valeur


def normaliser_pds_act(valeur):
    """
    Normalise le PDS provenant des ACT Métier.

    Dans les données étudiées, le PDS ACT contient
    un préfixe 98 qui n'est pas présent dans ID_PDS
    du Parc compteur ODYSSEE.

    Exemple :
    981234567890 -> 1234567890
    """

    valeur = nettoyer_identifiant(valeur)

    if valeur is None:
        return None

    if valeur.startswith("98"):
        return valeur[2:]

    return valeur


# ============================================================
# MATRICULES COMPTEURS
# ============================================================

def extraire_matricules_act(valeur):
    """
    Extrait les différents matricules éventuellement présents
    dans le champ « Matricule compteur ».

    Certains champs ACT peuvent contenir plusieurs matricules.
    La comparaison doit donc porter sur chaque matricule
    individuellement et non sur la chaîne complète.
    """

    if pd.isna(valeur):
        return []

    texte = str(valeur).upper().strip()

    candidats = re.findall(
        r"[A-Z0-9]+",
        texte,
    )

    return [
        candidat
        for candidat in candidats
        if len(candidat) >= 5
    ]


def compteur_present_dans_act(
    matricule_act,
    numero_serie_parc,
):
    """
    Vérifie si le compteur enregistré dans le Parc compteur
    est présent parmi les matricules indiqués dans l'ACT Métier.
    """

    numero_parc = nettoyer_identifiant(
        numero_serie_parc
    )

    if numero_parc is None:
        return None

    numero_parc = numero_parc.upper()

    matricules_act = extraire_matricules_act(
        matricule_act
    )

    if not matricules_act:
        return None

    return numero_parc in matricules_act


# ============================================================
# DIAMÈTRE
# ============================================================

DIAMETRES_PAR_CODE = {
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


def calculer_diametre_act(matricule):
    """
    Reproduction de la règle déterministe observée
    dans la macro métier.

    Le cinquième caractère du premier matricule permet
    d'obtenir le diamètre attendu.
    """

    matricules = extraire_matricules_act(
        matricule
    )

    if not matricules:
        return None

    premier_matricule = matricules[0]

    if len(premier_matricule) < 5:
        return None

    code = premier_matricule[4]

    return DIAMETRES_PAR_CODE.get(code)


# ============================================================
# CHARGEMENT DU PARC COMPTEUR
# ============================================================

def charger_parc_compteur(source):
    """
    Charge le Parc compteur depuis un CSV ou un fichier Excel.

    La lecture est volontairement limitée aux colonnes utiles
    à l'analyse afin de réduire la mémoire nécessaire,
    notamment pour les extractions volumineuses.

    source peut être :
    - un chemin local ;
    - un fichier envoyé depuis Streamlit.
    """

    try:

        nom = getattr(
            source,
            "name",
            str(source),
        ).lower()

        # ----------------------------------------------------
        # EXCEL
        # ----------------------------------------------------

        if nom.endswith(".xlsx") or nom.endswith(".xls"):

            parc = pd.read_excel(
                source,
                dtype=str,
            )

        # ----------------------------------------------------
        # CSV
        # ----------------------------------------------------

        else:

            # On tente d'abord le séparateur utilisé
            # habituellement dans les exports français.
            try:

                if hasattr(source, "seek"):
                    source.seek(0)

                parc = pd.read_csv(
                    source,
                    sep=";",
                    dtype=str,
                    low_memory=False,
                )

                # Si tout le fichier a été lu comme
                # une seule colonne, le séparateur n'est
                # probablement pas le point-virgule.
                if len(parc.columns) == 1:

                    if hasattr(source, "seek"):
                        source.seek(0)

                    parc = pd.read_csv(
                        source,
                        sep=",",
                        dtype=str,
                        low_memory=False,
                    )

            except Exception:

                # Dernière tentative avec la virgule.
                if hasattr(source, "seek"):
                    source.seek(0)

                parc = pd.read_csv(
                    source,
                    sep=",",
                    dtype=str,
                    low_memory=False,
                )

    except Exception as erreur:

        return None, (
            "Impossible de charger le parc compteur : "
            f"{erreur}"
        )


    # ========================================================
    # NETTOYAGE DES NOMS DE COLONNES
    # ========================================================

    parc.columns = (
        parc.columns
        .astype(str)
        .str.strip()
    )


    # ========================================================
    # VÉRIFICATION DES COLONNES
    # ========================================================

    colonnes_manquantes = [
        colonne
        for colonne in COLONNES_PARC_UTILES
        if colonne not in parc.columns
    ]

    if colonnes_manquantes:

        return None, (
            "Le fichier Parc compteur ne contient pas "
            "les colonnes nécessaires : "
            + ", ".join(colonnes_manquantes)
        )


    # ========================================================
    # CONSERVATION DES COLONNES UTILES
    # ========================================================

    parc = parc[
        COLONNES_PARC_UTILES
    ].copy()


    # ========================================================
    # NORMALISATION DU PDS PARC
    # ========================================================

    parc["PDS_PARC"] = (
        parc["ID_PDS"]
        .apply(nettoyer_identifiant)
    )

    return parc, None


# ============================================================
# ANALYSE COMPTEUR INCOMPATIBLE
# ============================================================

def analyser_compteurs_incompatibles(
    df_act,
    parc,
):
    """
    Analyse spécifiquement les rejets
    « Compteur incompatible ».

    L'analyse :
    1. sélectionne les rejets concernés ;
    2. normalise le PDS ;
    3. recherche le PDS dans le Parc compteur ;
    4. compare le compteur ACT au compteur ODYSSEE ;
    5. estime le diamètre attendu ;
    6. compare ce diamètre au Parc compteur ;
    7. produit un diagnostic explicable.

    Aucun traitement automatique n'est appliqué.
    Les résultats constituent une aide à l'analyse humaine.
    """

    # --------------------------------------------------------
    # Vérification de la présence de Résultat
    # --------------------------------------------------------

    if "Résultat" not in df_act.columns:
        return pd.DataFrame()


    # --------------------------------------------------------
    # Sélection des compteurs incompatibles
    # --------------------------------------------------------

    cas = df_act[
        df_act["Résultat"]
        .astype(str)
        .str.contains(
            TEXTE_COMPTEUR_INCOMPATIBLE,
            case=False,
            na=False,
        )
    ].copy()

    if cas.empty:
        return cas


    # --------------------------------------------------------
    # Normalisation PDS ACT
    # --------------------------------------------------------

    cas["PDS normalisé"] = (
        cas["PDS"]
        .apply(normaliser_pds_act)
    )


    # --------------------------------------------------------
    # Réduction du Parc compteur
    # --------------------------------------------------------

    parc_reduit = parc[
        [
            "PDS_PARC",
            "NUMERO_SERIE",
            "DIAMETRE",
            "FABRICANT",
            "MODELE",
        ]
    ].copy()


    # --------------------------------------------------------
    # Rapprochement ACT / ODYSSEE
    # --------------------------------------------------------

    resultat = cas.merge(
        parc_reduit,
        how="left",
        left_on="PDS normalisé",
        right_on="PDS_PARC",
    )


    # ========================================================
    # PDS
    # ========================================================

    resultat["PDS retrouvé"] = (
        resultat["NUMERO_SERIE"].notna()
    )


    # ========================================================
    # COMPARAISON DU COMPTEUR
    # ========================================================

    resultat["Compteur cohérent"] = (
        resultat.apply(
            lambda ligne:
                compteur_present_dans_act(
                    ligne.get(
                        "Matricule compteur"
                    ),
                    ligne.get(
                        "NUMERO_SERIE"
                    ),
                ),
            axis=1,
        )
    )


    # ========================================================
    # DIAMÈTRE
    # ========================================================

    resultat["Diamètre estimé ACT"] = (
        resultat["Matricule compteur"]
        .apply(calculer_diametre_act)
    )

    resultat["Diamètre parc"] = pd.to_numeric(
        resultat["DIAMETRE"],
        errors="coerce",
    )

    resultat["Diamètre cohérent"] = pd.NA

    masque_diametre = (
        resultat["Diamètre estimé ACT"].notna()
        & resultat["Diamètre parc"].notna()
    )

    resultat.loc[
        masque_diametre,
        "Diamètre cohérent",
    ] = (
        resultat.loc[
            masque_diametre,
            "Diamètre estimé ACT",
        ].astype(float)
        ==
        resultat.loc[
            masque_diametre,
            "Diamètre parc",
        ].astype(float)
    )


    # ========================================================
    # DIAGNOSTIC
    # ========================================================

    def creer_diagnostic(ligne):

        # PDS absent du Parc compteur
        if not bool(
            ligne["PDS retrouvé"]
        ):
            return (
                "PDS non retrouvé dans le parc compteur"
            )

        compteur_coherent = (
            ligne["Compteur cohérent"]
        )

        diametre_coherent = (
            ligne["Diamètre cohérent"]
        )


        # ----------------------------------------------------
        # Compteur identique
        # ----------------------------------------------------

        if compteur_coherent is True:

            if diametre_coherent is False:

                return (
                    "Compteur retrouvé - "
                    "diamètre à vérifier"
                )

            return (
                "Compteur cohérent avec le parc"
            )


        # ----------------------------------------------------
        # Compteur différent
        # ----------------------------------------------------

        if compteur_coherent is False:

            return (
                "Écart entre le compteur ACT Métier "
                "et le compteur du parc"
            )


        # ----------------------------------------------------
        # Comparaison impossible
        # ----------------------------------------------------

        return (
            "Comparaison du compteur impossible"
        )


    resultat["Diagnostic parc"] = (
        resultat.apply(
            creer_diagnostic,
            axis=1,
        )
    )


    # ========================================================
    # ORIENTATION
    # ========================================================

    resultat["Orientation"] = (
        "Analyse humaine"
    )

    return resultat


# ============================================================
# EXPORT DE L'ANALYSE
# ============================================================

def exporter_analyse_compteurs(analyse_compteurs):
    """
    Génère un classeur Excel dynamique pour l'analyse
    des rejets « Compteur incompatible ».

    Le fichier contient :
    - une feuille Synthèse ;
    - une feuille Tous les cas ;
    - une feuille par diagnostic réellement rencontré.

    Les feuilles sont créées automatiquement selon
    le contenu du fichier analysé.
    """

    sortie = BytesIO()

    # ========================================================
    # COLONNES À EXPORTER
    # ========================================================

    colonnes_detail = [
        "PDS",
        "PDS normalisé",
        "Matricule compteur",
        "NUMERO_SERIE",
        "Diamètre estimé ACT",
        "Diamètre parc",
        "FABRICANT",
        "MODELE",
        "PDS retrouvé",
        "Compteur cohérent",
        "Diamètre cohérent",
        "Diagnostic parc",
        "Orientation",
    ]

    colonnes_detail = [
        colonne
        for colonne in colonnes_detail
        if colonne in analyse_compteurs.columns
    ]

    detail = analyse_compteurs[
        colonnes_detail
    ].copy()

    # ========================================================
    # NOMS DES COLONNES POUR L'UTILISATEUR
    # ========================================================

    detail = detail.rename(
        columns={
            "NUMERO_SERIE": "Compteur parc ODYSSEE",
            "FABRICANT": "Fabricant parc",
            "MODELE": "Modèle parc",
        }
    )

    # ========================================================
    # SYNTHÈSE DYNAMIQUE
    # ========================================================

    diagnostics_nettoyes = (
        analyse_compteurs["Diagnostic parc"]
        .fillna("Diagnostic non renseigné")
    )

    synthese = (
        diagnostics_nettoyes
        .value_counts(dropna=False)
        .rename_axis("Diagnostic")
        .reset_index(name="Nombre de cas")
    )

    total = len(analyse_compteurs)

    if total > 0:
        synthese["Part des cas (%)"] = (
            synthese["Nombre de cas"]
            / total
            * 100
        ).round(1)
    else:
        synthese["Part des cas (%)"] = 0.0

    # ========================================================
    # NOM DES FEUILLES
    # ========================================================

    def creer_nom_feuille(diagnostic):
        """
        Donne un nom court et compréhensible aux diagnostics
        connus et crée automatiquement un nom pour les autres.
        """

        diagnostic = str(diagnostic)

        noms_connus = {
            (
                "Écart entre le compteur ACT Métier "
                "et le compteur du parc"
            ): "Écarts compteur",

            "Compteur cohérent avec le parc":
                "Compteurs cohérents",

            "PDS non retrouvé dans le parc compteur":
                "PDS non retrouvés",

            "Compteur retrouvé - diamètre à vérifier":
                "Diamètres à vérifier",

            "Comparaison du compteur impossible":
                "À vérifier",

            "Diagnostic non renseigné":
                "Sans diagnostic",
        }

        if diagnostic in noms_connus:
            return noms_connus[diagnostic]

        # -----------------------------------------------
        # Nouveau diagnostic non prévu dans le code
        # -----------------------------------------------

        nom = diagnostic

        # Caractères interdits dans les noms de feuilles Excel
        for caractere in [
            "\\",
            "/",
            "*",
            "?",
            ":",
            "[",
            "]",
        ]:
            nom = nom.replace(
                caractere,
                " ",
            )

        # Supprime les espaces multiples
        nom = " ".join(
            nom.split()
        )

        # Excel autorise maximum 31 caractères
        nom = nom[:31].strip()

        if not nom:
            nom = "Diagnostic"

        return nom

    # ========================================================
    # CRÉATION DU FICHIER EXCEL
    # ========================================================

    with pd.ExcelWriter(
        sortie,
        engine="openpyxl",
    ) as writer:

        # ====================================================
        # FEUILLE 1 : SYNTHÈSE
        # ====================================================

        synthese.to_excel(
            writer,
            sheet_name="Synthèse",
            index=False,
        )

        # ====================================================
        # FEUILLE 2 : TOUS LES CAS
        # ====================================================

        detail.to_excel(
            writer,
            sheet_name="Tous les cas",
            index=False,
        )

        # ====================================================
        # FEUILLES CRÉÉES AUTOMATIQUEMENT
        # SELON LES DIAGNOSTICS DU FICHIER
        # ====================================================

        diagnostics_presents = (
            diagnostics_nettoyes
            .drop_duplicates()
            .tolist()
        )

        noms_utilises = {
            "Synthèse",
            "Tous les cas",
        }

        for diagnostic in diagnostics_presents:

            # -----------------------------------------------
            # Sélection des lignes correspondant au diagnostic
            # -----------------------------------------------

            masque = (
                diagnostics_nettoyes
                == diagnostic
            )

            lignes_diagnostic = (
                detail.loc[
                    masque
                ]
                .copy()
            )

            if lignes_diagnostic.empty:
                continue

            # -----------------------------------------------
            # Création du nom de feuille
            # -----------------------------------------------

            nom_feuille = creer_nom_feuille(
                diagnostic
            )

            nom_base = nom_feuille
            numero = 2

            # -----------------------------------------------
            # Protection contre les noms en double
            # -----------------------------------------------

            while nom_feuille in noms_utilises:

                suffixe = f" {numero}"

                longueur_max = (
                    31
                    - len(suffixe)
                )

                nom_feuille = (
                    nom_base[:longueur_max]
                    + suffixe
                )

                numero += 1

            noms_utilises.add(
                nom_feuille
            )

            # -----------------------------------------------
            # Création de la feuille
            # -----------------------------------------------

            lignes_diagnostic.to_excel(
                writer,
                sheet_name=nom_feuille,
                index=False,
            )

        # ====================================================
        # MISE EN FORME DE TOUTES LES FEUILLES
        # ====================================================

        for nom_feuille in writer.book.sheetnames:

            ws = writer.book[
                nom_feuille
            ]

            # -----------------------------------------------
            # Figer la première ligne
            # -----------------------------------------------

            ws.freeze_panes = "A2"

            # -----------------------------------------------
            # Activer les filtres Excel
            # -----------------------------------------------

            ws.auto_filter.ref = (
                ws.dimensions
            )

            # -----------------------------------------------
            # Hauteur de l'en-tête
            # -----------------------------------------------

            ws.row_dimensions[1].height = 32

            # -----------------------------------------------
            # STYLE DE L'EN-TÊTE
            # -----------------------------------------------

            for cellule in ws[1]:

                cellule.font = Font(
                    bold=True,
                    color="FFFFFF",
                )

                cellule.fill = PatternFill(
                    fill_type="solid",
                    fgColor="087DB5",
                )

                cellule.alignment = Alignment(
                    horizontal="center",
                    vertical="center",
                    wrap_text=True,
                )

            # -----------------------------------------------
            # LARGEUR AUTOMATIQUE DES COLONNES
            # -----------------------------------------------

            for colonne in ws.columns:

                lettre = get_column_letter(
                    colonne[0].column
                )

                largeur = 12

                for cellule in colonne:

                    valeur = (
                        ""
                        if cellule.value is None
                        else str(cellule.value)
                    )

                    largeur = max(
                        largeur,
                        min(
                            len(valeur) + 2,
                            45,
                        ),
                    )

                    cellule.alignment = Alignment(
                        vertical="top",
                        wrap_text=True,
                    )

                ws.column_dimensions[
                    lettre
                ].width = largeur

            # -----------------------------------------------
            # COULEUR ALTERNÉE POUR LES LIGNES
            # -----------------------------------------------

            if ws.max_row > 1:

                remplissage_alterne = PatternFill(
                    fill_type="solid",
                    fgColor="F2F9FC",
                )

                for numero_ligne in range(
                    2,
                    ws.max_row + 1,
                ):

                    if numero_ligne % 2 == 0:

                        for cellule in ws[
                            numero_ligne
                        ]:

                            cellule.fill = (
                                remplissage_alterne
                            )

        # ====================================================
        # MISE EN FORME PARTICULIÈRE DE LA SYNTHÈSE
        # ====================================================

        ws_synthese = writer.book[
            "Synthèse"
        ]

        ws_synthese.column_dimensions[
            "A"
        ].width = 65

        ws_synthese.column_dimensions[
            "B"
        ].width = 18

        ws_synthese.column_dimensions[
            "C"
        ].width = 20

    # ========================================================
    # RETOUR DU FICHIER
    # ========================================================

    sortie.seek(0)

    return sortie