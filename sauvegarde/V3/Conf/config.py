import os

# Chargement des variables d'environnement
SEMANTIC_SCHOLAR_API_KEY = os.getenv('SEMANTIC_SCHOLAR_API_KEY', 'your-default-api-key')

# Paramètres généraux
NUM_RESULTS = 100
LANGUAGE_QUERIES = {
    'english': 'canine cognitive abilities',
    'french': 'capacités cognitives des chiens',
}


