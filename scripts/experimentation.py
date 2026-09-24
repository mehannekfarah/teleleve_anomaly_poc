"""
Expérimentation comparative — Qualification des rejets ACT Métier
Farah MEHANNEK — Mémoire Mastère IA, Développement et Big Data

Question : pour proposer le traitement d'un rejet ACT Métier, comment se comparent
une référence naïve, des règles métier et des modèles d'apprentissage supervisé,
et l'enrichissement par le parc ODYSSEE améliore-t-il la qualification ?

Protocole : validation croisée stratifiée répétée (5 plis x 5 répétitions),
prédictions hors-pli, mêmes données et mêmes métriques pour toutes les approches.
"""
import re, json, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix, precision_score

warnings.filterwarnings("ignore")
print("Chargement des données...", flush=True)
RNG = 42
import os
from pathlib import Path

# Chemins calculés à partir de l'emplacement du script : le script fonctionne
# quel que soit le dossier depuis lequel on le lance.
RACINE = Path(__file__).resolve().parents[1]                  # dossier teleleve_anomaly_poc
DOSSIER_DONNEES = RACINE / "data" / "processed"                # extractions pseudonymisées
OUT = str(RACINE / "outputs" / "experimentation")              # tableaux et figures produits
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- 1. Données
hist = pd.read_excel(os.path.join(DOSSIER_DONNEES, "ACT_Metier_historique_pseudonymise.xlsx"))
parc = pd.read_csv(os.path.join(DOSSIER_DONNEES, "Parc_compteur_pseudonymise.csv"), sep=";", encoding="utf-8-sig", dtype=str)

# ---------------------------------------------------------------- 2. Normalisation de la cible
def normaliser(t):
    if pd.isna(t):
        return None
    s = str(t).strip().lower()
    if s.startswith("voir nc"): return "Vérification terrain (NC)"
    if "chgt émet" in s or "chgt emet" in s: return "Changement émetteur"
    if s == "association": return "Association"
    if "annul" in s: return "Annulation"
    if "it4us" in s: return "IT4US"
    if "attente" in s or "attene" in s or s == "at": return "Attente clôture intervention"
    if "sop" in s: return "Support (SOP)"
    if "correction" in s or "maj" in s or "chgt cptr" in s: return "Correction données compteur"
    return "Autre"

hist["Classe"] = hist["Traitement"].apply(normaliser)
table_norm = (hist.dropna(subset=["Traitement"]).assign(Libelle=lambda x: x["Traitement"].astype(str).str.strip())
              .groupby(["Classe", "Libelle"]).size().reset_index(name="Effectif")
              .sort_values(["Classe", "Effectif"], ascending=[True, False]))
table_norm.to_csv(f"{OUT}/table_normalisation.csv", index=False, sep=";", encoding="utf-8-sig")

# ---------------------------------------------------------------- 3. Variables
def nid(v):
    if pd.isna(v): return None
    v = str(v).strip().upper()
    return v[:-2] if v.endswith(".0") else v

DIAM = {"A":15,"B":20,"D":30,"E":40,"F":50,"G":60,"H":80,"I":100,"J":125,"K":150,"L":200,"M":250,"N":300,"O":400,"P":500,"U":15,"V":15,"X":0}
df = hist.copy()
df["PDS_ODY"] = df["PDS"].apply(nid).apply(lambda p: p[2:] if isinstance(p, str) and p.startswith("98") else p)
df["CPT"] = df["Matricule compteur"].apply(nid)
df["EMT"] = df["Matricule émetteur"].apply(nid)
df["code_diam"] = df["CPT"].apply(lambda m: m[4] if isinstance(m, str) and len(m) >= 5 else "?")
df["diam_deduit"] = df["code_diam"].map(DIAM).fillna(0)
for c in ["Date action terrain", "Date reçu SITR"]:
    df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
df["delai_jours"] = (df["Date reçu SITR"] - df["Date action terrain"]).dt.days.clip(lower=0).fillna(-1)
df["index_meca"] = df["Index mécanique"].notna().astype(int)
df["index_elec"] = df["Index électronique"].notna().astype(int)
df["emetteur_renseigne"] = df["EMT"].notna().astype(int)
df["logs_present"] = df["Logs"].notna().astype(int)

