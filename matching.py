from firebase_client import db

LEVEL_MAP = {"Low": 0, "Medium": 1, "High": 2}
SLEEP_MAP = {"early": 0, "normal": 1, "night": 2}


def get_user(user_id):
    """Fetches one user profile from Firestore."""
    doc = db.collection("users").document(user_id).get()
    return doc.to_dict() if doc.exists else None


def compatibility_score(user_a, user_b):
    """Returns a 0-100 compatibility score between two real profile dicts."""

    # 1. Budget closeness (25%)
    budget_diff = abs(user_a["budget"] - user_b["budget"])
    budget_score = max(0, 100 - budget_diff / 10)

    # 2. Noise level closeness (20%)
    noise_diff = abs(LEVEL_MAP[user_a["noise_level"]] - LEVEL_MAP[user_b["noise_level"]])
    noise_score = max(0, 100 - noise_diff * 50)

    # 3. Cleanliness closeness (15%)
    clean_diff = abs(LEVEL_MAP[user_a["cleanliness"]] - LEVEL_MAP[user_b["cleanliness"]])
    clean_score = max(0, 100 - clean_diff * 50)

    # 4. Sleep schedule closeness (15%)
    sleep_diff = abs(SLEEP_MAP[user_a["sleep_schedule"]] - SLEEP_MAP[user_b["sleep_schedule"]])
    sleep_score = max(0, 100 - sleep_diff * 50)

    # 5. Age closeness (10%)
    age_diff = abs(user_a["age"] - user_b["age"])
    age_score = max(0, 100 - age_diff * 8)

    # 6. Smoking match (10%)
    smoking_score = 100 if user_a["smoking"] == user_b["smoking"] else 0

    # 7. Drinking match (5%)
    drinking_score = 100 if user_a["drinking"] == user_b["drinking"] else 0

    total = (
        budget_score * 0.25
        + noise_score * 0.20
        + clean_score * 0.15
        + sleep_score * 0.15
        + age_score * 0.10
        + smoking_score * 0.10
        + drinking_score * 0.05
    )
    return round(total, 1)

def get_all_users():
    """Fetches every user profile from Firestore."""
    return [doc.to_dict() for doc in db.collection("users").stream()]


def get_suggested_roommates(user_id, top_n=100):
    """Given a user_id, scores them against every other user and returns the
    top_n best matches, sorted highest first - this is the actual response
    your friend's swipe screen will consume."""
    all_users = get_all_users()
    user = next((u for u in all_users if u["id"] == user_id), None)

    if not user:
        return {"error": f"No user found with id '{user_id}'"}

    candidates = [u for u in all_users if u["id"] != user_id]

    scored = []
    for candidate in candidates:
        score = compatibility_score(user, candidate)
        scored.append({
            "id": candidate["id"],
            "score": score,
            "name": candidate["name"],
            "age": candidate["age"],
            "program": candidate["program"],
            "picture": candidate.get("picture"),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"user_id": user_id, "suggested_roommates": scored[:top_n]}

if __name__ == "__main__":
    user_a = get_user("U001")
    user_b = get_user("U002")
    print(f"U001 ({user_a['name']}) vs U002 ({user_b['name']}): {compatibility_score(user_a, user_b)}")

    print("\nAll suggestions for U001:")
    result = get_suggested_roommates("U001")
    print(f"Total suggestions returned: {len(result['suggested_roommates'])}")
    for r in result["suggested_roommates"]:
        print(r)