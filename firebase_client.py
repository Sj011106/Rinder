import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Loads the values from your .env file (GROQ_API_KEY, FIREBASE_SERVICE_ACCOUNT_PATH)
load_dotenv()

# Points to your downloaded Firebase key
cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "./serviceAccountKey.json")
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)

# This is your handle to Firestore - you'll use this "db" object everywhere later
db = firestore.client()

# --- Quick test: only runs when you execute this file directly ---
if __name__ == "__main__":
    doc = db.collection("users").document("U001").get()
    if doc.exists:
        print("Connected! U001 looks like:")
        print(doc.to_dict())
    else:
        print("Connected, but U001 wasn't found - check your collection/document names.")