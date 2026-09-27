import streamlit as st
import folium
import pandas as pd
from streamlit_folium import st_folium
from groq import Groq
import re
import unicodedata
from difflib import SequenceMatcher

# ============================================================
# CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="WATER CONFLICT",
    page_icon="💧",
    layout="wide"
)

# ============================================================
# CHARGEMENT DES DONNÉES
# ============================================================
@st.cache_data
def charger_donnees():
    return pd.read_csv("conflits_eau.csv")

df = charger_donnees()

# ============================================================
# CLÉ API GROQ (via Streamlit secrets)
# ============================================================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except Exception:
    client = None

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================
def normaliser(texte):
    if texte is None:
        return ""
    texte = str(texte).lower()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = re.sub(r"[\-/_,;.()\[\]]", " ", texte)
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte

def similitude(a, b):
    return SequenceMatcher(None, a, b).ratio()

def chercher_zone(question, seuil=0.72):
    q = normaliser(question)
    mots_question = [m for m in q.split() if len(m) >= 3]
    meilleure, score_max = None, 0
    for _, ligne in df.iterrows():
        score = 0
        for champ in [ligne["nom"], ligne["ressource_en_eau"], ligne["region"]]:
            for mot in normaliser(champ).split():
                if len(mot) < 3:
                    continue
                if mot in mots_question:
                    score += 3
                else:
                    for mq in mots_question:
                        if similitude(mot, mq) >= seuil:
                            score += 2
                            break
        for pays in normaliser(ligne["pays_concernes"]).split():
            if len(pays) < 3:
                continue
            if pays in mots_question:
                score += 4
            else:
                for mq in mots_question:
                    if similitude(pays, mq) >= seuil:
                        score += 3
                        break
        if score > score_max:
            score_max, meilleure = score, ligne
    return meilleure if score_max > 0 else None

def construire_contexte(sous_df):
    blocs = []
    for _, z in sous_df.iterrows():
        blocs.append(f"""ZONE : {z['nom']}
Région : {z['region']}
Pays concernés : {z['pays_concernes']}
Ressource : {z['ressource_en_eau']} ({z['type']})
Statut : {z['statut']}
Enjeux : {z['enjeux']}
Description : {z['description']}
Sources : {z['sources']}""")
    return "\n\n---\n\n".join(blocs)

SYSTEM_PROMPT = """Tu es WATER CONFLICT, un assistant expert spécialisé UNIQUEMENT sur :
- les conflits, tensions, crises et guerres liés aux ressources en eau dans le monde ;
- les fleuves, lacs, aquifères, barrages et bassins transfrontaliers ;
- les acteurs (États, ONU, organisations régionales) et les enjeux géopolitiques.

RÈGLES ABSOLUES :
1. Tu réponds TOUJOURS en français, de façon claire, factuelle et concise.
2. Tu te bases UNIQUEMENT sur le CONTEXTE fourni. Si une information n'y est pas, dis-le honnêtement.
3. Si la question sort du thème (eau/conflits), recentre poliment la réponse sur la thématique.
4. Ne jamais inventer de chiffres, de dates ou d'événements.
5. Structure ta réponse : réponse directe → éléments clés → sources.
6. Reste neutre politiquement, factuel, académique."""

def repondre(question):
    q_norm = normaliser(question)

    # Détection région
    for region in ["afrique", "asie", "europe", "amerique", "moyen orient"]:
        if region in q_norm and any(m in q_norm for m in ["zone", "liste", "pays", "quels"]):
            noms = {"afrique": "Afrique", "asie": "Asie", "europe": "Europe",
                    "amerique": "Amériques", "moyen orient": "Moyen-Orient"}
            reg = noms.get(region, region)
            sous = df[df["region"].str.lower().str.contains(region, na=False)]
            if len(sous) == 0:
                return f"❌ Aucune zone pour la région : **{reg}**.", None
            lignes = [f"- **{r['nom']}** ({r['statut']}) — {r['pays_concernes']}" for _, r in sous.iterrows()]
            return f"### 🌍 Zones en {reg} ({len(sous)})\n\n" + "\n".join(lignes), None

    # Détection niveau critique
    if any(m in q_norm for m in ["critique", "urgent", "grave", "pire"]):
        sous = df[df["statut"].str.startswith("🔴")]
        lignes = [f"- **{r['nom']}** — {r['pays_concernes']}" for _, r in sous.iterrows()]
        return f"### 🚨 Zones critiques ({len(sous)})\n\n" + "\n".join(lignes), None

    # Recherche de zone
    zone = chercher_zone(question)
    if zone is not None:
        sous_df = df[df["nom"] == zone["nom"]]
    else:
        sous_df = df.head(5)

    contexte = construire_contexte(sous_df)

    if client is None:
        return "⚠️ Service IA temporairement indisponible. Veuillez réessayer plus tard.", zone

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"CONTEXTE :\n{contexte}\n\nQUESTION : {question}\n\nRéponds en français."}
            ],
            temperature=0.4,
            max_tokens=500,
        )
        reponse = completion.choices[0].message.content
    except Exception:
        reponse = "⚠️ Service IA temporairement indisponible. Veuillez réessayer plus tard."

    zones_src = ", ".join(sous_df["nom"].tolist())
    reponse += f"\n\n---\n📚 **Zones mobilisées :** {zones_src}"
    return reponse, zone

