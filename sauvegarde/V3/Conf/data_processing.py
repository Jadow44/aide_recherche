import pandas as pd
import spacy
import logging

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df.drop_duplicates(subset=['title'], inplace=True)
    df['summary'] = df['summary'].str.replace(r'\W+', ' ', regex=True)
    return df

def preprocess_text(text: str, nlp) -> str:
    if isinstance(text, str):
        doc = nlp(text.lower())
        tokens = [token.lemma_ for token in doc if not token.is_stop and token.is_alpha]
        preprocessed_text = ' '.join(tokens)
        logging.debug(f"Preprocessed text: {preprocessed_text[:100]}")  # Print the first 100 characters of preprocessed text
        return preprocessed_text
    else:
        return ''

def preprocess_data(df: pd.DataFrame, nlp) -> pd.DataFrame:
    logging.info("Starting preprocessing...")
    logging.info(f"Initial number of rows: {len(df)}")

    df['summary'] = df['summary'].fillna('')
    df['processed_summary'] = df['summary'].apply(lambda text: preprocess_text(text, nlp))
    logging.info("Preprocessing done.")
    logging.info(f"Number of processed rows: {len(df)}")
    return df
