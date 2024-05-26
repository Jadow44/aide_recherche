import random
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import logging
from Conf.key import SEMANTIC_SCHOLAR_API_KEY

def select_proxy(proxies: list) -> dict:
    if not proxies:
        raise ValueError("No proxies available.")
    return {'http': f'http://{random.choice(proxies)}'}

def google_scholar_search(query: str, num_results: int, proxies: dict, keywords: list) -> list:
    results = []
    num_pages = num_results // 10 + (num_results % 10 > 0)
    total_attempts = 0
    max_attempts = 3  # Maximum attempts across all pages

    for page in range(num_pages):
        if total_attempts >= max_attempts:
            logging.warning("Too many failed attempts, stopping Google Scholar search.")
            break

        start = page * 10
        url = f"https://scholar.google.com/scholar?q={query}&start={start}"
        for attempt in range(3):  # Try up to 3 times per page
            try:
                logging.info(f"Fetching URL: {url} with proxy {proxies}")
                response = requests.get(url, proxies=proxies, timeout=10)
                response.raise_for_status()  # Raise HTTPError for bad responses
                time.sleep(15)  # Increase delay between successful requests to avoid rate limiting
                break
            except requests.exceptions.HTTPError as http_err:
                logging.error(f"HTTP error occurred: {http_err}")
                if response.status_code == 429:  # Too many requests
                    logging.warning("Too many requests, changing proxy...")
                    proxies = select_proxy(read_proxies_from_excel('Proxies/Adresse_Proxies.xlsx'))
                    time.sleep(60)  # Increase exponential backoff
                    continue
            except Exception as err:
                logging.error(f"Other error occurred: {err}")
                time.sleep(2 ** (attempt + 1))  # Exponential backoff
                continue
        else:
            logging.error("Failed to fetch URL after 3 attempts")
            total_attempts += 1
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.find_all('div', class_='gs_ri')
        
        for article in articles:
            title = article.find('h3').text if article.find('h3') else 'No title'
            link = article.find('a')['href'] if article.find('a') else 'No link'
            summary = article.find('div', class_='gs_rs').text if article.find('div', class_='gs_rs') else 'No summary'
            if any(keyword in title.lower() for keyword in keywords):
                results.append({'title': title, 'link': link, 'summary': summary})
        
        logging.info(f"Found {len(articles)} articles on page {page + 1}")

        if len(articles) == 0:
            break

    return results

def read_proxies_from_excel(file_path: str) -> list:
    try:
        df = pd.read_excel(file_path, usecols=[0], skiprows=[0], header=None, names=['Proxy'])
        proxies = df['Proxy'].tolist()
        random.shuffle(proxies)  # Shuffle the list of proxies
        logging.info(f"First 5 proxies from Excel file after shuffling: {proxies[:5]}")
        return proxies
    except Exception as e:
        logging.error(f"Error reading proxies from Excel: {e}")
        return []

def semantic_scholar_search(query: str, num_results: int, keywords: list) -> list:
    headers = {
        "x-api-key": SEMANTIC_SCHOLAR_API_KEY
    }
    results = []
    offset = 0
    while len(results) < num_results:
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&offset={offset}&limit=10&fields=title,url,abstract"
        logging.info(f"Fetching URL: {url}")
        response = requests.get(url, headers=headers)
        if response.status_code == 403:  # Forbidden
            logging.error(f"Failed to fetch URL: {url} with status code: {response.status_code}")
            break
        data = response.json()
        for article in data.get('data', []):
            title = article.get('title', 'No title')
            summary = article.get('abstract', 'No summary')
            if any(keyword in title.lower() for keyword in keywords):
                results.append({
                    'title': title,
                    'link': article.get('url', 'No link'),
                    'summary': summary
                })
        logging.info(f"Found {len(data.get('data', []))} articles")
        if not data.get('data', []):
            break
        offset += 10
    return results[:num_results]