# Enrichissement ODYSSEE (colonnes techniques uniquement, aucune donnée client)
p = parc.copy()
p["ID_PDS"] = p["ID_PDS"].apply(nid)
p["NUMERO_SERIE"] = p["NUMERO_SERIE"].apply(nid)
p["MATRICULE_EQUIPEMENT"] = p["MATRICULE_EQUIPEMENT"].apply(nid)
p = p.drop_duplicates("ID_PDS")
df = df.merge(p.add_prefix("ody_"), left_on="PDS_ODY", right_on="ody_ID_PDS", how="left")
df["ody_pds_trouve"] = df["ody_ID_PDS"].notna().astype(int)
df["ody_compteur_identique"] = (df["CPT"] == df["ody_NUMERO_SERIE"]).astype(int)
df["ody_emetteur_identique"] = (df["EMT"] == df["ody_MATRICULE_EQUIPEMENT"]).astype(int)
df["ody_diam"] = pd.to_numeric(df["ody_DIAMETRE"], errors="coerce").fillna(-1)
df["ody_diam_coherent"] = (df["ody_diam"] == df["diam_deduit"]).astype(int)
df["ody_telereleve"] = df["ody_MODE_DE_RELEVE"].fillna("").str.contains("Télé").astype(int)
df["ody_compact"] = (df["ody_SOLUTION_COMPACTE"] == "Oui").astype(int)
df["ody_annee"] = pd.to_numeric(df["ody_ANNEE_FABRICATION"], errors="coerce").fillna(-1)
df["ody_fabricant"] = df["ody_FABRICANT"].fillna("NON_TROUVE").str.split(" - ").str[0]

CAT_ACT = ["Résultat", "Scénario", "Prémonté", "Processus", "Source", "code_diam"]
NUM_ACT = ["delai_jours", "index_meca", "index_elec", "emetteur_renseigne", "logs_present", "diam_deduit"]
CAT_ODY = ["ody_fabricant"]
NUM_ODY = ["ody_pds_trouve", "ody_compteur_identique", "ody_emetteur_identique", "ody_diam", "ody_diam_coherent",
           "ody_telereleve", "ody_compact", "ody_annee"]

def matrice(d, avec_ody):
    cat = CAT_ACT + (CAT_ODY if avec_ody else [])
    num = NUM_ACT + (NUM_ODY if avec_ody else [])
    X = pd.get_dummies(d[cat].astype(str), dtype=int)
    return pd.concat([X, d[num].reset_index(drop=True).set_index(X.index)], axis=1)

# ---------------------------------------------------------------- 4. Jeu d'évaluation
lab = df[df["Classe"].notna()].copy()
n_autre = int((lab["Classe"] == "Autre").sum())
lab = lab[lab["Classe"] != "Autre"].reset_index(drop=True)
y = lab["Classe"].to_numpy(dtype=object)
classes = sorted(pd.unique(y))
X_act = matrice(lab, False).values
X_ody = matrice(lab, True).values
cols_ody = list(matrice(lab, True).columns)

REGLES = {
    "Ce PDS est déjà associé - Changer le libellé d'intervention": "Changement émetteur",
    "Fichier fabricant non reçu": "IT4US",
    "Aucune trame n'a été trouvée dans la plage horaire autorisée": "Vérification terrain (NC)",
}
AMBIGUS = ["Compteur incompatible", "Ce PDS n'est pas associé", "Poids d'impulsion vide", "Ce PDS est absent du patrimoine"]
lab["ambigu"] = lab["Résultat"].apply(lambda r: any(str(r).startswith(a) for a in AMBIGUS)).astype(int)
lab["couvert_regle"] = lab["Résultat"].str.strip().isin(REGLES).astype(int)

# ---------------------------------------------------------------- 5. Validation croisée
cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=RNG)
modeles = {
    "Arbre de décision": lambda: DecisionTreeClassifier(max_depth=6, class_weight="balanced", random_state=RNG),
    "Forêt aléatoire": lambda: RandomForestClassifier(n_estimators=300, class_weight="balanced", min_samples_leaf=1, random_state=RNG, n_jobs=-1),
    "Régression logistique": lambda: LogisticRegression(max_iter=3000, class_weight="balanced", C=1.0),
}

res = []                 # une ligne par (méthode, répétition)
oof = {}                 # prédictions hors-pli (dernière répétition gardée pour les matrices)
proba_rf = np.zeros((len(y), len(classes)))
n_rep_rf = np.zeros(len(y))

def score(nom, rep, yt, yp, masque_couv=None, sous_ens=None):
    idx = np.arange(len(yt)) if sous_ens is None else sous_ens
    yt_, yp_ = yt[idx], yp[idx]
    if masque_couv is not None:
        m = masque_couv[idx]
        couv = m.mean()
        prec = (yt_[m] == yp_[m]).mean() if m.sum() else np.nan
    else:
        couv, prec = 1.0, (yt_ == yp_).mean()
    res.append(dict(Methode=nom, Rep=rep, Couverture=couv, Exactitude_sur_couverts=prec,
                    Exactitude_globale=(yt_ == yp_).mean(),
                    F1_macro=f1_score(yt_, yp_, average="macro", labels=[c for c in classes if c in yt_], zero_division=0)))

