"""
Pseudonymisation des données pour la soutenance (RGPD)
Farah MEHANNEK — TR Assist

Principes appliqués :
1. Minimisation : on ne conserve que les colonnes techniques utiles, et dans le parc
   seulement les PDS présents dans l'extraction ACT Métier.
2. Suppression : toutes les données clients (nom, civilité, téléphones, e-mail,
   adresses, compte client…) sont retirées.
3. Pseudonymisation cohérente : PDS, matricules compteur et émetteur sont remplacés
   par des identifiants fictifs, avec LA MÊME correspondance dans tous les fichiers,
   pour que le rapprochement SITR / ODYSSEE et l'application continuent de fonctionner.
   Le format est conservé (préfixe « 98 » du PDS, 5 premiers caractères du matricule
   compteur qui portent le diamètre).
La clé secrète (SEL) ne doit pas être diffusée : sans elle, la correspondance est
irréversible pour un tiers.
"""
import hashlib, os, re, secrets
from pathlib import Path
import pandas as pd

SEL = os.environ.get("SEL_PSEUDO") or secrets.token_hex(32)   # clé aléatoire, jamais enregistrée
# Chemins calculés à partir de l'emplacement du script (dossier scripts/ du projet)
RACINE = Path(__file__).resolve().parents[1]
ENTREE = RACINE / "data" / "raw"          # extractions brutes (ne jamais diffuser)
SORTIE = RACINE / "data" / "processed"    # extractions pseudonymisées
os.makedirs(SORTIE, exist_ok=True)

def h(texte, n, alphabet="0123456789"):
    d = hashlib.sha256((SEL + "|" + texte).encode()).digest()
    val = int.from_bytes(d, "big")
    out = ""
    for _ in range(n):
        val, r = divmod(val, len(alphabet)); out += alphabet[r]
    return out

def nid(v):
    if pd.isna(v): return None
    v = str(v).strip().upper()
    return v[:-2] if v.endswith(".0") else v

# --- PDS : 10 chiffres fictifs ; le préfixe 98 de SITR est conservé
def pds_parc(v):
    v = nid(v)
    return None if v is None else h("PDS" + v, 10)
def pds_act(v):
    v = nid(v)
    if v is None: return None
    coeur = v[2:] if v.startswith("98") else v
    return ("98" if v.startswith("98") else "") + pds_parc(coeur)

# --- Matricule compteur : 5 premiers caractères conservés (fabricant, année, diamètre), le reste remplacé
def mat_token(t):
    if len(t) < 5: return t
    reste = "".join(h("CPT" + t + str(i), 1, "0123456789" if c.isdigit() else "ABCDEFGHJKLMNPRSTUVWXYZ")
                    for i, c in enumerate(t[5:]))
    return t[:5] + reste
def mat_compteur(v):
    if pd.isna(v): return v
    s = str(v).strip().upper()
    if s.endswith(".0"): s = s[:-2]
    return re.sub(r"[A-Z0-9]+", lambda m: mat_token(m.group(0)), s)

# --- Matricule émetteur : 4 premiers caractères conservés
def mat_emetteur(v):
    v = nid(v)
    if v is None: return None
    return v[:4] + h("EMT" + v, max(len(v) - 4, 6))

COL_PARC = ["ID_PDS", "NUMERO_SERIE", "MATRICULE_EQUIPEMENT", "FABRICANT", "MODELE", "DIAMETRE",
            "ANNEE_FABRICATION", "SOLUTION_COMPACTE", "MODE_DE_RELEVE", "ETAT_PDS"]

def traiter_act(df):
    df = df.copy()
    df["PDS"] = df["PDS"].apply(pds_act)
    df["Matricule compteur"] = df["Matricule compteur"].apply(mat_compteur)
    df["Matricule émetteur"] = df["Matricule émetteur"].apply(mat_emetteur)
    if "Fichier" in df.columns:
        df["Fichier"] = df["Fichier"].astype(str).str.extract(r"([^\\/]+)$")[0]   # garde seulement le nom du fichier
    return df

print("Pseudonymisation des extractions ACT Métier...", flush=True)
# 1. ACT Métier historique (avec Traitement) et extraction de juillet (sans Traitement)
hist = pd.read_excel(f"{ENTREE}/Historique_Fichier_acte_metier.xlsx", sheet_name=2)
juil = pd.read_excel(f"{ENTREE}/act_metier_juillet.xlsx")
hist_a, juil_a = traiter_act(hist), traiter_act(juil)
hist_a.to_excel(f"{SORTIE}/ACT_Metier_historique_pseudonymise.xlsx", index=False)
juil_a.to_excel(f"{SORTIE}/ACT_Metier_juillet_pseudonymise.xlsx", index=False)

print("Pseudonymisation du parc compteur (peut prendre une minute)...", flush=True)
# 2. Parc compteur : colonnes techniques + PDS utiles uniquement
pds_utiles = set(hist["PDS"].apply(nid).dropna().apply(lambda p: p[2:] if p.startswith("98") else p).tolist())
parc = pd.read_csv(f"{ENTREE}/Parc_compteur.csv", sep=";", encoding="utf-8-sig", usecols=COL_PARC, dtype=str)
n_total = len(parc)
parc = parc[parc["ID_PDS"].apply(nid).fillna("").isin(pds_utiles)].copy()
parc["ID_PDS"] = parc["ID_PDS"].apply(pds_parc)
parc["NUMERO_SERIE"] = parc["NUMERO_SERIE"].apply(mat_compteur)
parc["MATRICULE_EQUIPEMENT"] = parc["MATRICULE_EQUIPEMENT"].apply(mat_emetteur)
parc.to_csv(f"{SORTIE}/Parc_compteur_pseudonymise.csv", sep=";", index=False, encoding="utf-8-sig")

print(f"ACT historique : {len(hist_a)} lignes | ACT juillet : {len(juil_a)} lignes")
print(f"Parc : {n_total} lignes et 111 colonnes -> {len(parc)} lignes et {len(COL_PARC)} colonnes techniques")
print(f"Terminé. Fichiers créés dans : {SORTIE}")
