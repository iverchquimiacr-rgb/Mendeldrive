import sqlite3
from security import hash_password

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("SELECT ID, Password FROM usuarios")
users = cursor.fetchall()

for user_id, password in users:

    if not password.startswith("pbkdf2:"):
        hashed = hash_password(password)

        cursor.execute(
            "UPDATE usuarios SET Password = ? WHERE ID = ?",
            (hashed, user_id)
        )

conn.commit()
conn.close()

print("✔ Contraseñas convertidas a hash")