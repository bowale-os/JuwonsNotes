import os
import json
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, storage

load_dotenv()

# --- Firebase Admin SDK Setup (Server-side) ---
def initialize_firebase_admin():
    if not firebase_admin._apps:
        service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
        if not service_account_json:
            raise ValueError("Missing FIREBASE_SERVICE_ACCOUNT_JSON in environment variables.")

        cred = credentials.Certificate(json.loads(service_account_json))
        app = firebase_admin.initialize_app(cred, {
            'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET')
        })
    else:
        app = firebase_admin.get_app()
    
    return {
        "app": app,
        "firestore": firestore.client(app),
        "storage": storage.bucket(os.getenv('FIREBASE_STORAGE_BUCKET'))
    }
