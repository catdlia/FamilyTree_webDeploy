# utils/hasher.py
import bcrypt

# Список паролів, які ти хочеш використовувати
passwords_to_hash = ['admin123', 'f87A]35EDo32']

print("--- ЗБЕРЕЖИ ЦІ ХЕШІ У .streamlit/secrets.toml ---")

for password in passwords_to_hash:
    # Генеруємо сіль і хеш
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    # Декодуємо в стрічку для запису в TOML
    hashed_str = hashed.decode('utf-8')
    print(f'Password: "{password}" -> Hash: "{hashed_str}"')