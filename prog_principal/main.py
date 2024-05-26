import sys
import os
import subprocess
import pandas as pd
from datetime import datetime
import time
import logging
from Conf.data_collection import semantic_scholar_search, select_proxy, read_proxies_from_excel, crossref_search, pubmed_search
from Conf.data_processing import clean_data, preprocess_data
import spacy
from queries_keywords import queries_keywords  # Import the queries and keywords
from Conf.key import SEMANTIC_SCHOLAR_API_KEY, CROSSREF_API_KEY, PUBMED_API_KEY  # Import API keys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROXIES_FILE = os.path.join(BASE_DIR, '../Proxies/Adresse_Proxies.xlsx')
CLEANED_FILE_DIRECTORY = os.path.join(BASE_DIR, '../bibliotheque_cyno/data/cleaned/')
CLEANED_FILE_PATH = os.path.join(CLEANED_FILE_DIRECTORY, 'cleaned_articles.xlsx')
PROCESSED_FILE_DIRECTORY = os.path.join(BASE_DIR, '../bibliotheque_cyno/data/processed/')
PROCESSED_FILE_PATH = os.path.join(PROCESSED_FILE_DIRECTORY, 'processed_articles.xlsx')

def update_proxies_if_needed(proxies_file: str) -> bool:
    if not os.path.exists(proxies_file):
        return True

    last_modified_time = datetime.fromtimestamp(os.path.getmtime(proxies_file))
    current_time = datetime.now()
    elapsed_time = (current_time - last_modified_time).total_seconds()
    return elapsed_time >= 3600  # 1 hour in seconds

def ensure_directory_exists(directory: str):
    if not os.path.exists(directory):
        os.makedirs(directory)
        logging.info(f"Created directory: {directory}")

def main():
    # Use the imported queries and keywords directly
    queries_keywords_df = pd.DataFrame(queries_keywords)

    if queries_keywords_df.empty:
        logging.error("No queries and keywords found. Exiting...")
        return

    # Vérifier si les proxies doivent être mis à jour
    if update_proxies_if_needed(PROXIES_FILE):
        logging.info("Updating proxies...")
        subprocess.run(['python', os.path.join(BASE_DIR, '../Proxies/main_proxies.py')])
        logging.info(f"Proxies updated at {datetime.now()}")

    # Lire les proxies depuis le fichier Excel
    try:
        proxies = read_proxies_from_excel(PROXIES_FILE)
        logging.info(f"Retrieved {len(proxies)} proxies from Excel")
    except Exception as e:
        logging.error(f"Error reading proxies from Excel: {e}")
        return

    if not proxies:
        logging.error("No proxies available after reading from Excel.")
        return

    # Test de sélection d'un proxy
    try:
        selected_proxy = select_proxy(proxies)
        logging.info(f"Selected proxy: {selected_proxy}")
    except Exception as e:
        logging.error(f"Error selecting proxy: {e}")
        return

    # Effectuer les recherches pour chaque query
    for index, row in queries_keywords_df.iterrows():
        query = row['query']
        keywords = row['keywords'].split(',')
        num_results = 10 # nb a modifier pour augementer les resultats
        articles = []

        logging.info(f"Searching for query: {query} with keywords: {keywords}")
        
        # Semantic Scholar Search
        if SEMANTIC_SCHOLAR_API_KEY != 'nul':
            try:
                articles = semantic_scholar_search(query, num_results, keywords)
                logging.info(f"Found {len(articles)} articles from Semantic Scholar")
            except Exception as e:
                logging.error(f"Error searching articles from Semantic Scholar: {e}")

        # Attempt to search on CrossRef
        if len(articles) == 0 and CROSSREF_API_KEY != 'nul':
            try:
                articles = crossref_search(query, num_results, keywords)
                logging.info(f"Found {len(articles)} articles from CrossRef")
            except Exception as e:
                logging.error(f"Error searching articles from CrossRef: {e}")

        # Attempt to search on PubMed
        if len(articles) == 0 and PUBMED_API_KEY != 'nul':
            try:
                articles = pubmed_search(query, num_results, keywords)
                logging.info(f"Found {len(articles)} articles from PubMed")
            except Exception as e:
                logging.error(f"Error searching articles from PubMed: {e}")

        if len(articles) == 0:
            logging.error("No articles found. Moving to next query...")
            continue

        # Convertir les résultats en DataFrame
        df = pd.DataFrame(articles)

        # Test de nettoyage des données
        df_cleaned = clean_data(df)
        logging.info(f"Cleaned data: {df_cleaned.head()}")
        ensure_directory_exists(CLEANED_FILE_DIRECTORY)
        df_cleaned.to_excel(CLEANED_FILE_PATH, index=False)
        logging.info(f"Cleaned data saved to {CLEANED_FILE_PATH}")

        # Vérifier et charger le modèle Spacy
        try:
            nlp = spacy.load('en_core_web_sm')
        except IOError:
            logging.info("Downloading Spacy model 'en_core_web_sm'...")
            subprocess.run(['python', '-m', 'spacy', 'download', 'en_core_web_sm'])
            nlp = spacy.load('en_core_web_sm')

        # Test de prétraitement des données
        df_processed = preprocess_data(df_cleaned, nlp)
        logging.info(f"Processed data: {df_processed.head()}")
        ensure_directory_exists(PROCESSED_FILE_DIRECTORY)
        df_processed.to_excel(PROCESSED_FILE_PATH, index=False)
        logging.info(f"Processed data saved to {PROCESSED_FILE_PATH}")

if __name__ == '__main__':
    main()
