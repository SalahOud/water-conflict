# 🌍 WATER CONFLICT

Application interactive d'exploration des zones de conflits, tensions et guerres liées aux ressources en eau dans le monde.

## 🎯 Fonctionnalités

- 🗺️ Carte mondiale interactive (Plotly)
- 📋 Fiche détaillée pour 20 zones hydriques majeures
- 🔎 Recherche tolérante aux fautes de frappe
- 💬 Assistant intelligent (RAG + LLM SmolLM2-1.7B)
- 📚 Sources affichées (Pacific Institute, ONU-Eau, UNESCO)

## 🧠 Architecture

Question utilisateur
       ↓
Détection d'intention
       ↓
RAG (retrieval sur base CSV)
       ↓
LLM (SmolLM2-1.7B-Instruct)
       ↓
Réponse cadrée sur la thématique eau

## 🛠️ Technologies

- Python, Pandas, Plotly, ipywidgets
- HuggingFace Transformers
- SmolLM2-1.7B-Instruct

## 📚 Sources des données

- Pacific Institute — Water Conflict Chronology
- ONU-Eau (SDG 6)
- FAO AQUASTAT
- UNESCO — World Water Development Reports

## 🚀 Utilisation

Ouvrir `WATER_CONFLICT.ipynb` dans Google Colab et exécuter les cellules dans l'ordre.

## 👤 Auteur

[Nom] — Master Calcul Parallèle & IA — [Année]
