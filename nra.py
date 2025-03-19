import pandas as pd
import folium
from pyproj import Transformer
from shapely.geometry import Polygon

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
    Retourne une liste de points [lat, lon] adaptée à Folium.
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

def main():
    # Lecture du CSV (adaptez le nom du fichier si nécessaire)
    df = pd.read_csv("input/Localisations NRA NRO.csv", sep=",")

    # Vérification des colonnes requises
    for col in ["the_geom", "osm_original_geom", "telecom-medium"]:
        if col not in df.columns:
            print(f"Colonne '{col}' introuvable.")
            return

    # Création du transformer de EPSG:3857 vers EPSG:4326
    transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    # Détermination d'un centre de carte en utilisant le premier point ou polygone valide
    center_lat, center_lon = 46.5, 2.5  # valeurs par défaut pour la France
    found_center = False
    for idx, row in df.iterrows():
        pt = parse_point(row["the_geom"])
        if pt:
            center_lat, center_lon = transform_point(pt[0], pt[1], transformer)
            found_center = True
            break
        poly = parse_polygon(row["osm_original_geom"])
        if poly:
            poly_latlon = transform_coords(poly, transformer)
            if poly_latlon:
                center_lat, center_lon = poly_latlon[0]
                found_center = True
                break

    m = folium.Map(location=[center_lat, center_lon], zoom_start=13 if found_center else 6)

    # Parcours de chaque ligne
    for idx, row in df.iterrows():
        # A) Affichage du point (the_geom) avec un symbole plus grand
        pt = parse_point(row["the_geom"])
        if pt:
            lat, lon = transform_point(pt[0], pt[1], transformer)
            folium.CircleMarker(
                location=[lat, lon],
                radius=8,  # rayon plus grand pour le point
                color="black",
                fill=True,
                fill_color="black",
                fill_opacity=0.8,
                popup=f"Point {idx}"
            ).add_to(m)

        # B) Affichage du polygone et calcul du centroïde pour obtenir ses coordonnées GPS
        poly_raw = parse_polygon(row["osm_original_geom"])
        if poly_raw:
            # Transformer le polygone pour affichage
            poly_latlon = transform_coords(poly_raw, transformer)
            if len(poly_latlon) > 2:
                techno = row.get("telecom-medium", "")
                color = get_polygon_color(techno)
                folium.Polygon(
                    locations=poly_latlon,
                    color=color,
                    fill=True,
                    fill_opacity=0.4,
                    popup=f"Polygone {idx} - {techno}"
                ).add_to(m)

                # Calcul du centroïde du polygone dans le système EPSG:3857
                try:
                    poly_shape = Polygon(poly_raw)
                    centroid = poly_shape.centroid
                    # Transformer le centroïde en coordonnées GPS (EPSG:4326)
                    cent_lat, cent_lon = transform_point(centroid.x, centroid.y, transformer)
                    # Ajouter un marqueur au centroïde avec un symbole plus grand
                    folium.CircleMarker(
                        location=[cent_lat, cent_lon],
                        radius=1,  # un point encore plus grand pour le centroïde
                        color="orange",
                        fill=True,
                        fill_color="orange",
                        fill_opacity=0.9,
                        popup=f"Centroïde {idx}: ({cent_lat:.5f}, {cent_lon:.5f})"
                    ).add_to(m)
                except Exception as e:
                    print(f"Erreur lors du calcul du centroïde pour le polygone {idx}: {e}")

    # Sauvegarder la carte dans un fichier HTML
    m.save("map_points_polygons.html")
    print("Carte sauvegardée dans 'map_points_polygons.html'.")

if __name__ == "__main__":
    main()
