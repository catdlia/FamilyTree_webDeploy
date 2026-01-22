import csv
import os
from datetime import datetime

LOG_FILE = os.path.join("family_tree_data", "activity_log.csv")


class LoggerService:
    def __init__(self):
        if not os.path.exists(LOG_FILE):
            os.makedirs("family_tree_data", exist_ok=True)
            with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "User", "Action", "Details"])

    def log(self, action: str, details: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # --- УНІВЕРСАЛЬНЕ ВИЗНАЧЕННЯ КОРИСТУВАЧА ---
        user = "Desktop Admin"  # За замовчуванням
        try:
            import streamlit as st
            # Перевіряємо, чи ми в контексті Streamlit
            if hasattr(st, 'session_state') and 'name' in st.session_state:
                user = st.session_state['name']
        except ImportError:
            pass  # Якщо streamlit не встановлено або не запущено
        except Exception:
            pass  # Інші помилки контексту
        # -------------------------------------------

        try:
            with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, user, action, details])
        except Exception as e:
            print(f"Logging error: {e}")

    def get_recent_logs(self, limit=20):
        if not os.path.exists(LOG_FILE): return []
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                reader = list(csv.reader(f))
                if len(reader) < 2: return []
                data = reader[1:]
                return data[-limit:][::-1]
        except:
            return []