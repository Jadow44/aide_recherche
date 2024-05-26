import os
import requests
import pandas as pd

def fetch_proxies():
    url = 'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all'
    response = requests.get(url)
    
    if response.status_code != 200:
        raise Exception(f"Failed to load proxies, status code: {response.status_code}")
    
    proxies = response.text.splitlines()
    
    proxy_list = []
    for proxy in proxies:
        ip, port = proxy.split(':')
        proxy_list.append({'Proxy': f"{ip}:{port}"})
    
    return proxy_list

def update_proxies_excel(file_path):
    print("Fetching proxies...")
    proxies = fetch_proxies()
    
    if not proxies:
        print("No proxies found. Exiting without updating the Excel file.")
        return
    
    print("Converting proxies to DataFrame...")
    df = pd.DataFrame(proxies)
    
    # Ensure the directory exists
    dir_name = os.path.dirname(file_path)
    if dir_name and not os.path.exists(dir_name):
        print(f"Creating directory: {dir_name}")
        os.makedirs(dir_name, exist_ok=True)
    else:
        print(f"Directory already exists or not needed: {dir_name}")
    
    print(f"Saving proxies to Excel file: {file_path}")
    df.to_excel(file_path, index=False)
    print("File saved successfully.")

if __name__ == "__main__":
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Define the path to the Excel file within the Proxies folder
    file_path = os.path.join(script_dir, '../Proxies/Adresse_Proxies.xlsx')
    update_proxies_excel(file_path)

