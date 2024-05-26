import pandas as pd
import spacy

def clean_data(df):
    df.drop_duplicates(subset=['title'], inplace=True)
    df['summary'] = df['summary'].str.replace(r'\W+', ' ', regex=True)
    return df

def preprocess_text(text, nlp):
    if isinstance(text, str):
        doc = nlp(text.lower())
        tokens = [token.lemma_ for token in doc if not token.is_stop and token.is_alpha]
        preprocessed_text = ' '.join(tokens)
        print(f"Preprocessed text: {preprocessed_text[:100]}")  # Print the first 100 characters of preprocessed text
        return preprocessed_text
    else:
        return ''

def preprocess_data(df, nlp):
    print("Starting preprocessing...")  # Debugging line
    print("Initial number of rows:", len(df))  # Debugging line

    df['summary'] = df['summary'].fillna('')
    df['processed_summary'] = df['summary'].apply(lambda text: preprocess_text(text, nlp))
    print("Preprocessing done.")  # Debugging line
    print("Number of processed rows:", len(df))  # Debugging line
    return df
