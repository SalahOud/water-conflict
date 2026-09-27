import streamlit as st
import folium
import pandas as pd
from streamlit_folium import st_folium
from groq import Groq
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="WATER CONFLICT",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# STYLE
# ============================================================

css_file = Path("style.css")

if css_file.exists():
    with open(css_file, "r", encoding="utf-8") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )


# ============================================================
# DONNÉES
# ============================================================

@st.cache_data
def charger_donnees():
    return pd.read_csv("conflits_eau.csv")


df = charger_donnees()


# ============================================================
# VÉRIFICATION DES COLONNES
# ============================================================

colonnes_requises = [
    "nom",
    "region",
    "pays_concernes",
    "ressource_en_eau",
    "type",
    "latitude",
    "longitude",
    "statut",
    "enjeux",
    "description",
    "sources"
]

colonnes_manquantes = [
    c for c in colonnes_requises
    if c not in df.columns
]

if colonnes_manquantes:
    st.error(
        "Colonnes manquantes dans conflits_eau.csv : "
        + ", ".join(colonnes_manquantes)
    )
    st.stop()


# ============================================================
# GROQ
# ============================================================

try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except Exception:
    client = None


# ============================================================
# NORMALISATION
# ============================================================

def normaliser(texte):

    if texte is None:
        return ""

    texte = str(texte).lower()

    texte = unicodedata.normalize(
        "NFD",
        texte
    )

    texte = "".join(
        c for c in texte
        if unicodedata.category(c) != "Mn"
    )

    texte = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texte
    )

    texte = re.sub(
        r"\s+",
        " ",
        texte
    ).strip()

    return texte


# ============================================================
# SIMILITUDE
# ============================================================

def similitude(a, b):
    return SequenceMatcher(
        None,
        normaliser(a),
        normaliser(b)
    ).ratio()


# ============================================================
# TROUVER LES ZONES PERTINENTES
# ============================================================

def trouver_zones(question, max_zones=5):

    q = normaliser(question)

    if not q:
        return df.head(0)

    mots = [
        m for m in q.split()
        if len(m) >= 3
    ]

    resultats = []

    for index, ligne in df.iterrows():

        score = 0

        # ----------------------------------------------------
        # NOM DE LA ZONE
        # ----------------------------------------------------

        nom = normaliser(ligne["nom"])

        if nom in q:
            score += 20

        for mot in nom.split():

            if len(mot) >= 3 and mot in mots:
                score += 10

            for mq in mots:

                if similitude(mot, mq) >= 0.82:
                    score += 4

        # ----------------------------------------------------
        # RESSOURCE
        # ----------------------------------------------------

        ressource = normaliser(
            ligne["ressource_en_eau"]
        )

        if ressource in q:
            score += 15

        for mot in ressource.split():

            if len(mot) >= 3 and mot in mots:
                score += 7

            for mq in mots:

                if similitude(mot, mq) >= 0.82:
                    score += 3

        # ----------------------------------------------------
        # PAYS
        # ----------------------------------------------------

        pays = normaliser(
            ligne["pays_concernes"]
        )

        for pays_mot in pays.split():

            if len(pays_mot) < 3:
                continue

            if pays_mot in mots:
                score += 10

            for mq in mots:

                if similitude(
                    pays_mot,
                    mq
                ) >= 0.85:

                    score += 4

        # ----------------------------------------------------
        # RÉGION
        # ----------------------------------------------------

        region = normaliser(
            ligne["region"]
        )

        if region in q:
            score += 8

        # ----------------------------------------------------
        # ENJEUX
        # ----------------------------------------------------

        enjeux = normaliser(
            ligne["enjeux"]
        )

        for mot in enjeux.split():

            if len(mot) < 4:
                continue

            if mot in mots:
                score += 3

        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        description = normaliser(
            ligne["description"]
        )

        for mot in mots:

            if len(mot) >= 5 and mot in description:
                score += 1

        if score > 0:

            resultats.append(
                (score, index)
            )

    # --------------------------------------------------------
    # TRI
    # --------------------------------------------------------

    resultats.sort(
        key=lambda x: x[0],
        reverse=True
    )

    indices = [
        index
        for score, index in resultats[:max_zones]
    ]

    if not indices:
        return df.head(0)

    return df.loc[indices]


# ============================================================
# QUESTIONS GÉNÉRALES
# ============================================================