print(f"{len(y)} rejets évalués, {len(classes)} classes de traitement. Validation croisée en cours (1 à 5 minutes)...", flush=True)
splits = list(cv.split(X_act, y))
for rep in range(5):
    print(f"  Répétition {rep + 1}/5 en cours...", flush=True)
    preds = {k: np.empty(len(y), dtype=object) for k in
             ["Référence naïve (classe majoritaire)", "Règles apprises (table Résultat→Traitement)"] +
             [f"{m} — ACT seul" for m in modeles] + [f"{m} — ACT + ODYSSEE" for m in modeles]}
    couv_table = np.zeros(len(y), dtype=bool)
    for tr, te in splits[rep*5:(rep+1)*5]:
        ytr = y[tr]
        maj = pd.Series(ytr).mode()[0]
        preds["Référence naïve (classe majoritaire)"][te] = maj
        # règles apprises : traitement majoritaire par Résultat, si vu en apprentissage
        t = pd.DataFrame({"r": lab["Résultat"].to_numpy(dtype=object)[tr], "y": ytr}).groupby("r")["y"].agg(lambda s: s.mode()[0])
        rr = lab["Résultat"].to_numpy(dtype=object)[te]
        preds["Règles apprises (table Résultat→Traitement)"][te] = [t.get(r, maj) for r in rr]
        couv_table[te] = [r in t.index for r in rr]
        for mn, f in modeles.items():
            for suf, X in [("ACT seul", X_act), ("ACT + ODYSSEE", X_ody)]:
                m = f().fit(X[tr], ytr)
                preds[f"{mn} — {suf}"][te] = m.predict(X[te])
                if mn == "Forêt aléatoire" and suf == "ACT + ODYSSEE":
                    pr = m.predict_proba(X[te])
                    full = np.zeros((len(te), len(classes)))
                    for j, c in enumerate(m.classes_): full[:, classes.index(c)] = pr[:, j]
                    proba_rf[te] += full; n_rep_rf[te] += 1
    for k, v in preds.items():
        score(k, rep, y, v)
        score(k + " [cas ambigus]", rep, y, v, sous_ens=np.where(lab["ambigu"] == 1)[0])
    oof = preds

# Règles expertes (fixes, pas d'apprentissage) : couverture + exactitude sur les cas couverts
yp_regle = lab["Résultat"].str.strip().map(REGLES).fillna("HUMAIN").to_numpy(dtype=object)
m_regle = yp_regle != "HUMAIN"
score("Règles métier expertes (3 règles)", 0, y, yp_regle, masque_couv=m_regle)

R = (pd.DataFrame(res).groupby("Methode")
     .agg(Couverture=("Couverture", "mean"), Exactitude_sur_couverts=("Exactitude_sur_couverts", "mean"),
          F1_macro=("F1_macro", "mean"), F1_macro_ecart_type=("F1_macro", "std"))
     .round(3).reset_index())
R.to_csv(f"{OUT}/resultats_comparaison.csv", index=False, sep=";", encoding="utf-8-sig")

print("Calcul de l'approche hybride et des figures...", flush=True)
# ---------------------------------------------------------------- 6. Hybride : règles + forêt avec seuil
proba = proba_rf / np.maximum(n_rep_rf, 1)[:, None]
conf = proba.max(1); yp_rf = np.array(classes)[proba.argmax(1)]
courbe = []
for s in np.round(np.arange(0.30, 1.00, 0.05), 2):
    auto_ml = (~m_regle) & (conf >= s)
    pred = np.where(m_regle, yp_regle, yp_rf)
    auto = m_regle | auto_ml
    courbe.append(dict(Seuil=s, Couverture=auto.mean(),
                       Exactitude_cas_auto=(pred[auto] == y[auto]).mean(),
                       Couverture_ML_seul=auto_ml.mean(),
                       Exactitude_ML_cas_auto=(pred[auto_ml] == y[auto_ml]).mean() if auto_ml.sum() else np.nan))
C = pd.DataFrame(courbe).round(3)
C.to_csv(f"{OUT}/hybride_seuils.csv", index=False, sep=";", encoding="utf-8-sig")

# ---------------------------------------------------------------- 7. Figures
plt.rcParams.update({"font.size": 10})
fig, ax = plt.subplots(figsize=(7, 4.2))
ax.plot(C["Couverture"]*100, C["Exactitude_cas_auto"]*100, "o-", color="#1592B8", label="Hybride : règles + forêt aléatoire")
for _, r in C[C["Seuil"].isin([0.30, 0.50, 0.60, 0.90])].iterrows():
    ax.annotate(f"seuil {r.Seuil:.2f}", (r.Couverture*100, r.Exactitude_cas_auto*100), textcoords="offset points", xytext=(-55, -4), fontsize=8)