# ============================================================
# INTERFACE
# ============================================================
st.title("💧 WATER CONFLICT")
st.markdown("### Explorez les zones de conflits, tensions et guerres liées à l'eau dans le monde")

# --- Barre latérale : filtres ---
st.sidebar.header("🔎 Filtres")

regions = ["Toutes"] + sorted(df["region"].unique().tolist())
region_choisie = st.sidebar.selectbox("Région", regions)

niveaux = ["Tous", "🔴 Critique", "🟠 Tension", "🟡 Surveillance", "🟢 Coopération"]
niveau_choisi = st.sidebar.selectbox("Niveau", niveaux)

recherche = st.sidebar.text_input("Rechercher (pays, fleuve...)")

# Filtrage
df_filtre = df.copy()
if region_choisie != "Toutes":
    df_filtre = df_filtre[df_filtre["region"] == region_choisie]
if niveau_choisi != "Tous":
    prefix = niveau_choisi.split()[0]
    df_filtre = df_filtre[df_filtre["statut"].str.startswith(prefix)]
if recherche:
    r = normaliser(recherche)
    mask = (
        df_filtre["nom"].apply(normaliser).str.contains(r, na=False)
        | df_filtre["pays_concernes"].apply(normaliser).str.contains(r, na=False)
        | df_filtre["ressource_en_eau"].apply(normaliser).str.contains(r, na=False)
    )
    df_filtre = df_filtre[mask]

# --- Statistiques ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("🌍 Zones affichées", len(df_filtre))
col2.metric("🔴 Critiques", len(df_filtre[df_filtre["statut"].str.startswith("🔴")]))
col3.metric("🟠 Tensions", len(df_filtre[df_filtre["statut"].str.startswith("🟠")]))
col4.metric("🟡 Surveillance", len(df_filtre[df_filtre["statut"].str.startswith("🟡")]))

# --- Carte ---
st.subheader("🗺️ Carte mondiale")

couleurs = {
    "🟥": "darkred", "🔴": "red", "🟠": "orange",
    "🟡": "gold", "🟢": "green"
}

m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB positron")

for _, row in df_filtre.iterrows():
    prefix = row["statut"][:1] if len(row["statut"]) > 0 else "🔴"
    couleur = couleurs.get(prefix, "blue")
    popup_html = f"""
    <div style="width:300px">
    <h4>💧 {row['nom']}</h4>
    <b>Région :</b> {row['region']}<br>
    <b>Pays :</b> {row['pays_concernes']}<br>
    <b>Ressource :</b> {row['ressource_en_eau']}<br>
    <b>Statut :</b> {row['statut']}<br>
    <b>Enjeux :</b> {row['enjeux']}<br>
    </div>
    """
    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=10,
        color=couleur,
        fill=True,
        fill_color=couleur,
        fill_opacity=0.8,
        popup=folium.Popup(popup_html, max_width=350),
        tooltip=f"{row['nom']} — {row['statut']}"
    ).add_to(m)

st_folium(m, width="stretch", height=550, returned_objects=[])

# --- Fiche détaillée ---
st.subheader("📋 Fiche d'une zone")
zone_choisie = st.selectbox("Sélectionnez une zone", df_filtre["nom"].tolist())

if zone_choisie:
    z = df[df["nom"] == zone_choisie].iloc[0]
    st.markdown(f"""
    ### 💧 {z['nom']}

    | Champ | Valeur |
    |-------|--------|
    | **🌍 Région** | {z['region']} |
    | **👥 Pays concernés** | {z['pays_concernes']} |
    | **🌊 Ressource** | {z['ressource_en_eau']} ({z['type']}) |
    | **📍 Coordonnées** | {z['latitude']}°, {z['longitude']}° |
    | **🚨 Statut** | {z['statut']} |
    | **⚠️ Enjeux** | {z['enjeux']} |
    | **📖 Description** | {z['description']} |
    | **📚 Sources** | {z['sources']} |
    """)

# --- Chatbot ---
st.subheader("💬 Posez une question")
question = st.text_input("Ex : Quels sont les enjeux autour du Nil ?")

if st.button("Envoyer") and question:
    with st.spinner("Analyse en cours..."):
        rep, zone = repondre(question)
    st.markdown(rep)
    if zone is not None:
        st.caption(f"📌 Zone identifiée : {zone['nom']}")

st.markdown("---")
st.caption("🌍 WATER CONFLICT — Anas OUDADDA / Master Hydroprotech")
