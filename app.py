import pandas as pd
import folium
from pyproj import Transformer
from shapely.geometry import Polygon
import math

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calcule la distance (en km) entre deux points GPS (en degrés) en utilisant la formule haversine.
    """
    R = 6371  # Rayon de la Terre en km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# --- Fonctions pour le CSV NRA (points et polygones) ---

def parse_point(wkt_string):
    """
    Extrait (x, y) depuis un WKT de type "POINT (x y)".
    Retourne None si le format est invalide.
    """
    if not isinstance(wkt_string, str):
        return None
    wkt_string = wkt_string.strip()
    if wkt_string.startswith("POINT(") and wkt_string.endswith(")"):
        coords_str = wkt_string[len("POINT("):-1].strip()
        parts = coords_str.split()
        if len(parts) == 2:
            try:
                x = float(parts[0].strip("()"))
                y = float(parts[1].strip("()"))
                return (x, y)
            except ValueError:
                return None
    return None

def parse_polygon(wkt_string):
    """
    Extrait la liste des paires (x, y) depuis un WKT de type
    "SRID=3857;POLYGON((x1 y1,x2 y2,...))" ou "POLYGON((...))".
    Retourne une liste vide si le format est invalide.
    """
    if not isinstance(wkt_string, str):
        return []
    wkt_string = wkt_string.strip()
    if ";" in wkt_string:
        parts = wkt_string.split(";", 1)
        geom_str = parts[1].strip()
    else:
        geom_str = wkt_string

    if geom_str.startswith("POLYGON((") and geom_str.endswith("))"):
        coords_str = geom_str[len("POLYGON(("):-2]
    else:
        return []

    pairs = coords_str.split(",")
    coords = []
    for pair in pairs:
        subparts = pair.strip().split()
        if len(subparts) == 2:
            x_str = subparts[0].strip("()")
            y_str = subparts[1].strip("()")
            try:
                x = float(x_str)
                y = float(y_str)
                coords.append((x, y))
            except ValueError:
                print(f"Erreur lors de la conversion en float pour {subparts}")
    return coords

def transform_coords(coords, transformer):
    """
    Transforme une liste de paires (x, y) depuis EPSG:3857 vers EPSG:4326.
    Retourne une liste de points [lat, lon] (ordre attendu par Folium).
    """
    transformed = []
    for (x, y) in coords:
        lon, lat = transformer.transform(x, y)
        transformed.append([lat, lon])
    return transformed

def transform_point(x, y, transformer):
    """
    Transforme un point (x, y) depuis EPSG:3857 vers EPSG:4326.
    Retourne (lat, lon).
    """
    lon, lat = transformer.transform(x, y)
    return (lat, lon)

def get_polygon_color(tech):
    """
    Retourne une couleur en fonction de la valeur dans telecom-medium.
      - "copper" -> "red"
      - "fibre"  -> "green"
      - sinon -> "blue"
    """
    if not isinstance(tech, str):
        return "blue"
    tech = tech.strip().lower()
    if tech == "copper":
        return "red"
    elif tech == "fibre":
        return "green"
    else:
        return "blue"

# --- Fonction pour traiter les points GPS fiab et exporter les résultats dans un CSV ---

def process_and_add_gps_points(map_object, gps_csv, nra_points):
    """
    Lit le CSV contenant des coordonnées GPS (colonnes "Latitude" et "Longitude")
    avec le délimiteur ";".
    Pour chaque point, recherche le NRA le plus proche (liste de (lat, lon, fid)),
    ajoute un marker sur la carte et stocke les résultats dans une DataFrame.
    La colonne "Libelle" du fichier fiab est ajoutée dans le CSV de résultat (mais n'est pas affichée sur la carte).
    """
    results = []
    try:
        df_gps = pd.read_csv(gps_csv, sep=";")
    except Exception as e:
        print(f"Erreur lors de la lecture de {gps_csv}: {e}")
        return map_object, pd.DataFrame()

    if "Latitude" not in df_gps.columns or "Longitude" not in df_gps.columns:
        print("Les colonnes 'Latitude' et/ou 'Longitude' sont introuvables dans le fichier GPS.")
        return map_object, pd.DataFrame()

    for idx, row in df_gps.iterrows():
        try:
            lat = float(row["Latitude"])
            lon = float(row["Longitude"])
        except Exception as e:
            print(f"Erreur de conversion pour la ligne {idx} dans {gps_csv}: {e}")
            continue
        if math.isnan(lat) or math.isnan(lon):
            print(f"Ligne {idx} ignorée car Latitude ou Longitude est NaN.")
            continue

        # Recherche du NRA le plus proche parmi nra_points (utilisation des centroïdes)
        min_distance = None
        closest_nra = None
        for (nra_lat, nra_lon, nra_fid) in nra_points:
            d = haversine_distance(lat, lon, nra_lat, nra_lon)
            if min_distance is None or d < min_distance:
                min_distance = d
                closest_nra = (nra_lat, nra_lon, nra_fid)

        popup_text = f"GPS {idx}\nNRA: {closest_nra[2]} ({min_distance:.2f} km)"
        # On n'affiche plus le Libelle sur la carte, uniquement dans le CSV.
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color="purple",
            fill=True,
            fill_color="purple",
            fill_opacity=0.8,
            popup=popup_text
        ).add_to(map_object)

        # Récupérer le Libelle si présent
        libelle = row.get("Libelle", "")
        if pd.isna(libelle):
            libelle = ""

        results.append({
            "fiab_index": idx,
            "fiab_lat": lat,
            "fiab_lon": lon,
            "Libelle": libelle,
            "nra_fid": closest_nra[2],
            "nra_lat": closest_nra[0],
            "nra_lon": closest_nra[1],
            "distance_km": min_distance
        })

    df_results = pd.DataFrame(results)
    return map_object, df_results

# --- Fonction principale ---

def main():
    # Lecture du CSV des données NRA (points/polygones)
    df = pd.read_csv("input/Localisations NRA NRO.csv", sep=",")

    # Vérification des colonnes requises dans le CSV NRA
    for col in ["FID", "the_geom", "osm_original_geom", "telecom-medium"]:
        if col not in df.columns:
            print(f"Colonne '{col}' introuvable dans le CSV NRA.")
            return

    # Création du transformer de EPSG:3857 vers EPSG:4326
    transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    # Construction de la liste des positions NRA en utilisant le centroïde des polygones
    nra_points = []
    for idx, row in df.iterrows():
        fid = row["FID"]
        poly_raw = parse_polygon(row["osm_original_geom"])
        if poly_raw:
            try:
                poly_shape = Polygon(poly_raw)
                centroid = poly_shape.centroid
                cent_lat, cent_lon = transform_point(centroid.x, centroid.y, transformer)
                nra_points.append((cent_lat, cent_lon, fid))
            except Exception as e:
                print(f"Erreur pour NRA {fid} lors du calcul du centroïde: {e}")
                pt = parse_point(row["the_geom"])
                if pt:
                    lat, lon = transform_point(pt[0], pt[1], transformer)
                    nra_points.append((lat, lon, fid))
        else:
            pt = parse_point(row["the_geom"])
            if pt:
                lat, lon = transform_point(pt[0], pt[1], transformer)
                nra_points.append((lat, lon, fid))
    if not nra_points:
        print("Aucun point NRA valide trouvé.")
        return

    # Centre la carte sur le premier NRA (centroïde)
    center_lat, center_lon = nra_points[0][0], nra_points[0][1]
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

    # Affichage des NRA : points, polygones et centroïdes
    for idx, row in df.iterrows():
        fid = row["FID"]
        # A) Affichage du point (the_geom)
        pt = parse_point(row["the_geom"])
        if pt:
            lat, lon = transform_point(pt[0], pt[1], transformer)
            folium.CircleMarker(
                location=[lat, lon],
                radius=8,
                color="black",
                fill=True,
                fill_color="black",
                fill_opacity=0.8,
                popup=f"NRA Point {fid}"
            ).add_to(m)
        # B) Affichage du polygone et de son centroïde
        poly_raw = parse_polygon(row["osm_original_geom"])
        if poly_raw:
            poly_latlon = transform_coords(poly_raw, transformer)
            if len(poly_latlon) > 2:
                techno = row.get("telecom-medium", "")
                color = get_polygon_color(techno)
                folium.Polygon(
                    locations=poly_latlon,
                    color=color,
                    fill=True,
                    fill_opacity=0.4,
                    popup=f"NRA Polygone {fid} - {techno}"
                ).add_to(m)
                try:
                    poly_shape = Polygon(poly_raw)
                    centroid = poly_shape.centroid
                    cent_lat, cent_lon = transform_point(centroid.x, centroid.y, transformer)
                    folium.CircleMarker(
                        location=[cent_lat, cent_lon],
                        radius=10,
                        color="orange",
                        fill=True,
                        fill_color="orange",
                        fill_opacity=0.9,
                        popup=f"Centroïde NRA {fid}: ({cent_lat:.5f}, {cent_lon:.5f})"
                    ).add_to(m)
                except Exception as e:
                    print(f"Erreur lors du calcul du centroïde pour NRA {fid}: {e}")

    # --- Ajout et traitement des points GPS du fichier fiab ---
    m, df_results = process_and_add_gps_points(m, "input/fiab.csv", nra_points)

    # Export du résultat dans un CSV
    output_csv = "output_nearest_nra.csv"
    df_results.to_csv(output_csv, index=False)
    print(f"Fichier CSV exporté : {output_csv}")

    # Sauvegarde de la carte dans un fichier HTML
    m.save("map_all.html")
    print("Carte sauvegardée dans 'map_all.html'.")

if __name__ == "__main__":
    main()