def question_generale(question):

    q = normaliser(question)

    mots_generaux = [
        "toutes les zones",
        "toutes les regions",
        "toutes les régions",
        "dans le monde",
        "monde",
        "liste",
        "quelles sont les zones",
        "quels sont les conflits",
        "zones critiques",
        "zones en tension"
    ]

    return any(
        mot in q
        for mot in mots_generaux
    )


# ============================================================
# CONSTRUIRE LE CONTEXTE
# ============================================================

def construire_contexte(sous_df):

    blocs = []

    for _, z in sous_df.iterrows():

        bloc = f"""
ZONE
Nom : {z['nom']}
Région : {z['region']}
Pays concernés : {z['pays_concernes']}
Ressource : {z['ressource_en_eau']}
Type : {z['type']}
Statut : {z['statut']}
Enjeux : {z['enjeux']}
Description : {z['description']}
Sources : {z['sources']}
"""

        blocs.append(bloc.strip())

    return "\n\n-------------------------\n\n".join(
        blocs
    )


# ============================================================
# PROMPT IA
# ============================================================

SYSTEM_PROMPT = """

Tu es l'assistant intelligent de l'application WATER CONFLICT.

Ton domaine est exclusivement celui des conflits, tensions,
coopérations et enjeux géopolitiques liés aux ressources en eau.

Tu dois répondre comme un assistant universitaire spécialisé
en hydropolitique.

IMPORTANT :

- Réponds naturellement en français.
- Ne commence PAS systématiquement par "Réponse directe".
- Ne suis PAS un modèle de réponse rigide.
- Adapte la longueur à la question.
- Une question simple doit recevoir une réponse simple.
- Une question complexe doit recevoir une réponse développée.
- Utilise des paragraphes naturels et, lorsque cela améliore
  la lisibilité, des listes courtes.
- Ne répète pas inutilement la question de l'utilisateur.
- Ne termine pas systématiquement par une section "Sources".
- Si les sources sont utiles, mentionne-les naturellement
  à la fin.
- Ne mets jamais "selon le contexte fourni" dans chaque phrase.
- Ne parle jamais de ton fonctionnement interne.

FIABILITÉ :

Tu dois utiliser exclusivement les informations présentes
dans les données fournies avec la question.

Tu ne dois pas inventer :
- chiffres
- dates
- événements
- acteurs
- accords
- conflits
- sources

Si l'information demandée n'existe pas dans les données,
dis simplement que cette information n'est pas disponible
dans la base WATER CONFLICT.

IMPORTANT :

Une tension autour de l'eau n'est pas automatiquement
une guerre.

Utilise les termes :
- tension
- crise hydropolitique
- compétition
- coopération
- conflit

uniquement lorsqu'ils correspondent aux données.

STYLE :

Le niveau attendu correspond à un travail de Master 2.

La réponse doit être claire, précise, professionnelle
et compréhensible.

Exemple de bonne réponse :

"Les tensions autour du Nil concernent principalement
l'Égypte, le Soudan et l'Éthiopie. Le principal enjeu
est la gestion du Nil Bleu et du Grand barrage de la
Renaissance éthiopienne (GERD).

Pour l'Éthiopie, le barrage représente notamment un
projet majeur de production hydroélectrique. Pour les
États situés en aval, les préoccupations portent sur
le débit disponible et la gestion de la ressource.

Les principaux enjeux identifiés dans la base sont donc
le partage de l'eau, les barrages, l'irrigation,
l'hydroélectricité et la souveraineté."

Ne copie pas cet exemple sauf si les données fournies
correspondent réellement à la question.
"""


# ============================================================
# CHATBOT
# ============================================================

