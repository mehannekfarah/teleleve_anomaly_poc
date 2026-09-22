# TR Assist

TR Assist est une preuve de concept développée dans le cadre de mon mémoire de Mastère Intelligence Artificielle, Développement et Big Data.

Le projet étudie comment l'automatisation et l'exploitation des données peuvent contribuer au traitement des anomalies rencontrées dans les données de télérelève des compteurs d'eau.

## Objectif

TR Assist permet d'analyser une extraction de rejets métier et de proposer une aide au traitement selon plusieurs niveaux :

- application de règles métier pour les situations suffisamment déterministes ;
- orientation vers une analyse humaine lorsque le cas reste ambigu ;
- analyse approfondie de certains rejets à partir de données complémentaires ;
- export des résultats au format Excel.

Le prototype ne vise pas à remplacer l'expertise humaine, mais à automatiser les traitements répétitifs et à faciliter l'analyse des situations plus complexes.

## Fonctionnalités

- Import d'un fichier de données
- Analyse automatique des rejets
- Application de règles métier
- Identification des cas nécessitant une analyse humaine
- Analyse approfondie du cas « Compteur incompatible »
- Rapprochement avec des données complémentaires
- Visualisation des résultats
- Export des résultats au format Excel

## Technologies utilisées

- Python
- Streamlit
- pandas
- openpyxl

## Lancement de l'application

Installer les dépendances :

pip install -r requirements.txt

Puis lancer l'application :

python -m streamlit run app.py

## Structure du projet

Le projet contient le code nécessaire au fonctionnement du prototype TR Assist ainsi que les fichiers de configuration associés.

Les données internes utilisées dans le cadre de l'étude ne sont pas publiées dans ce dépôt.

## Contexte

Projet réalisé dans le cadre d'un mémoire de fin d'études en Mastère Intelligence Artificielle, Développement et Big Data.

Auteur : Farah MEHANNEK  
Année : 2026