from firebase_client import db
import requests
from collections import Counter


def get_listing_count(area_keyword=None):
    """Counts how many listings exist, optionally filtered to one area/neighborhood."""
    docs = [doc.to_dict() for doc in db.collection("house").stream()]

    if area_keyword:
        docs = [d for d in docs if area_keyword.lower() in d.get("neighborhood", "").lower()]

    return {"count": len(docs), "area": area_keyword or "all areas"}


def get_available_areas():
    """Returns the distinct neighborhoods that currently have at least one listing."""
    docs = [doc.to_dict() for doc in db.collection("house").stream()]
    neighborhoods = sorted(set(d.get("neighborhood", "") for d in docs if d.get("neighborhood")))
    return {"neighborhoods": neighborhoods}


def get_listings(area_keyword=None, min_price=None, max_price=None, property_type=None):
    """Returns raw listing records matching the given filters, for browsing or answering
    detail questions. For averages/min/max/extremes, use get_stats instead - it's smaller
    and guaranteed accurate across ALL matches, not just a sample."""
    docs = [doc.to_dict() for doc in db.collection("house").stream()]

    if area_keyword:
        docs = [d for d in docs if area_keyword.lower() in d.get("neighborhood", "").lower()]
    if min_price is not None:
        docs = [d for d in docs if d.get("rent", 0) >= min_price]
    if max_price is not None:
        docs = [d for d in docs if d.get("rent", 0) <= max_price]
    if property_type:
        docs = [d for d in docs if property_type.lower() in d.get("property_type", "").lower()]

    trimmed = [
        {
            "title": d.get("title"),
            "neighborhood": d.get("neighborhood"),
            "rent": d.get("rent"),
            "bedrooms": d.get("bedrooms"),
            "bathrooms": d.get("bathrooms"),
            "available_rooms": d.get("available_rooms"),
            "furnished": d.get("furnished"),
            "property_type": d.get("property_type"),
            "utilities_included": d.get("utilities_included"),
            "bus_stop": (
                f"{d['closest_bus_stop']['name']} ({d['closest_bus_stop']['walk_minutes']} min walk)"
                if d.get("closest_bus_stop") else None
            ),
        }
        for d in docs
    ]

    return {"count": len(trimmed), "listings": trimmed[:20]}  # capped at 20 to stay well under token limits


NUMERIC_FIELDS = ["rent", "bedrooms", "bathrooms", "available_rooms"]


def get_stats(field, area_keyword=None, min_price=None, max_price=None, property_type=None):
    """Computes real min/max/average for a numeric field across listings matching the
    given filters, plus which listing(s) hit the min and max. Works correctly no matter
    how many listings match, since only the computed summary is returned - not raw records."""
    if field not in NUMERIC_FIELDS:
        return {"error": f"'{field}' isn't a supported field. Supported: {NUMERIC_FIELDS}"}

    docs = [doc.to_dict() for doc in db.collection("house").stream()]

    if area_keyword:
        docs = [d for d in docs if area_keyword.lower() in d.get("neighborhood", "").lower()]
    if min_price is not None:
        docs = [d for d in docs if d.get("rent", 0) >= min_price]
    if max_price is not None:
        docs = [d for d in docs if d.get("rent", 0) <= max_price]
    if property_type:
        docs = [d for d in docs if property_type.lower() in d.get("property_type", "").lower()]

    docs_with_field = [d for d in docs if field in d]
    if not docs_with_field:
        return {"field": field, "count": 0, "min": None, "max": None, "avg": None}

    values = [d[field] for d in docs_with_field]
    min_val, max_val = min(values), max(values)

    min_listing = next(d for d in docs_with_field if d[field] == min_val)
    max_listing = next(d for d in docs_with_field if d[field] == max_val)

    return {
        "field": field,
        "count": len(values),
        "min": min_val,
        "max": max_val,
        "avg": round(sum(values) / len(values), 2),
        "listing_with_min": {"title": min_listing.get("title"), "neighborhood": min_listing.get("neighborhood"), field: min_val},
        "listing_with_max": {"title": max_listing.get("title"), "neighborhood": max_listing.get("neighborhood"), field: max_val},
    }


CATEGORICAL_FIELDS = ["furnished", "utilities_included", "property_type"]


def get_field_counts(field, area_keyword=None, min_price=None, max_price=None, property_type=None):
    """Counts how many listings fall into each value of a true/false or category field
    (furnished, utilities_included, property_type), with real percentages - computed in
    Python, not estimated by the AI from a sample."""
    if field not in CATEGORICAL_FIELDS:
        return {"error": f"'{field}' isn't supported. Supported: {CATEGORICAL_FIELDS}"}

    docs = [doc.to_dict() for doc in db.collection("house").stream()]

    if area_keyword:
        docs = [d for d in docs if area_keyword.lower() in d.get("neighborhood", "").lower()]
    if min_price is not None:
        docs = [d for d in docs if d.get("rent", 0) >= min_price]
    if max_price is not None:
        docs = [d for d in docs if d.get("rent", 0) <= max_price]
    if property_type:
        docs = [d for d in docs if property_type.lower() in d.get("property_type", "").lower()]

    values = [d[field] for d in docs if field in d]
    total = len(values)
    if total == 0:
        return {"field": field, "total": 0, "counts": {}}

    counts = Counter(values)
    return {
        "field": field,
        "total": total,
        "counts": dict(counts),
        "percentages": {str(k): round((v / total) * 100, 1) for k, v in counts.items()},
    }


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
ARCGIS_WARD_QUERY_URL = "https://services2.arcgis.com/iLWAxhpxafhOza2U/ArcGIS/rest/services/Wards/FeatureServer/80/query"