def repondre(question):

    if not question.strip():

        return (
            "Posez une question sur une zone, "
            "un fleuve, un pays ou un enjeu hydropolitique.",
            None
        )

    # --------------------------------------------------------
    # Sélection intelligente des données
    # --------------------------------------------------------

    zones = trouver_zones(
        question,
        max_zones=6
    )

    # --------------------------------------------------------
    # Si question très générale
    # --------------------------------------------------------

    if question_generale(question):

        zones = df.copy()

    # --------------------------------------------------------
    # Aucun résultat
    # --------------------------------------------------------

    if len(zones) == 0:

        return (
            "Je ne trouve pas de zone correspondant "
            "à cette question dans la base WATER CONFLICT. "
            "Essayez avec le nom d'un fleuve, d'un lac, "
            "d'un pays ou d'une zone hydropolitique.",
            None
        )

    # --------------------------------------------------------
    # Contexte
    # --------------------------------------------------------

    contexte = construire_contexte(
        zones
    )

    # --------------------------------------------------------
    # Groq indisponible
    # --------------------------------------------------------

    if client is None:

        return (
            "La clé API Groq n'est pas configurée "
            "dans les Secrets Streamlit.",
            None
        )

    # --------------------------------------------------------
    # Appel LLM
    # --------------------------------------------------------

    try:

        completion = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"""
Voici les données disponibles dans WATER CONFLICT :

{contexte}

QUESTION DE L'UTILISATEUR :

{question}

Réponds directement à la question.
Utilise uniquement les données pertinentes.
"""
                }
            ],

            temperature=0.25,

            max_tokens=800
        )

        reponse = (
            completion
            .choices[0]
            .message
            .content
            .strip()
        )

        return reponse, zones

    except Exception as e:

        return (
            f"Une erreur est survenue avec le service IA : {e}",
            None
        )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="water-header">

        <div class="water-logo">
            WATER <span>CONFLICT</span>
        </div>

        <div class="water-subtitle">
            GLOBAL HYDROPOLITICAL INTELLIGENCE PLATFORM
        </div>

    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown(
    """
    <div style="
        font-size:18px;
        font-weight:700;
        letter-spacing:2px;
        color:#ffffff;
        margin-bottom:25px;
    ">
        EXPLORER
    </div>
    """,
    unsafe_allow_html=True
)


regions = [
    "Toutes"
] + sorted(
    df["region"]
    .dropna()
    .unique()
    .tolist()
)


region_choisie = st.sidebar.selectbox(
    "RÉGION",
    regions
)


niveaux = [
    "Tous",
    "🔴 Critique",
    "🟠 Tension",
    "🟡 Surveillance",
    "🟢 Coopération"
]


niveau_choisi = st.sidebar.selectbox(
    "NIVEAU",
    niveaux
)


recherche = st.sidebar.text_input(
    "RECHERCHE",
    placeholder="Pays, fleuve, lac..."
)


# ============================================================
# FILTRAGE
# ============================================================

df_filtre = df.copy()


if region_choisie != "Toutes":

    df_filtre = df_filtre[
        df_filtre["region"] == region_choisie
    ]


if niveau_choisi != "Tous":

    prefix = niveau_choisi.split()[0]

    df_filtre = df_filtre[
        df_filtre["statut"]
        .astype(str)
        .str.startswith(prefix)
    ]


if recherche:

    recherche_norm = normaliser(
        recherche
    )

    mask = (

        df_filtre["nom"]
        .apply(normaliser)
        .str.contains(
            recherche_norm,
            na=False
        )

        |

        df_filtre["pays_concernes"]
        .apply(normaliser)
        .str.contains(
            recherche_norm,
            na=False
        )

        |

        df_filtre["ressource_en_eau"]
        .apply(normaliser)
        .str.contains(
            recherche_norm,
            na=False
        )
    )

    df_filtre = df_filtre[
        mask
    ]


# ============================================================
# STATISTIQUES
# ============================================================

st.markdown(
    '<div class="section-title">Global overview</div>',
    unsafe_allow_html=True
)


col1, col2, col3, col4 = st.columns(4)


critiques = len(
    df_filtre[
        df_filtre["statut"]
        .astype(str)
        .str.startswith("🔴")
    ]
)


tensions = len(
    df_filtre[
        df_filtre["statut"]
        .astype(str)
        .str.startswith("🟠")
    ]
)


surveillance = len(
    df_filtre[
        df_filtre["statut"]
        .astype(str)
        .str.startswith("🟡")
    ]
)


