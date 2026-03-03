import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = "database.db"
EXCEL_PATH = "data.xlsx"

def create_tables(conn):
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        ID INTEGER PRIMARY KEY,
        Nombre TEXT,
        Password TEXT,
        Tipo_pago TEXT,
        Carpetas_compradas TEXT,
        Carpetas_asignadas INTEGER,
        Monto_base REAL,
        Pago_confirmado TEXT,
        Fecha_registro TEXT,
        Estado TEXT,
        Fecha_ultimo_pago TEXT,
        Fecha_vencimiento TEXT,
        Rol TEXT,
        Debe_cambiar_password INTEGER,
        Debe_elegir_plan INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pagos (
        ID INTEGER PRIMARY KEY,
        usuario_ID INTEGER,
        monto REAL,
        fecha TEXT,
        estado TEXT,
        comprobante TEXT,
        admin_ID INTEGER,
        fecha_procesado TEXT
    )
    """)

    conn.commit()

def migrate_excel_to_sqlite(conn):
    df_usuarios = pd.read_excel(EXCEL_PATH, sheet_name="Usuarios")
    df_pagos = pd.read_excel(EXCEL_PATH, sheet_name="Pagos")

    df_usuarios.to_sql("usuarios", conn, if_exists="append", index=False)
    df_pagos.to_sql("pagos", conn, if_exists="append", index=False)

def verify_migration(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    usuarios_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM pagos")
    pagos_count = cursor.fetchone()[0]

    print("✔ Migración completada")
    print(f"Usuarios migrados: {usuarios_count}")
    print(f"Pagos migrados: {pagos_count}")

def main():
    if not Path(EXCEL_PATH).exists():
        raise FileNotFoundError("No se encontró data.xlsx")

    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)
    migrate_excel_to_sqlite(conn)
    verify_migration(conn)
    conn.close()

if __name__ == "__main__":
    main()