# Nominatim's usage policy requires a descriptive User-Agent identifying the app
HEADERS = {"User-Agent": "RinderHackathonApp/1.0 (student project, UNB)"}


def geocode_place(place_name):
    """Turns a place name into (lat, lon, matched_name) using OpenStreetMap's free Nominatim geocoder."""
    params = {"q": f"{place_name}, Fredericton, New Brunswick, Canada", "format": "json", "limit": 1}
    resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
    results = resp.json()
    if not results:
        return None
    matched_name = results[0].get("display_name", "unknown")
    return float(results[0]["lat"]), float(results[0]["lon"]), matched_name


def ward_num_to_neighborhood(ward_num):
    """Matches a ward number to the exact neighborhood string already used in Firestore."""
    areas = get_available_areas()["neighborhoods"]
    for area in areas:
        prefix = area.split(" - ")[0].strip()  # e.g. "11 - East Downtown..." -> "11"
        if prefix == str(ward_num):
            return area
    return None


def find_ward_for_place(place_name):
    """Given a place name or address, finds which Fredericton neighborhood/ward it falls in."""
    coords = geocode_place(place_name)
    if not coords:
        return {"error": f"Couldn't find coordinates for '{place_name}'. Try a more complete or formal version of this place's name."}

    lat, lon, matched_name = coords
    params = {
        "f": "json",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "Ward_Num,WardNames",
        "returnGeometry": "false",
    }
    resp = requests.get(ARCGIS_WARD_QUERY_URL, params=params, timeout=10)
    data = resp.json()

    features = data.get("features", [])
    if not features:
        return {"error": f"'{place_name}' doesn't seem to fall inside any Fredericton ward."}

    ward_num = features[0]["attributes"]["Ward_Num"]
    neighborhood = ward_num_to_neighborhood(ward_num)

    return {
        "requested_place": place_name,
        "matched_to": matched_name,
        "ward_number": ward_num,
        "neighborhood": neighborhood or features[0]["attributes"]["WardNames"],
    }


AVAILABLE_FUNCTIONS = {
    "get_listing_count": get_listing_count,
    "get_available_areas": get_available_areas,
    "find_ward_for_place": find_ward_for_place,
    "get_listings": get_listings,
    "get_stats": get_stats,
    "get_field_counts": get_field_counts,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_listing_count",
            "description": "Get the number of housing listings available, optionally filtered to a specific neighborhood",
            "parameters": {
                "type": "object",
                "properties": {
                    "area_keyword": {"type": "string", "description": "e.g. 'Nashwaaksis', 'Downtown' - leave empty for all areas"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_areas",
            "description": "Get the list of distinct neighborhoods that currently have listings",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_ward_for_place",
            "description": "Find which Fredericton neighborhood/ward a specific place, landmark, or address falls in",
            "parameters": {
                "type": "object",
                "properties": {
                    "place_name": {"type": "string", "description": "e.g. 'the hospital', '700 Priestman Street', 'UNB campus'"}
                },
                "required": ["place_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_listings",
            "description": "Get raw listing records (rent, bedrooms, bathrooms, furnished, property type, bus stop, utilities, etc.), optionally filtered by area, price range, or property type. Use this for browsing listings or answering detail questions - NOT for averages/min/max, use get_stats for those instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area_keyword": {"type": "string"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                    "property_type": {"type": "string", "description": "e.g. 'Room in Shared House', 'Townhouse'"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "Compute real min/max/average for a numeric field (rent, bedrooms, bathrooms, available_rooms) across listings, optionally filtered by area/price/property type. Also returns which listing has the min and max. Use this for any question about averages, extremes ('most/least X'), or ranges - it's guaranteed accurate, unlike estimating from raw listings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": ["rent", "bedrooms", "bathrooms", "available_rooms"]},
                    "area_keyword": {"type": "string"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                    "property_type": {"type": "string"},
                },
                "required": ["field"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_field_counts",
            "description": "Get real counts and percentages for a true/false or category field (furnished, utilities_included, property_type) across ALL matching listings - guaranteed accurate, use instead of counting from get_listings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": ["furnished", "utilities_included", "property_type"]},
                    "area_keyword": {"type": "string"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                },
                "required": ["field"],
            },
        },
    },
]


# --- Quick test ---
if __name__ == "__main__":
    print(get_listing_count())
    print(get_available_areas())
    print(get_listings(max_price=800))
    print(get_stats("bathrooms"))
    print(get_stats("bedrooms"))
    print(get_field_counts("furnished"))
    print(find_ward_for_place("Dr. Everett Chalmers Hospital"))