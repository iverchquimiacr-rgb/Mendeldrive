import os
import sqlite3
import psycopg2
import pandas as pd
from urllib.parse import urlparse

DB_NAME = "database.db"

# ==============================
# CONEXIÓN
# ==============================
def get_connection():
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        # PostgreSQL en Render
        return psycopg2.connect(database_url)
    else:
        # SQLite local
        return sqlite3.connect(DB_NAME)
# ==============================
# INICIALIZAR BASE DE DATOS
# ==============================
def initialize_database():
    """
    Crea las tablas 'usuarios' y 'pagos' si no existen.
    No crea admin aquí; eso se hace en user_manager.crear_admin_inicial()
    """
    conn = get_connection()
    cursor = conn.cursor()

    # TABLA USUARIOS
    if "postgres" in str(type(conn)).lower():
        # PostgreSQL
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            ID SERIAL PRIMARY KEY,
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
    else:
        # SQLite
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

    # TABLA PAGOS
    if "postgres" in str(type(conn)).lower():
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            ID SERIAL PRIMARY KEY,
            Usuario_ID INTEGER,
            Monto REAL,
            Fecha TEXT,
            Estado TEXT,
            Comprobante TEXT,
            Admin_ID INTEGER,
            Fecha_procesado TEXT
        )
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            ID INTEGER PRIMARY KEY,
            Usuario_ID INTEGER,
            Monto REAL,
            Fecha TEXT,
            Estado TEXT,
            Comprobante TEXT,
            Admin_ID INTEGER,
            Fecha_procesado TEXT
        )
        """)

    conn.commit()
    conn.close()

# ==============================
# USUARIOS
# ==============================
def load_users():
    initialize_database()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM usuarios", conn)
    conn.close()

    columnas_necesarias = {
        "Rol": "Usuario",
        "Debe_cambiar_password": 0,
        "Debe_elegir_plan": 0
    }

    for col, default in columnas_necesarias.items():
        if col not in df.columns:
            df[col] = default

    return df

def save_users(df):
    conn = get_connection()
    df.to_sql("usuarios", conn, if_exists="replace", index=False)
    conn.close()

# ==============================
# PAGOS
# ==============================
def load_payments():
    initialize_database()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM pagos", conn)
    conn.close()
    return df

def save_payments(df):
    conn = get_connection()
    df.to_sql("pagos", conn, if_exists="replace", index=False)
    conn.close()