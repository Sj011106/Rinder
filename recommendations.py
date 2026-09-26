from firebase_client import db

# The exact 12 neighborhood names your profile descriptions were generated with
KNOWN_AREAS = [
    "Clements / Sunset",
    "McLeod / Brookside",
    "Nashwaaksis North",
    "Main Street / North Devon",
    "Marysville",
    "South Devon / Barker's Point / Lower St. Mary's",
    "Southwood Park / Lincoln",
    "Skyline Acres",
    "Bishop Drive / Odell",
    "West Downtown & Plat / Sunshine Gardens",
    "East Downtown & Plat / UNB Campus",
    "Silverwood / Garden Creek",
]


def extract_preferred_area(description):
    """Checks a profile's description text for one of the 12 known Fredericton
    neighborhood names. Returns the matched name, or None if none is confidently found -
    callers should fall back to budget-only recommendations when this returns None."""
    if not description:
        return None
    for area in KNOWN_AREAS:
        if area.lower() in description.lower():
            return area
    return None

def get_recommended_listings(user_id, top_n=100):
    """Ranks ALL listings for a user - closest-budget + preferred-area matches first,
    then everything else sorted by closeness to their budget. Nothing is excluded,
    just ordered so the best fits appear first."""

    user_doc = db.collection("users").document(user_id).get()
    if not user_doc.exists:
        return {"error": f"No user found with id '{user_id}'"}
    user = user_doc.to_dict()

    budget = user.get("budget")
    if budget is None:
        return {"error": f"User '{user_id}' has no budget set"}

    preferred_area = extract_preferred_area(user.get("description"))

    all_listings = [doc.to_dict() for doc in db.collection("house").stream()]

    # Tag every listing (no filtering out) with area match + distance from budget
    for l in all_listings:
        l["_matches_area"] = bool(
            preferred_area and preferred_area.lower() in l.get("neighborhood", "").lower()
        )
        l["_rent_distance"] = abs(l.get("rent", 0) - budget)

    # Area-matching listings first (as a group), then everyone else -
    # each group internally sorted by closeness to the exact budget
    all_listings.sort(key=lambda l: (not l["_matches_area"], l["_rent_distance"]))

    trimmed = [
        {
            "id": l.get("id"),
            "title": l.get("title"),
            "neighborhood": l.get("neighborhood"),
            "rent": l.get("rent"),
            "bedrooms": l.get("bedrooms"),
            "property_type": l.get("property_type"),
            "matches_preferred_area": l["_matches_area"],
        }
        for l in all_listings[:top_n]
    ]

    return {
        "user_id": user_id,
        "budget": budget,
        "preferred_area": preferred_area,
        "count": len(trimmed),
        "recommended_listings": trimmed,
    }
# --- Quick test ---
if __name__ == "__main__":
    print("All ranked listings for U001:")
    result = get_recommended_listings("U001")
    print(f"Budget: {result['budget']}, preferred area: {result['preferred_area']}, total: {result['count']}")
    for l in result["recommended_listings"][:10]:
        print(l)
