import pandas as pd
import requests
import time
import re
import sys
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm  # Import de tqdm pour la barre de progression

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URL de l'API Nominatim et User-Agent personnalisé
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
HEADERS = {"User-Agent": "Python-Geocoder-Optimized"}

# Création d'une session avec gestion des retries
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

def reverse_geocode(lat, lon, cache):
    """Effectue un géocodage inverse avec OpenStreetMap (Nominatim)."""
    coord_key = (lat, lon)
    if coord_key in cache:
        return cache[coord_key]

    params = {
        "format": "json",
        "lat": lat,
        "lon": lon,
        "zoom": 18,
        "addressdetails": 1
    }

    try:
        response = session.get(NOMINATIM_URL, headers=HEADERS, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if "display_name" in data:
            short_address = extract_short_address(data["display_name"])
            cache[coord_key] = short_address
            time.sleep(1)  # Respect des limitations de l'API
            return short_address
        else:
            logging.warning(f"Display name manquant pour les coordonnées ({lat}, {lon})")
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur API pour les coordonnées ({lat}, {lon}): {e}")
        return "Erreur API"

    return "Adresse non trouvée"

def extract_short_address(full_address):
    """
    Extrait 'Numéro Rue, CP Ville' à partir de l'adresse complète.
    Cette expression régulière peut être adaptée selon le format d'adresse attendu.
    """
    match = re.search(r"(\d+\s[\w\s\-']+),\s([\w\s\-']+),\s(\d{5})\s([\w\s\-']+)", full_address)
    if match:
        # Format : numéro, rue, code postal, ville
        return f"{match.group(1)}, {match.group(4)} {match.group(2)}"
    return full_address

def process_csv(input_csv, output_csv):
    """Charge un fichier CSV, ajoute les adresses postales courtes et enregistre le résultat."""
    try:
        df = pd.read_csv(input_csv, sep=";", dtype=str)
    except Exception as e:
        logging.error(f"Erreur lors de la lecture du fichier CSV: {e}")
        return

    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        raise ValueError("Les colonnes 'Latitude' et 'Longitude' sont manquantes dans le fichier CSV.")

    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    cache = {}  # Cache pour éviter les requêtes redondantes
    total_rows = len(df)

    # Utilisation de tqdm pour afficher la progression du traitement
    for i, row in tqdm(df.iterrows(), total=total_rows, desc="Traitement des lignes", unit="ligne"):
        lat = row["Latitude"]
        lon = row["Longitude"]
        if pd.notnull(lat) and pd.notnull(lon):
            df.at[i, "Adresse Postale"] = reverse_geocode(lat, lon, cache)
        else:
            df.at[i, "Adresse Postale"] = "Coordonnées invalides"

    try:
        df.to_csv(output_csv, index=False, sep=";")
        logging.info(f"Fichier enregistré : {output_csv}")
    except Exception as e:
        logging.error(f"Erreur lors de l'enregistrement du fichier CSV: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Géocodage inverse pour un fichier CSV avec Nominatim")
    parser.add_argument("input_csv", help="Chemin vers le fichier CSV d'entrée")
    parser.add_argument("output_csv", help="Chemin vers le fichier CSV de sortie")
    args = parser.parse_args()

    process_csv(args.input_csv, args.output_csv)
