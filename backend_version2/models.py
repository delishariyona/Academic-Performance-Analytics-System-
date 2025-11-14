# backend/models.py
import mysql.connector
from config import DB_CONFIG

def get_db():
    """
    Returns a mysql.connector connection.
    Caller should close() the connection when done.
    """
    return mysql.connector.connect(**DB_CONFIG)
