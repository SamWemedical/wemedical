import sqlite3

def get_db_connection():
    conn = sqlite3.connect('WEmedical.db', timeout=10)  # รอสูงสุด 10 วินาที
    conn.row_factory = sqlite3.Row
    return conn