ax.scatter([m_regle.mean()*100], [(yp_regle[m_regle] == y[m_regle]).mean()*100], color="#4FA83A", s=70, zorder=5, label="Règles expertes seules")
ax.set_xlabel("Couverture : part des rejets traités automatiquement (%)")
ax.set_ylabel("Exactitude sur les cas automatisés (%)")
ax.set_title("Compromis couverture / exactitude selon le seuil de confiance")
ax.grid(alpha=.3); ax.legend(loc="lower left")
fig.tight_layout(); fig.savefig(f"{OUT}/fig_couverture_exactitude.png", dpi=200); plt.close(fig)

best = "Forêt aléatoire — ACT + ODYSSEE"
cm = confusion_matrix(y, oof[best], labels=classes)
fig, ax = plt.subplots(figsize=(7.5, 6))
ax.imshow(cm, cmap="Blues")
ax.set_xticks(range(len(classes))); ax.set_xticklabels(classes, rotation=40, ha="right", fontsize=8)
ax.set_yticks(range(len(classes))); ax.set_yticklabels(classes, fontsize=8)
for i in range(len(classes)):
    for j in range(len(classes)):
        ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=8, color="white" if cm[i, j] > cm.max()/2 else "black")
ax.set_xlabel("Traitement prédit"); ax.set_ylabel("Traitement réel (décision humaine)")
ax.set_title("Matrice de confusion — forêt aléatoire (ACT + ODYSSEE)")
fig.tight_layout(); fig.savefig(f"{OUT}/fig_matrice_confusion.png", dpi=200); plt.close(fig)

rf = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=RNG, n_jobs=-1).fit(X_ody, y)
imp = pd.Series(rf.feature_importances_, index=cols_ody).sort_values(ascending=False).head(12)
NOMS = {"delai_jours": "Délai action terrain → réception SITR", "ody_annee": "Année de fabrication (ODYSSEE)",
        "ody_compteur_identique": "Compteur identique au parc (ODYSSEE)", "index_meca": "Index mécanique renseigné",
        "emetteur_renseigne": "Matricule émetteur renseigné", "logs_present": "Journaux techniques présents",
        "ody_compact": "Solution compacte (ODYSSEE)", "ody_diam": "Diamètre (ODYSSEE)", "index_elec": "Index électronique renseigné",
        "ody_pds_trouve": "PDS retrouvé dans le parc", "ody_emetteur_identique": "Émetteur identique au parc (ODYSSEE)",
        "diam_deduit": "Diamètre déduit du matricule", "ody_diam_coherent": "Diamètre cohérent avec le parc"}
def libelle(v):
    if v.startswith("Résultat_"):
        t = "Motif : " + v[len("Résultat_"):].split(" - ")[0]
    else:
        t = NOMS.get(v, v)
    return t if len(t) <= 48 else t[:47] + "…"
fig, ax = plt.subplots(figsize=(9, 5))
ax.barh([libelle(i) for i in imp.index[::-1]], imp.values[::-1], color="#0B2A55")
ax.set_xlabel("Importance (réduction d'impureté)")
fig.suptitle("Variables les plus utilisées par la forêt aléatoire", fontsize=12)
fig.tight_layout(); fig.savefig(f"{OUT}/fig_importance_variables.png", dpi=200); plt.close(fig)

rep = classification_report(y, oof[best], labels=classes, zero_division=0, output_dict=True)
pd.DataFrame(rep).T.round(3).to_csv(f"{OUT}/rapport_par_classe_foret_ody.csv", sep=";", encoding="utf-8-sig")

info = dict(n_total=len(hist), n_labellises=int(hist["Classe"].notna().sum()), n_autre_exclus=n_autre,
            n_evaluation=len(y), n_non_traites=int(hist["Classe"].isna().sum()),
            repartition=pd.Series(y).value_counts().to_dict(), n_ambigus=int(lab["ambigu"].sum()),
            regles_couverture=float(m_regle.mean()), regles_exactitude=float((yp_regle[m_regle] == y[m_regle]).mean()),
            pds_trouves_parc=int(lab["ody_pds_trouve"].sum()))
json.dump(info, open(f"{OUT}/info.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
print(json.dumps(info, ensure_ascii=False, indent=1, default=float))
pd.set_option("display.width", 200)
print(R.to_string()); print(C.to_string())
print(imp.round(3).to_string())
print(f"\nTerminé. Résultats et figures enregistrés dans : {OUT}", flush=True)