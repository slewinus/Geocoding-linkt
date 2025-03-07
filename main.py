import pandas as pd
import requests
import time
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URLs et User-Agent
DATA_GOUV_URL = "https://api-adresse.data.gouv.fr/reverse"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
HEADERS = {"User-Agent": "Python-Geocoder-Optimized"}

# Création d'une session partagée avec stratégie de réessai
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

def reverse_geocode_data_gouv(lat, lon):
    """
    Interroge l'API adresse.data.gouv.fr pour obtenir une adresse sous le format
    "Numéro Rue, Code Postal Ville". Retourne None si aucun résultat satisfaisant n'est trouvé.
    """
    params = {
        "lat": lat,
        "lon": lon
    }
    try:
        response = session.get(DATA_GOUV_URL, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        features = data.get("features")
        if features:
            props = features[0].get("properties", {})
            housenumber = props.get("housenumber", "").strip()
            street = props.get("street", "").strip()
            postcode = props.get("postcode", "").strip()
            city = props.get("city", "").strip()
            if street and postcode and city:
                if housenumber:
                    return f"{housenumber} {street}, {postcode} {city}"
                else:
                    return f"{street}, {postcode} {city}"
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur avec data.gouv pour ({lat}, {lon}) : {e}")
        return None

def reverse_geocode_osm(lat, lon):
    """
    Interroge l'API Nominatim d'OpenStreetMap pour obtenir une adresse sous le format
    "Numéro Rue, Code Postal Ville". Retourne None si aucune adresse n'est trouvée.
    """
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
        addr = data.get("address", {})
        housenumber = addr.get("house_number", "").strip()
        road = addr.get("road", "").strip()
        postcode = addr.get("postcode", "").strip()
        city = addr.get("city", addr.get("town", addr.get("village", ""))).strip()
        if road and postcode and city:
            if housenumber and housenumber != postcode:
                return f"{housenumber} {road}, {postcode} {city}"
            else:
                return f"{road}, {postcode} {city}"
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur avec Nominatim pour ({lat}, {lon}) : {e}")
        return None

def reverse_geocode(lat, lon, cache):
    """
    Tente d'obtenir une adresse via data.gouv.fr. Si aucun résultat satisfaisant n'est trouvé,
    utilise Nominatim comme solution de secours.
    """
    coord_key = (lat, lon)
    if coord_key in cache:
        return cache[coord_key]

    # Premier essai avec data.gouv.fr
    address = reverse_geocode_data_gouv(lat, lon)
    if address:
        logging.info(f"Adresse trouvée via data.gouv pour ({lat}, {lon}) : {address}")
        # Petit délai pour respecter les limitations de data.gouv (environ 0.2 s)
        time.sleep(0.2)
    else:
        logging.info(f"data.gouv n'a rien trouvé pour ({lat}, {lon}). Passage à Nominatim.")
        address = reverse_geocode_osm(lat, lon)
        if address:
            logging.info(f"Adresse trouvée via Nominatim pour ({lat}, {lon}) : {address}")
            # Respect strict des limitations de Nominatim (1 seconde entre les requêtes)
            time.sleep(1)
        else:
            address = "Adresse non trouvée"
    cache[coord_key] = address
    return address

def process_csv(input_csv, output_csv):
    """
    Charge le CSV, ajoute une colonne "Adresse Postale" obtenue par géocodage inverse,
    et enregistre le résultat.
    """
    try:
        df = pd.read_csv(input_csv, sep=";", dtype=str)
    except Exception as e:
        logging.error(f"Erreur lors de la lecture du CSV: {e}")
        return

    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        raise ValueError("Les colonnes 'Latitude' et 'Longitude' sont requises dans le CSV.")

    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    cache = {}
    total_rows = len(df)

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
        logging.error(f"Erreur lors de l'enregistrement du CSV: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Géocodage inverse pour un CSV : tente data.gouv.fr, puis Nominatim en fallback."
    )
    parser.add_argument("input_csv", help="Chemin vers le CSV d'entrée")
    parser.add_argument("output_csv", help="Chemin vers le CSV de sortie")
    args = parser.parse_args()

    process_csv(args.input_csv, args.output_csv)