with col1:

    st.markdown(
        f"""
        <div class="stat-card stat-blue">
            <div class="stat-label">Zones</div>
            <div class="stat-value">{len(df_filtre)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


with col2:

    st.markdown(
        f"""
        <div class="stat-card stat-red">
            <div class="stat-label">Critical</div>
            <div class="stat-value">{critiques}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


with col3:

    st.markdown(
        f"""
        <div class="stat-card stat-orange">
            <div class="stat-label">Tensions</div>
            <div class="stat-value">{tensions}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


with col4:

    st.markdown(
        f"""
        <div class="stat-card stat-yellow">
            <div class="stat-label">Monitoring</div>
            <div class="stat-value">{surveillance}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


st.write("")


# ============================================================
# CARTE
# ============================================================

st.markdown(
    '<div class="section-title">Global water conflict map</div>',
    unsafe_allow_html=True
)


m = folium.Map(
    location=[20, 10],
    zoom_start=2,
    tiles="CartoDB dark_matter",
    control_scale=True
)


couleurs = {
    "🔴": "#ef4444",
    "🟠": "#f59e0b",
    "🟡": "#eab308",
    "🟢": "#22c55e"
}


for _, row in df_filtre.iterrows():

    statut = str(
        row["statut"]
    )

    prefix = (
        statut[:1]
        if statut
        else "🔴"
    )

    couleur = couleurs.get(
        prefix,
        "#20c7ff"
    )


    popup_html = f"""
    <div style="
        width:300px;
        font-family:Arial,sans-serif;
        background:#0b1117;
        color:#ffffff;
        padding:10px;
    ">

        <h3 style="
            margin-bottom:10px;
            color:#20c7ff;
        ">
            {row['nom']}
        </h3>

        <b>Région</b><br>
        {row['region']}

        <br><br>

        <b>Pays</b><br>
        {row['pays_concernes']}

        <br><br>

        <b>Ressource</b><br>
        {row['ressource_en_eau']}

        <br><br>

        <b>Statut</b><br>
        {row['statut']}

    </div>
    """


    folium.CircleMarker(
        location=[
            row["latitude"],
            row["longitude"]
        ],
        radius=8,
        color=couleur,
        weight=2,
        fill=True,
        fill_color=couleur,
        fill_opacity=0.8,
        popup=folium.Popup(
            popup_html,
            max_width=350
        ),
        tooltip=row["nom"]
    ).add_to(m)


st_folium(
    m,
    width="stretch",
    height=600,
    returned_objects=[]
)


# ============================================================
# FICHE ZONE
# ============================================================

st.markdown(
    '<div class="section-title">Zone intelligence</div>',
    unsafe_allow_html=True
)


if len(df_filtre) > 0:

    zone_choisie = st.selectbox(
        "Sélectionner une zone",
        df_filtre["nom"].tolist()
    )

    z = df[
        df["nom"] == zone_choisie
    ].iloc[0]

    statut = str(
        z["statut"]
    )


    if statut.startswith("🔴"):

        status_class = "status-critical"
        status_text = "CRITICAL"

    elif statut.startswith("🟠"):

        status_class = "status-tension"
        status_text = "HIGH TENSION"

    elif statut.startswith("🟡"):

        status_class = "status-tension"
        status_text = "MONITORING"

    else:

        status_class = "status-tension"
        status_text = "COOPERATION"


    st.markdown(
        f"""
        <div class="zone-card">

            <div class="zone-title">
                {z['nom']}
            </div>

            <div class="zone-country">
                {z['region']} · {z['pays_concernes']}
            </div>

            <div class="{status_class}">
                {status_text}
            </div>

            <div class="info-label">
                WATER RESOURCE
            </div>

            <div class="info-value">
                {z['ressource_en_eau']}
            </div>

            <div class="info-label">
                TYPE
            </div>

            <div class="info-value">
                {z['type']}
            </div>

            <div class="info-label">
                KEY ISSUES
            </div>

            <div class="info-value">
                {z['enjeux']}
            </div>

            <div class="info-label">
                DESCRIPTION
            </div>

            <div class="info-value">
                {z['description']}
            </div>

            <div class="info-label">
                SOURCES
            </div>

            <div class="info-value">
                {z['sources']}
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

else:

    st.info(
        "Aucune zone ne correspond aux filtres."
    )


# ============================================================
# CHATBOT
# ============================================================

st.markdown(
    """
    <div class="chat-card">

        <div class="chat-title">
            ASK WATER CONFLICT
        </div>

        <div class="chat-description">
            Posez une question sur les tensions
            et conflits liés aux ressources en eau.
        </div>

    </div>
    """,
    unsafe_allow_html=True
)


question = st.text_input(
    "QUESTION",
    placeholder="Ex. Quels sont les enjeux autour du Nil ?",
    label_visibility="collapsed"
)


if st.button(
    "ANALYZE",
    use_container_width=True
) and question:

    with st.spinner(
        "Analyse..."
    ):

        reponse, zones_utilisees = repondre(
            question
        )

    st.markdown(
        reponse
    )

    if zones_utilisees is not None:

        noms = ", ".join(
            zones_utilisees["nom"].tolist()
        )

        st.caption(
            f"Données utilisées : {noms}"
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="water-footer">

        WATER CONFLICT ·
        Global Hydropolitical Intelligence Platform

        <br><br>

        Sources de données :
        Pacific Institute · UN-Water · UNESCO

    </div>
    """,
    unsafe_allow_html=True
)
