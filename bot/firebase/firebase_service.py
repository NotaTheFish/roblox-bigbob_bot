# bot/firebase_service.py

import firebase_admin
from firebase_admin import credentials, db
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_KEY_PATH = os.path.join(BASE_DIR, "firebase/serviceAccountKey.json")

DATABASE_URL = "https://moderation-ad9f6-default-rtdb.europe-west1.firebasedatabase.app"


# Инициализация Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_KEY_PATH)
    firebase_admin.initialize_app(cred, {
        "databaseURL": DATABASE_URL
    })


def set_data(path: str, data: dict):
    """
    Полностью заменяет данные по указанному пути
    """
    ref = db.reference(path)
    ref.set(data)


def update_data(path: str, data: dict):
    """
    Обновляет поля по указанному пути
    """
    ref = db.reference(path)
    ref.update(data)


def delete(path: str):
    """
    Удаляет узел
    """
    ref = db.reference(path)
    ref.delete()


def get(path: str):
    """
    Получает данные по пути
    """
    ref = db.reference(path)
    return ref.get()
