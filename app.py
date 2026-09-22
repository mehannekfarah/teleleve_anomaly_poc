import pandas as pd
import streamlit as st
import altair as alt

from src.data_loader import load_data, validate_schema
from src.business_rules import appliquer_regles_traitement
from src.export import dataframe_to_excel, creer_synthese
from src.parc_enrichment import (
    charger_parc_compteur,
    analyser_compteurs_incompatibles,
    exporter_analyse_compteurs,
)


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="TR Assist | Télérelève",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# CONSTANTES
# ============================================================

TRADUCTION_SCENARIOS = {
    "Association": "Association",
    "AssociationCancelation": "Annulation d'association",
    "MeterChange": "Changement de compteur",
    "MeterModuleChange": "Changement compteur / émetteur",
    "MeterModuleRemoval": "Retrait de l'émetteur",
    "ReparamIndex": "Reparamétrage de l'index",
}

ANOMALIES_DISPONIBLES = [
    "Sélectionner une anomalie",
    "Compteur incompatible",
    "Compteur différent du patrimoine",
    "PDS absent du patrimoine",
    "PDS non associé",
    "Émetteur déjà associé",
    "Poids d'impulsion incohérent",
]


# ============================================================
# FONCTIONS D'AFFICHAGE
# ============================================================

def traduire_scenario(valeur):
    if pd.isna(valeur):
        return "—"

    return TRADUCTION_SCENARIOS.get(
        str(valeur),
        str(valeur),
    )


def preparer_affichage(dataframe):
    affichage = dataframe.copy()

    if "Scénario" in affichage.columns:
        affichage["Scénario"] = (
            affichage["Scénario"]
            .apply(traduire_scenario)
        )

    return affichage.fillna("—")


# ============================================================
# STYLE
# ============================================================

