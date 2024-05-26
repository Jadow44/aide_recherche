import sys
import os
import subprocess
import pandas as pd
from datetime import datetime
import time  # Ajout de l'importation
from Conf.data_collection import google_scholar_search, select_proxy, read_proxies_from_excel, semantic_scholar_search
from Conf.data_processing import clean_data, preprocess_data
import spacy

# Variables globales pour les chemins de fichiers
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROXIES_FILE = os.path.join(BASE_DIR, '../Proxies/Adresse_Proxies.xlsx')
CLEANED_FILE_DIRECTORY = os.path.join(BASE_DIR, '../bibliotheque_cyno/data/cleaned/')
CLEANED_FILE_PATH = os.path.join(CLEANED_FILE_DIRECTORY, 'cleaned_articles.xlsx')
PROCESSED_FILE_DIRECTORY = os.path.join(BASE_DIR, '../bibliotheque_cyno/data/processed/')
PROCESSED_FILE_PATH = os.path.join(PROCESSED_FILE_DIRECTORY, 'processed_articles.xlsx')

def update_proxies_if_needed(proxies_file):
    if not os.path.exists(proxies_file):
        return True

    last_modified_time = datetime.fromtimestamp(os.path.getmtime(proxies_file))
    current_time = datetime.now()
    elapsed_time = (current_time - last_modified_time).total_seconds()
    return elapsed_time >= 3600  # 1 hour in seconds

def ensure_directory_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

def main():
    # Vérifier si les proxies doivent être mis à jour
    if update_proxies_if_needed(PROXIES_FILE):
        print("Updating proxies...")
        subprocess.run(['python', os.path.join(BASE_DIR, '../Proxies/main_proxies.py')])
        print(f"Proxies updated at {datetime.now()}")

    # Lire les proxies depuis le fichier Excel
    try:
        proxies = read_proxies_from_excel(PROXIES_FILE)
        print(f"Retrieved {len(proxies)} proxies from Excel")
    except Exception as e:
        print(f"Error reading proxies from Excel: {e}")
        return

    if not proxies:
        print("No proxies available after reading from Excel.")
        return

    # Test de sélection d'un proxy
    try:
        selected_proxy = select_proxy(proxies)
        print(f"Selected proxy: {selected_proxy}")
    except Exception as e:
        print(f"Error selecting proxy: {e}")
        return

    # Test de recherche sur Google Scholar
    query = "canine cognitive abilities"
    num_results = 10
    articles = []
    try:
        articles = google_scholar_search(query, num_results, selected_proxy)
        print(f"Found {len(articles)} articles from Google Scholar")
    except Exception as e:
        print(f"Error searching articles: {e}")
        if "429" in str(e):
            print("Too many requests, changing proxy...")
            try:
                selected_proxy = select_proxy(proxies)
                articles = google_scholar_search(query, num_results, selected_proxy)
                print(f"Found {len(articles)} articles from Google Scholar")
            except Exception as e:
                print(f"Error searching articles with new proxy: {e}")

    if len(articles) == 0:
        # Recherche sur Semantic Scholar si Google Scholar ne retourne aucun résultat
        try:
            articles = semantic_scholar_search(query, num_results)
            print(f"Found {len(articles)} articles from Semantic Scholar")
        except Exception as e:
            print(f"Error searching articles: {e}")

    if len(articles) == 0:
        print("No articles found. Exiting...")
        return

    # Convertir les résultats en DataFrame
    df = pd.DataFrame(articles)

    # Test de nettoyage des données
    df_cleaned = clean_data(df)
    print(f"Cleaned data: {df_cleaned.head()}")
    # Assurer que le répertoire de sauvegarde existe
    ensure_directory_exists(CLEANED_FILE_DIRECTORY)
    # Sauvegarder les données nettoyées dans un fichier Excel
    df_cleaned.to_excel(CLEANED_FILE_PATH, index=False)
    print(f"Cleaned data saved to {CLEANED_FILE_PATH}")

    # Vérifier et charger le modèle Spacy
    try:
        nlp = spacy.load('en_core_web_sm')
    except IOError:
        print("Downloading Spacy model 'en_core_web_sm'...")
        subprocess.run(['python', '-m', 'spacy', 'download', 'en_core_web_sm'])
        nlp = spacy.load('en_core_web_sm')

    # Test de prétraitement des données
    df_processed = preprocess_data(df_cleaned, nlp)
    print(f"Processed data: {df_processed.head()}")
    # Assurer que le répertoire de sauvegarde existe
    ensure_directory_exists(PROCESSED_FILE_DIRECTORY)
    # Sauvegarder les données prétraitées dans un fichier Excel
    df_processed.to_excel(PROCESSED_FILE_PATH, index=False)
    print(f"Processed data saved to {PROCESSED_FILE_PATH}")

if __name__ == '__main__':
    main()
