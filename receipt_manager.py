from database import get_connection
from datetime import datetime
import pandas as pd

# ==============================
# CREAR COMPROBANTE
# ==============================

def create_receipt(user_id, nombre, monto):

    conn = get_connection()
    cur = conn.cursor()

    # obtener siguiente ID
    cur.execute("SELECT COUNT(*) FROM comprobantes")
    total = cur.fetchone()[0] + 1

    year = datetime.now().year

    nombre_clean = nombre.replace(" ", "_").upper()

    codigo = f"{year}-{nombre_clean}-{total}"

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        INSERT INTO comprobantes
        (Codigo, Usuario_ID, Nombre, Monto, Fecha)
        VALUES (%s, %s, %s, %s, %s)
    """, (codigo, user_id, nombre, monto, fecha))

    conn.commit()
    conn.close()

    return codigo


# ==============================
# LISTAR COMPROBANTES
# ==============================

def get_all_receipts():

    conn = get_connection()

    df = pd.read_sql("SELECT * FROM comprobantes ORDER BY ID DESC", conn)

    conn.close()

    return df