st.markdown(
    """
<style>

:root {
    --navy: #071F4A;
    --blue: #087DB5;
    --cyan: #18A9D5;
    --turquoise: #20B9C2;
    --green: #78D900;
    --text: #17324D;
    --muted: #6C8193;
    --border: #DCE7ED;
}

/* PAGE */

.stApp {
    background:
        radial-gradient(
            circle at 7% 3%,
            rgba(24,169,213,.08),
            transparent 24%
        ),
        linear-gradient(
            180deg,
            #F8FCFD 0px,
            #FFFFFF 520px
        );
}

.block-container {
    max-width: 1480px;
    padding-top: 1.35rem;
    padding-bottom: 2.5rem;
}

html,
body,
[class*="css"] {
    font-family:
        Inter,
        "Segoe UI",
        Arial,
        sans-serif;
    color: var(--text);
}

h1, h2, h3 {
    color: var(--navy);
}


/* HEADER */

.app-header {
    position: relative;
    overflow: hidden;

    background:
        linear-gradient(
            110deg,
            #FFFFFF 0%,
            #F5FBFD 68%,
            #EBF8FC 100%
        );

    border: 1px solid #D8E8EF;
    border-radius: 20px;
    padding: 25px 30px;

    box-shadow:
        0 8px 28px
        rgba(7,31,74,.07);
}

.app-header::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;

    width: 5px;

    background:
        linear-gradient(
            180deg,
            var(--green),
            var(--cyan),
            var(--blue)
        );
}

.app-name {
    font-size: 2.05rem;
    font-weight: 780;
    color: var(--navy);
    line-height: 1.1;
}

.app-subtitle {
    color: #315A78;
    font-size: 1.03rem;
    font-weight: 550;
    margin-top: 8px;
}

.app-context {
    color: #71879A;
    font-size: .88rem;
    margin-top: 9px;
}


/* INFO */

.info-box {
    padding: 21px 25px;
    border-radius: 16px;

    background:
        linear-gradient(
            110deg,
            rgba(8,125,181,.11),
            rgba(24,169,213,.08),
            rgba(120,217,0,.07)
        );

    border: 1px solid #C7E5EF;
    border-left: 5px solid var(--cyan);

    color: #31536E;
    line-height: 1.65;

    margin: 22px 0 27px 0;

    box-shadow:
        0 5px 18px
        rgba(7,31,74,.055);
}

.info-box b {
    color: var(--navy);
}


/* WORKFLOW */

.workflow {
    display: flex;
    align-items: center;
    justify-content: center;

    gap: 10px;
    flex-wrap: wrap;

    margin: 13px 0 36px;
}

.workflow-step {
    padding: 10px 17px;
    border-radius: 24px;

    color: white;
    font-size: .84rem;
    font-weight: 700;

    box-shadow:
        0 4px 12px
        rgba(7,31,74,.10);
}

.step-1 {
    background: linear-gradient(135deg, #071F4A, #087DB5);
}

.step-2 {
    background: linear-gradient(135deg, #087DB5, #139CC8);
}

.step-3 {
    background: linear-gradient(135deg, #139CC8, #20B9C2);
}

.step-4 {
    background: linear-gradient(135deg, #20B9C2, #54C985);
}

.step-5 {
    background: linear-gradient(135deg, #54C985, #78D900);
}

.workflow-arrow {
    color: #11A9D1;
    font-size: 1.18rem;
    font-weight: 800;
}


/* SECTIONS */

.section-label {
    display: inline-block;

    color: #0879AE;

    background:
        linear-gradient(
            100deg,
            #E8F7FB,
            #F0FBF6
        );

    border: 1px solid #D4EEF5;
    border-radius: 6px;

    padding: 5px 9px;

    font-size: .72rem;
    font-weight: 800;

    text-transform: uppercase;
    letter-spacing: .09em;

    margin-bottom: 8px;
}

.section-title {
    color: var(--navy);
    font-size: 1.5rem;
    font-weight: 740;
    margin-bottom: 17px;
}


/* UPLOAD */

[data-testid="stFileUploaderDropzone"] {
    background:
        linear-gradient(
            100deg,
            #FBFDFE,
            #F3FAFC
        );

    border: 1.5px dashed #8FC8DD;
    border-radius: 15px;

    padding: 21px;
}


/* KPI */

[data-testid="stMetric"] {
    position: relative;
    overflow: hidden;

    background:
        linear-gradient(
            145deg,
            #FFFFFF,
            #F7FCFD
        );

    border: 1px solid #DCE7ED;
    border-radius: 15px;

    padding: 18px 19px;
    min-height: 125px;

    box-shadow:
        0 4px 14px
        rgba(7,31,74,.045);
}

[data-testid="stMetric"]::before {
    content: "";
    position: absolute;

    top: 0;
    left: 0;

    width: 100%;
    height: 4px;

    background:
        linear-gradient(
            90deg,
            var(--blue),
            var(--cyan),
            var(--green)
        );
}

[data-testid="stMetricValue"] {
    color: var(--navy);
    font-weight: 730;
}


/* GRAPHIQUES */

[data-testid="stVegaLiteChart"] {
    background:
        linear-gradient(
            145deg,
            rgba(240,250,252,.60),
            rgba(255,255,255,.95)
        );

    border: 1px solid #E0EBF0;
    border-radius: 16px;

    padding: 8px;

    box-shadow:
        0 4px 15px
        rgba(7,31,74,.04);
}


/* EXPANDERS */

[data-testid="stExpander"] {
    background: #FFFFFF;

    border: 1px solid #DCE6EC;
    border-radius: 13px;

    overflow: hidden;
    margin-bottom: 11px;

    box-shadow:
        0 2px 9px
        rgba(7,31,74,.025);
}


/* TABLEAUX */

[data-testid="stDataFrame"] {
    border: 1px solid #DFE7EC;
    border-radius: 12px;
    overflow: hidden;
}


/* ANALYSE APPROFONDIE */

.advanced-zone {
    margin-top: 25px;
    padding: 25px 27px;

    border-radius: 20px;

    background:
        linear-gradient(
            125deg,
            rgba(7,31,74,.035),
            rgba(24,169,213,.07),
            rgba(120,217,0,.055)
        );

    border: 1px solid #CDE5ED;

    box-shadow:
        0 8px 25px
        rgba(7,31,74,.055);
}

.advanced-title {
    color: #071F4A;

    font-size: 1.25rem;
    font-weight: 750;

    margin-bottom: 8px;
}

.advanced-description {
    color: #526E82;
    line-height: 1.65;
}


/* SÉLECTEUR D'ANOMALIE */

.anomaly-selector-header {
    display: flex;
    align-items: center;
    gap: 17px;

    margin-top: 22px;
    margin-bottom: 14px;

    padding: 20px 24px;

    background:
        linear-gradient(
            105deg,
            rgba(8,125,181,.15),
            rgba(24,169,213,.11),
            rgba(120,217,0,.09)
        );

    border: 1px solid #B6DFEA;
    border-left: 6px solid #18A9D5;

    border-radius: 17px;

    box-shadow:
        0 8px 24px
        rgba(7,31,74,.08);
}

.anomaly-selector-icon {
    font-size: 2rem;
}

.anomaly-selector-title {
    color: #071F4A;
    font-size: 1.20rem;
    font-weight: 780;
}

.anomaly-selector-text {
    color: #526E82;
    font-size: .92rem;
    margin-top: 4px;
}


/* SELECTBOX MIS EN AVANT */

div[data-baseweb="select"] > div {
    min-height: 68px !important;

    border-radius: 16px !important;
    border: 2px solid #18A9D5 !important;

    background:
        linear-gradient(
            100deg,
            #FFFFFF,
            #F0FAFD
        ) !important;

    box-shadow:
        0 7px 20px
        rgba(8,125,181,.14) !important;

    font-size: 1.08rem !important;
}

div[data-baseweb="select"] > div:hover {
    border-color: #087DB5 !important;

    box-shadow:
        0 8px 23px
        rgba(8,125,181,.20) !important;
}


/* CAS D'ÉTUDE */

.case-study-box {
    margin: 18px 0 23px 0;
    padding: 25px 28px;

    border-radius: 18px;

    background:
        linear-gradient(
            115deg,
            rgba(7,31,74,.045),
            rgba(24,169,213,.09),
            rgba(120,217,0,.07)
        );

    border: 1px solid #C8E6ED;

    box-shadow:
        0 7px 22px
        rgba(7,31,74,.06);
}

.case-study-title {
    color: #071F4A;

    font-size: 1.18rem;
    font-weight: 780;

    margin-bottom: 15px;
}

.case-study-number {
    color: #087DB5;

    font-size: 2.5rem;
    font-weight: 800;

    line-height: 1;
}

.case-study-caption {
    color: #526E82;

    font-size: .88rem;

    margin-top: 6px;
    margin-bottom: 18px;
}

.case-study-description {
    color: #31536E;
    line-height: 1.7;
}


/* EXPORT */

.export-box {
    background:
        linear-gradient(
            105deg,
            rgba(8,125,181,.08),
            rgba(24,169,213,.05),
            rgba(120,217,0,.06)
        );

    border: 1px solid #D4E9F1;
    border-radius: 14px;

    padding: 18px 21px;

    color: #3C5C73;
}

.stDownloadButton > button {
    background:
        linear-gradient(
            100deg,
            #087DB5,
            #18A9D5
        );

    color: #FFFFFF;

    border: none;
    border-radius: 10px;

    min-height: 47px;

    font-weight: 680;

    box-shadow:
        0 5px 13px
        rgba(8,125,181,.18);
}

.stDownloadButton > button:hover {
    color: white;
    transform: translateY(-1px);
}


/* FOOTER */

.footer {
    margin-top: 50px;
    padding: 25px 15px;

    border-top: 1px solid #DDE7EC;

    text-align: center;

    color: #75899A;

    font-size: .81rem;
    line-height: 1.75;
}

.footer strong {
    color: #31536E;
}

</style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# EN-TÊTE
# ============================================================

col_logo, col_titre, col_suez = st.columns(
    [1.15, 5.5, 1.05],
    vertical_alignment="center",
)

with col_logo:
    st.image(
        "assets/logo_PoC.png",
        width=135,
    )

with col_titre:
    st.markdown(
        """
<div class="app-header">

<div class="app-name">
TR Assist
</div>

<div class="app-subtitle">
Aide au traitement des rejets ACT Métier
</div>

<div class="app-context">
Télérelève des compteurs d'eau ·
Prototype d'aide à la décision
</div>

</div>
        """,
        unsafe_allow_html=True,
    )

with col_suez:
    st.image(
        "assets/logo_SUEZ.png",
        width=105,
    )


# ============================================================
# PRÉSENTATION
# ============================================================

st.markdown(
    """
<div class="info-box">

<b>Principe du prototype.</b><br>

TR Assist exploite le <b>Résultat fourni par SITR</b>
afin de proposer un traitement lorsqu'une règle suffisamment
régulière a été identifiée dans l'historique étudié.

Les situations non couvertes restent orientées vers une
<b>analyse humaine</b>.

</div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# WORKFLOW
# ============================================================

st.markdown(
    """
<div class="workflow">

<span class="workflow-step step-1">
1 · Import ACT Métier
</span>

<span class="workflow-arrow">→</span>

<span class="workflow-step step-2">
2 · Analyse
</span>

<span class="workflow-arrow">→</span>

<span class="workflow-step step-3">
3 · Proposition
</span>

<span class="workflow-arrow">→</span>

<span class="workflow-step step-4">
4 · Validation humaine si nécessaire
</span>

<span class="workflow-arrow">→</span>

<span class="workflow-step step-5">
5 · Export Excel
</span>

</div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# IMPORT ACT MÉTIER
# ============================================================

st.markdown(
    """
<div class="section-label">
Étape 1
</div>

<div class="section-title">
Importer une extraction ACT Métier
</div>
    """,
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader(
    "Fichier ACT Métier",
    type=["xlsx", "csv"],
    help=(
        "Le fichier doit notamment contenir "
        "la colonne « Résultat » fournie par SITR."
    ),
    label_visibility="collapsed",
    key="upload_act_metier",
)


# ============================================================
# AUCUN FICHIER
# ============================================================

if uploaded_file is None:

    st.info(
        "Sélectionnez une extraction ACT Métier au format "
        "Excel ou CSV pour lancer l'analyse."
    )


# ============================================================
# ANALYSE PRINCIPALE
# ============================================================

else:

    df, erreur = load_data(uploaded_file)

    if erreur:
        st.error(erreur)
        st.stop()

    valide, message = validate_schema(df)

    if not valide:
        st.error(message)
        st.stop()

    if "Résultat" not in df.columns:
        st.error(
            "La colonne « Résultat » est absente. "
            "Le prototype nécessite le résultat fourni par SITR."
        )
        st.stop()

    st.success(
        (
            f"Fichier chargé avec succès · "
            f"{len(df):,} lignes détectées."
        ).replace(",", " ")
    )

    df_results = appliquer_regles_traitement(df)


    # ========================================================
    # KPI
    # ========================================================

    total_rejets = len(df_results)

    total_regles = int(
        (
            df_results["Mode de décision"]
            == "Règle métier"
        ).sum()
    )

    total_humain = int(
        (
            df_results["Mode de décision"]
            == "Traitement humain"
        ).sum()
    )

    taux_couverture = (
        total_regles / total_rejets * 100
        if total_rejets > 0
        else 0
    )

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        """
<div class="section-label">
Vue d'ensemble
</div>

<div class="section-title">
Résultats de l'analyse
</div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(
        4,
        gap="medium",
    )

    col1.metric(
        "Rejets analysés",
        f"{total_rejets:,}".replace(",", " "),
    )

    col2.metric(
        "Traitements proposés",
        f"{total_regles:,}".replace(",", " "),
    )

    col3.metric(
        "À analyser humainement",
        f"{total_humain:,}".replace(",", " "),
    )

    col4.metric(
        "Couverture par les règles",
        f"{taux_couverture:.1f} %",
    )

    st.caption(
        "La couverture correspond à la proportion de rejets "
        "pour lesquels le prototype dispose actuellement "
        "d'une règle de traitement. "
        "Elle ne constitue pas un taux de réussite."
    )

    cas_regles = df_results[
        df_results["Mode de décision"]
        == "Règle métier"
    ].copy()

    cas_humains = df_results[
        df_results["Mode de décision"]
        == "Traitement humain"
    ].copy()


    # ========================================================
    # VISUALISATION GÉNÉRALE
    # ========================================================

    st.markdown("<br>", unsafe_allow_html=True)

    gauche, droite = st.columns(
        [1.05, 1],
        gap="large",
    )

    with gauche:

        st.markdown(
            """
<div class="section-label">
Décision
</div>

<div class="section-title">
Répartition des cas
</div>
            """,
            unsafe_allow_html=True,
        )

        repartition_decisions = pd.DataFrame(
            {
                "Mode de décision": [
                    "Règle métier",
                    "Analyse humaine",
                ],
                "Nombre de cas": [
                    total_regles,
                    total_humain,
                ],
            }
        )

        donut = (
            alt.Chart(repartition_decisions)
            .mark_arc(
                innerRadius=75,
                outerRadius=115,
                cornerRadius=6,
                padAngle=0.025,
            )
            .encode(
                theta=alt.Theta(
                    "Nombre de cas:Q"
                ),
                color=alt.Color(
                    "Mode de décision:N",
                    scale=alt.Scale(
                        domain=[
                            "Règle métier",
                            "Analyse humaine",
                        ],
                        range=[
                            "#78D900",
                            "#087DB5",
                        ],
                    ),
                    legend=alt.Legend(
                        title=None,
                        orient="bottom",
                    ),
                ),
                tooltip=[
                    alt.Tooltip(
                        "Mode de décision:N",
                        title="Décision",
                    ),
                    alt.Tooltip(
                        "Nombre de cas:Q",
                        title="Nombre de cas",
                    ),
                ],
            )
            .properties(height=300)
        )

        centre_data = pd.DataFrame(
            {
                "texte": [
                    f"{taux_couverture:.1f} %"
                ]
            }
        )

        centre = (
            alt.Chart(centre_data)
            .mark_text(
                size=27,
                fontWeight="bold",
                color="#071F4A",
            )
            .encode(
                text="texte:N"
            )
        )

        st.altair_chart(
            donut + centre,
            use_container_width=True,
        )

        st.caption(
            "Vert : cas couverts par une règle métier · "
            "Bleu : cas conservés pour analyse humaine."
        )


    # ========================================================
    # TRAITEMENTS PROPOSÉS
    # ========================================================

    with droite:

        st.markdown(
            """
<div class="section-label">
Automatisation
</div>

<div class="section-title">
Traitements proposés
</div>
            """,
            unsafe_allow_html=True,
        )

        if cas_regles.empty:

            st.info(
                "Aucun traitement n'est actuellement "
                "proposé par une règle métier."
            )

        else:

            repartition_traitements = (
                cas_regles["Traitement proposé"]
                .value_counts()
                .rename_axis("Traitement proposé")
                .reset_index(name="Nombre de cas")
            )

            st.dataframe(
                repartition_traitements,
                use_container_width=True,
                hide_index=True,
                height=245,
            )

            st.caption(
                "Ces propositions proviennent uniquement "
                "des règles retenues dans le périmètre "
                "actuel du PoC."
            )


    # ========================================================
    # EXPLORATION
    # ========================================================

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        """
<div class="section-label">
Exploration
</div>

<div class="section-title">
Consulter les résultats
</div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(
        "Synthèse par type de rejet",
        expanded=True,
    ):

        synthese = creer_synthese(
            df_results
        )

        st.dataframe(
            synthese,
            use_container_width=True,
            hide_index=True,
            height=380,
        )


    with st.expander(
        f"Cas couverts par une règle métier ({total_regles})",
        expanded=False,
    ):

        if cas_regles.empty:

            st.info("Aucun cas couvert.")

        else:

            traitements_disponibles = sorted(
                cas_regles[
                    "Traitement proposé"
                ]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            traitements_selectionnes = st.multiselect(
                "Filtrer par traitement proposé",
                options=traitements_disponibles,
                default=[],
                placeholder="Tous les traitements",
            )

            cas_regles_filtres = cas_regles.copy()

            if traitements_selectionnes:

                cas_regles_filtres = (
                    cas_regles_filtres[
                        cas_regles_filtres[
                            "Traitement proposé"
                        ]
                        .astype(str)
                        .isin(
                            traitements_selectionnes
                        )
                    ]
                )

            colonnes = [
                "PDS",
                "Matricule compteur",
                "Matricule émetteur",
                "Scénario",
                "Résultat",
                "Traitement proposé",
                "Justification",
            ]

            colonnes = [
                c
                for c in colonnes
                if c in cas_regles_filtres.columns
            ]

            st.dataframe(
                preparer_affichage(
                    cas_regles_filtres[
                        colonnes
                    ]
                ),
                use_container_width=True,
                hide_index=True,
                height=430,
            )


    with st.expander(
        f"Cas nécessitant une analyse humaine ({total_humain})",
        expanded=False,
    ):

        if cas_humains.empty:

            st.success(
                "Tous les cas sont couverts."
            )

        else:

            filtre1, filtre2 = st.columns(2)

            resultats_disponibles = sorted(
                cas_humains[
                    "Résultat"
                ]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            with filtre1:

                resultats_selectionnes = st.multiselect(
                    "Filtrer par type de rejet",
                    resultats_disponibles,
                    placeholder="Tous les types de rejet",
                )

            scenarios_disponibles = []

            if "Scénario" in cas_humains.columns:

                scenarios_disponibles = sorted(
                    cas_humains[
                        "Scénario"
                    ]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )

            with filtre2:

                scenarios_selectionnes = st.multiselect(
                    "Filtrer par scénario",
                    scenarios_disponibles,
                    format_func=traduire_scenario,
                    placeholder="Tous les scénarios",
                )

            cas_filtres = cas_humains.copy()

            if resultats_selectionnes:

                cas_filtres = cas_filtres[
                    cas_filtres[
                        "Résultat"
                    ]
                    .astype(str)
                    .isin(
                        resultats_selectionnes
                    )
                ]

            if scenarios_selectionnes:

                cas_filtres = cas_filtres[
                    cas_filtres[
                        "Scénario"
                    ]
                    .astype(str)
                    .isin(
                        scenarios_selectionnes
                    )
                ]

            colonnes = [
                "PDS",
                "Matricule compteur",
                "Matricule émetteur",
                "Scénario",
                "Résultat",
                "Traitement proposé",
                "Justification",
            ]

            colonnes = [
                c
                for c in colonnes
                if c in cas_filtres.columns
            ]

            st.dataframe(
                preparer_affichage(
                    cas_filtres[
                        colonnes
                    ]
                ),
                use_container_width=True,
                hide_index=True,
                height=480,
            )


    # ========================================================
    # EXPORT PRINCIPAL
    # ========================================================

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        """
<div class="section-label">
Export
</div>

<div class="section-title">
Exporter le fichier ACT Métier enrichi
</div>
        """,
        unsafe_allow_html=True,
    )

    export_col1, export_col2 = st.columns(
        [2.3, 1],
        vertical_alignment="center",
        gap="large",
    )

    with export_col1:

        st.markdown(
            """
<div class="export-box">

<b>Export de l'analyse générale</b><br><br>

Le fichier conserve les données ACT Métier d'origine
et ajoute les propositions du prototype.

Il contient également une synthèse des rejets
et les cas restant à analyser.

</div>
            """,
            unsafe_allow_html=True,
        )

    excel_file = dataframe_to_excel(
        df_results
    )

    with export_col2:

        st.download_button(
            label="Télécharger l'export général",
            data=excel_file,
            file_name="ACT_Metier_enrichi_TR_Assist.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True,
        )


    # ========================================================
    # ANALYSE APPROFONDIE
    # ========================================================

    st.markdown("<br><br>", unsafe_allow_html=True)

    st.markdown(
        """
<div class="section-label">
Analyse approfondie
</div>

<div class="section-title">
Approfondir une anomalie spécifique
</div>

<div class="advanced-zone">

<div class="advanced-title">
Analyse métier ciblée
</div>

<div class="advanced-description">

Les rejets ACT Métier ne nécessitent pas tous
le même niveau d'analyse.

Sélectionnez une anomalie afin d'accéder à une analyse
complémentaire adaptée au type de rejet rencontré.

</div>

</div>
        """,
        unsafe_allow_html=True,
    )


    # ========================================================
    # SÉLECTEUR D'ANOMALIE
    # ========================================================

    st.markdown(
        """
<div class="anomaly-selector-header">

<div class="anomaly-selector-icon">
🔎
</div>

<div>

<div class="anomaly-selector-title">
Choisir l'anomalie à approfondir
</div>

<div class="anomaly-selector-text">
Sélectionnez un type de rejet pour ouvrir son module
d'analyse spécifique.
</div>

</div>

</div>
        """,
        unsafe_allow_html=True,
    )

    anomalie_selectionnee = st.selectbox(
        "Type d'anomalie à approfondir",
        options=ANOMALIES_DISPONIBLES,
        key="selection_anomalie",
        label_visibility="collapsed",
    )


    # ========================================================
    # AUCUNE ANOMALIE
    # ========================================================

    if (
        anomalie_selectionnee
        == "Sélectionner une anomalie"
    ):

        st.info(
            "Choisissez une anomalie dans la liste ci-dessus. "
            "Le cas « Compteur incompatible » est développé "
            "dans la version actuelle du PoC."
        )


    # ========================================================
    # COMPTEUR INCOMPATIBLE
    # ========================================================

    elif (
        anomalie_selectionnee
        == "Compteur incompatible"
    ):

        st.success(
            "✓ Module « Compteur incompatible » "
            "disponible dans le PoC"
        )

        nombre_incompatibles = int(
            df_results[
                "Résultat"
            ]
            .astype(str)
            .str.contains(
                "compteur incompatible",
                case=False,
                na=False,
            )
            .sum()
        )

        st.markdown(
            f"""
<div class="case-study-box">

<div class="case-study-title">
Cas d'étude développé : Compteur incompatible
</div>

<div class="case-study-number">
{nombre_incompatibles}
</div>

<div class="case-study-caption">
rejet(s) « Compteur incompatible » détecté(s)
dans l'extraction ACT Métier
</div>

<div class="case-study-description">

Ce rejet nécessite une analyse plus approfondie.

TR Assist propose donc d'enrichir les informations
ACT Métier avec le <b>Parc compteur ODYSSEE</b>.

Le rapprochement est effectué à partir du PDS afin
de comparer le compteur présent dans l'acte métier
avec le compteur enregistré dans le patrimoine.

Le diamètre est également utilisé comme information
complémentaire pour faciliter le diagnostic.

</div>

</div>
            """,
            unsafe_allow_html=True,
        )


        # ====================================================
        # IMPORT PARC COMPTEUR
        # ====================================================

        st.markdown(
            """
<div class="section-label">
Données complémentaires
</div>

<div class="section-title">
Importer le Parc compteur ODYSSEE
</div>
            """,
            unsafe_allow_html=True,
        )

        uploaded_parc = st.file_uploader(
            "Parc compteur ODYSSEE",
            type=[
                "csv",
                "xlsx",
                "xls",
            ],
            key="upload_parc_compteur",
            help=(
                "Le fichier doit contenir notamment "
                "ID_PDS, NUMERO_SERIE, DIAMETRE, "
                "FABRICANT et MODELE."
            ),
            label_visibility="collapsed",
        )


        # ====================================================
        # TRAITEMENT DU PARC
        # ====================================================

        if uploaded_parc is None:

            st.caption(
                "Chargez l'extraction Parc compteur pour "
                "lancer le rapprochement avec les rejets "
                "« Compteur incompatible »."
            )

        else:

            parc, erreur_parc = (
                charger_parc_compteur(
                    uploaded_parc
                )
            )

            if erreur_parc:

                st.error(
                    erreur_parc
                )

            else:

                with st.spinner(
                    "Rapprochement avec le parc compteur..."
                ):

                    analyse_compteurs = (
                        analyser_compteurs_incompatibles(
                            df_results,
                            parc,
                        )
                    )


                # ============================================
                # AUCUN CAS
                # ============================================

                if analyse_compteurs.empty:

                    st.warning(
                        "Aucun rejet « Compteur incompatible » "
                        "n'a été trouvé dans l'extraction "
                        "ACT Métier chargée."
                    )


                # ============================================
                # RÉSULTATS
                # ============================================

                else:

                    st.success(
                        "✓ Rapprochement avec le parc compteur "
                        "terminé."
                    )

                    total_incompatibles = len(
                        analyse_compteurs
                    )

                    pds_retrouves = int(
                        analyse_compteurs[
                            "PDS retrouvé"
                        ].sum()
                    )

                    pds_non_retrouves = (
                        total_incompatibles
                        - pds_retrouves
                    )

                    compteurs_coherents = int(
                        (
                            analyse_compteurs[
                                "Compteur cohérent"
                            ] == True
                        ).sum()
                    )

                    compteurs_differents = int(
                        (
                            analyse_compteurs[
                                "Compteur cohérent"
                            ] == False
                        ).sum()
                    )

                    taux_rapprochement = (
                        pds_retrouves
                        / total_incompatibles
                        * 100
                        if total_incompatibles
                        else 0
                    )


                    # ========================================
                    # KPI PARC
                    # ========================================

                    st.markdown(
                        "<br>",
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        """
<div class="section-label">
Résultats du rapprochement
</div>

<div class="section-title">
Diagnostic du parc compteur
</div>
                        """,
                        unsafe_allow_html=True,
                    )

                    p1, p2, p3, p4 = st.columns(
                        4,
                        gap="medium",
                    )

                    p1.metric(
                        "Compteurs incompatibles",
                        total_incompatibles,
                    )

                    p2.metric(
                        "PDS retrouvés",
                        pds_retrouves,
                    )

                    p3.metric(
                        "PDS non retrouvés",
                        pds_non_retrouves,
                    )

                    p4.metric(
                        "Taux de rapprochement",
                        f"{taux_rapprochement:.1f} %",
                    )

                    st.caption(
                        "Le taux de rapprochement mesure "
                        "la proportion de PDS retrouvés dans "
                        "le parc compteur. Il ne constitue pas "
                        "un taux de correction automatique."
                    )


                    # ========================================
                    # RÉPARTITION DES DIAGNOSTICS
                    # ========================================

                    diagnostic_resume = pd.DataFrame(
                        {
                            "Diagnostic": [
                                "Compteur cohérent",
                                "Compteur différent",
                                "PDS non retrouvé",
                            ],
                            "Nombre de cas": [
                                compteurs_coherents,
                                compteurs_differents,
                                pds_non_retrouves,
                            ],
                        }
                    )

                    diagnostic_resume = (
                        diagnostic_resume[
                            diagnostic_resume[
                                "Nombre de cas"
                            ] > 0
                        ]
                        .copy()
                    )

                    st.markdown(
                        "<br>",
                        unsafe_allow_html=True,
                    )

                    graph_col, table_col = st.columns(
                        [1.05, 1],
                        gap="large",
                    )


                    # ========================================
                    # DONUT
                    # ========================================

                    with graph_col:

                        st.markdown(
                            """
<div class="section-label">
Répartition
</div>

<div class="section-title">
Diagnostic des compteurs
</div>
                            """,
                            unsafe_allow_html=True,
                        )

                        donut_parc = (
                            alt.Chart(
                                diagnostic_resume
                            )
                            .mark_arc(
                                innerRadius=75,
                                outerRadius=115,
                                cornerRadius=6,
                                padAngle=0.025,
                            )
                            .encode(
                                theta=alt.Theta(
                                    "Nombre de cas:Q"
                                ),

                                color=alt.Color(
                                    "Diagnostic:N",

                                    scale=alt.Scale(
                                        domain=[
                                            "Compteur cohérent",
                                            "Compteur différent",
                                            "PDS non retrouvé",
                                        ],

                                        range=[
                                            "#78D900",
                                            "#18A9D5",
                                            "#087DB5",
                                        ],
                                    ),

                                    legend=alt.Legend(
                                        title=None,
                                        orient="bottom",
                                    ),
                                ),

                                tooltip=[
                                    alt.Tooltip(
                                        "Diagnostic:N",
                                        title="Diagnostic",
                                    ),

                                    alt.Tooltip(
                                        "Nombre de cas:Q",
                                        title="Nombre de cas",
                                    ),
                                ],
                            )
                            .properties(
                                height=300
                            )
                        )

                        centre_parc_data = pd.DataFrame(
                            {
                                "texte": [
                                    f"{total_incompatibles} cas"
                                ]
                            }
                        )

                        centre_parc = (
                            alt.Chart(
                                centre_parc_data
                            )
                            .mark_text(
                                size=25,
                                fontWeight="bold",
                                color="#071F4A",
                            )
                            .encode(
                                text="texte:N"
                            )
                        )

                        st.altair_chart(
                            donut_parc + centre_parc,
                            use_container_width=True,
                        )

                        st.caption(
                            "Répartition des rejets "
                            "« Compteur incompatible » "
                            "après rapprochement avec "
                            "le Parc compteur ODYSSEE."
                        )


                    # ========================================
                    # TABLEAU RÉCAPITULATIF
                    # ========================================

                    with table_col:

                        st.markdown(
                            """
<div class="section-label">
Synthèse
</div>

<div class="section-title">
Résultats du rapprochement
</div>
                            """,
                            unsafe_allow_html=True,
                        )

                        diagnostic_affichage = (
                            diagnostic_resume
                            .sort_values(
                                "Nombre de cas",
                                ascending=False,
                            )
                            .reset_index(
                                drop=True
                            )
                        )

                        diagnostic_affichage[
                            "Part des cas (%)"
                        ] = (
                            diagnostic_affichage[
                                "Nombre de cas"
                            ]
                            / total_incompatibles
                            * 100
                        ).round(1)

                        st.dataframe(
                            diagnostic_affichage,
                            use_container_width=True,
                            hide_index=True,
                            height=245,
                        )

                        st.caption(
                            "Le détail de chaque catégorie "
                            "est disponible ci-dessous et "
                            "dans l'export Excel."
                        )


                    # ========================================
                    # DÉTAIL DU RAPPROCHEMENT
                    # ========================================

                    with st.expander(
                        "Afficher le détail du rapprochement",
                        expanded=False,
                    ):

                        colonnes_parc = [
                            "PDS",
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

                        colonnes_parc = [
                            c
                            for c in colonnes_parc
                            if c in analyse_compteurs.columns
                        ]

                        affichage_parc = (
                            analyse_compteurs[
                                colonnes_parc
                            ]
                            .copy()
                            .rename(
                                columns={
                                    "NUMERO_SERIE":
                                        "Compteur parc ODYSSEE",

                                    "FABRICANT":
                                        "Fabricant parc",

                                    "MODELE":
                                        "Modèle parc",
                                }
                            )
                            .fillna("—")
                        )

                        st.dataframe(
                            affichage_parc,
                            use_container_width=True,
                            hide_index=True,
                            height=430,
                        )


                    # ========================================
                    # EXPLICATION
                    # ========================================

                    st.info(
                        "Cette analyse enrichit le rejet SITR "
                        "avec les informations du parc compteur. "
                        "Elle signale les écarts observés mais "
                        "ne réalise aucune modification automatique "
                        "dans ODYSSEE ou SITR."
                    )


                    # ========================================
                    # EXPORT COMPTEURS
                    # ========================================

                    st.markdown(
                        """
<div class="export-box">

<b>Export de l'analyse « Compteur incompatible »</b>
<br><br>

Le fichier contient le détail du rapprochement
entre les données ACT Métier et le Parc compteur ODYSSEE.

Il contient également une synthèse des diagnostics
et des feuilles distinctes regroupant les cas
selon le diagnostic obtenu.

Ces feuilles permettent notamment de récupérer directement
les dossiers concernés et de les transmettre au service
ou à la personne chargée de leur analyse.

<br><br>

Les résultats constituent une aide à l'analyse.
Aucune correction n'est directement appliquée
aux systèmes d'information.

</div>
                        """,
                        unsafe_allow_html=True,
                    )

                    excel_compteurs = (
                        exporter_analyse_compteurs(
                            analyse_compteurs
                        )
                    )

                    st.download_button(
                        label=(
                            "Télécharger l'analyse "
                            "des compteurs incompatibles"
                        ),

                        data=excel_compteurs,

                        file_name=(
                            "Analyse_compteurs_incompatibles_"
                            "TR_Assist.xlsx"
                        ),

                        mime=(
                            "application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet"
                        ),

                        use_container_width=True,
                        key="download_compteurs_incompatibles",
                    )


    # ========================================================
    # AUTRES ANOMALIES
    # ========================================================

    else:

        st.info(
            "Extension prévue"
        )

        st.info(
            f"Le module spécifique « {anomalie_selectionnee} » "
            "n'est pas développé dans le périmètre actuel du PoC. "
            "L'architecture de TR Assist permet toutefois "
            "d'intégrer progressivement une logique adaptée "
            "à chaque type d'anomalie."
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
<div class="footer">

<strong>TR Assist · Prototype de mémoire</strong><br>

Prototype conçu et développé par
<strong>Farah MEHANNEK</strong><br>

Mastère Intelligence Artificielle,
Développement et Big Data · Promotion 2024–2026<br>

Projet réalisé en apprentissage chez SUEZ Eau de France

</div>
    """,
    unsafe_allow_html=True,
)