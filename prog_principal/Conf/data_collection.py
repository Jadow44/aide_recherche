import random
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from Conf.key import SEMANTIC_SCHOLAR_API_KEY, CROSSREF_API_KEY, PUBMED_API_KEY

def select_proxy(proxies):
    if not proxies:
        raise ValueError("No proxies available.")
    return {'http': f'http://{random.choice(proxies)}'}

def read_proxies_from_excel(file_path):
    try:
        df = pd.read_excel(file_path, usecols=[0], skiprows=[0], header=None, names=['Proxy'])
        proxies = df['Proxy'].tolist()
        random.shuffle(proxies)  # Shuffle the list of proxies
        print(f"First 5 proxies from Excel file after shuffling: {proxies[:5]}")  # Debugging line
        return proxies
    except Exception as e:
        print(f"Error reading proxies from Excel: {e}")
        return []

def semantic_scholar_search(query, num_results, keywords):
    headers = {
        "x-api-key": SEMANTIC_SCHOLAR_API_KEY
    }
    results = []
    offset = 0
    while len(results) < num_results:
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&offset={offset}&limit=10&fields=title,url,abstract"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data from Semantic Scholar: {response.status_code}")
        data = response.json()
        for article in data.get('data', []):
            title = article.get('title', 'No title')
            summary = article.get('abstract', 'No summary')
            results.append({
                'title': title,
                'link': article.get('url', 'No link'),
                'summary': summary
            })
        if not data.get('data', []):
            break
        offset += 10
    return results[:num_results]

def crossref_search(query, num_results, keywords):
    if CROSSREF_API_KEY == 'nul':
        print("CrossRef API key is not available. Skipping CrossRef search.")
        return []

    url = f"https://api.crossref.org/works?query={query}&rows={num_results}"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Error fetching data from CrossRef: {response.status_code}")
    data = response.json()
    results = []
    for item in data['message']['items']:
        title = item.get('title', ['No title'])[0]
        link = item.get('URL', 'No link')
        summary = item.get('abstract', 'No summary')
        results.append({
            'title': title,
            'link': link,
            'summary': summary
        })
    return results

def pubmed_search(query, num_results, keywords):
    if PUBMED_API_KEY == 'nul':
        print("PubMed API key is not available. Skipping PubMed search.")
        return []

    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={query}&retmax={num_results}&retmode=json"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Error fetching data from PubMed: {response.status_code}")
    data = response.json()
    id_list = data.get('esearchresult', {}).get('idlist', [])
    results = []
    for pmid in id_list:
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
        response = requests.get(url)
        if response.status_code != 200:
            continue
        summary_data = response.json()
        docsum = summary_data.get('result', {}).get(pmid, {})
        title = docsum.get('title', 'No title')
        link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        summary = docsum.get('summary', 'No summary')
        results.append({
            'title': title,
            'link': link,
            'summary': summary
        })
    return results
