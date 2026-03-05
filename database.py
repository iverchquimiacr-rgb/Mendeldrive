import os
import sqlite3
import psycopg2
import pandas as pd

DB_NAME = "database.db"


# ==============================
# CONEXIÓN
# ==============================
def get_connection():

    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        # PostgreSQL (Render)
        conn = psycopg2.connect(database_url)
        return conn

    else:
        # SQLite local
        conn = sqlite3.connect(DB_NAME)
        return conn


def is_postgres(conn):
    return "psycopg2" in str(type(conn))


# ==============================
# INICIALIZAR BASE DE DATOS
# ==============================
def initialize_database():

    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres(conn):

        # ==============================
        # USUARIOS
        # ==============================

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nombre TEXT,
            password TEXT,
            tipo_pago TEXT,
            carpetas_compradas TEXT,
            carpetas_asignadas INTEGER,
            monto_base REAL,
            pago_confirmado TEXT,
            fecha_registro TEXT,
            estado TEXT,
            fecha_ultimo_pago TEXT,
            fecha_vencimiento TEXT,
            rol TEXT,
            debe_cambiar_password INTEGER,
            debe_elegir_plan INTEGER
        )
        """)

        # ==============================
        # PAGOS
        # ==============================

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER,
            monto REAL,
            fecha TEXT,
            estado TEXT,
            comprobante TEXT,
            admin_id INTEGER,
            fecha_procesado TEXT
        )
        """)

    else:

        # ==============================
        # SQLITE
        # ==============================

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
# NORMALIZAR COLUMNAS
# ==============================
def normalize_users_columns(df):

    if df.empty:
        return df

    # PostgreSQL usa minúsculas
    df.columns = [col.capitalize() for col in df.columns]

    rename_map = {
        "Id": "ID",
        "Nombre": "Nombre",
        "Password": "Password",
        "Tipo_pago": "Tipo_pago",
        "Carpetas_compradas": "Carpetas_compradas",
        "Carpetas_asignadas": "Carpetas_asignadas",
        "Monto_base": "Monto_base",
        "Pago_confirmado": "Pago_confirmado",
        "Fecha_registro": "Fecha_registro",
        "Estado": "Estado",
        "Fecha_ultimo_pago": "Fecha_ultimo_pago",
        "Fecha_vencimiento": "Fecha_vencimiento",
        "Rol": "Rol",
        "Debe_cambiar_password": "Debe_cambiar_password",
        "Debe_elegir_plan": "Debe_elegir_plan"
    }

    df = df.rename(columns=rename_map)

    return df


def normalize_payments_columns(df):

    if df.empty:
        return df

    df.columns = [col.capitalize() for col in df.columns]

    rename_map = {
        "Id": "ID",
        "Usuario_id": "Usuario_ID",
        "Monto": "Monto",
        "Fecha": "Fecha",
        "Estado": "Estado",
        "Comprobante": "Comprobante",
        "Admin_id": "Admin_ID",
        "Fecha_procesado": "Fecha_procesado"
    }

    df = df.rename(columns=rename_map)

    return df


# ==============================
# USUARIOS
# ==============================
def load_users():

    initialize_database()

    conn = get_connection()

    df = pd.read_sql_query("SELECT * FROM usuarios", conn)

    conn.close()

    df = normalize_users_columns(df)

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

    if not is_postgres(conn):

        df.to_sql("usuarios", conn, if_exists="replace", index=False)

    else:

        cursor = conn.cursor()

        cursor.execute("DELETE FROM usuarios")

        if "ID" in df.columns:
            df = df.drop(columns=["ID"])

        for _, row in df.iterrows():

            cursor.execute("""
            INSERT INTO usuarios (
                nombre,
                password,
                tipo_pago,
                carpetas_compradas,
                carpetas_asignadas,
                monto_base,
                pago_confirmado,
                fecha_registro,
                estado,
                fecha_ultimo_pago,
                fecha_vencimiento,
                rol,
                debe_cambiar_password,
                debe_elegir_plan
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                row.get("Nombre"),
                row.get("Password"),
                row.get("Tipo_pago"),
                row.get("Carpetas_compradas"),
                row.get("Carpetas_asignadas"),
                row.get("Monto_base"),
                row.get("Pago_confirmado"),
                row.get("Fecha_registro"),
                row.get("Estado"),
                row.get("Fecha_ultimo_pago"),
                row.get("Fecha_vencimiento"),
                row.get("Rol"),
                row.get("Debe_cambiar_password"),
                row.get("Debe_elegir_plan")
            ))

        conn.commit()

    conn.close()


# ==============================
# PAGOS
# ==============================
def load_payments():

    initialize_database()

    conn = get_connection()

    df = pd.read_sql_query("SELECT * FROM pagos", conn)

    conn.close()

    df = normalize_payments_columns(df)

    return df


def save_payments(df):

    conn = get_connection()

    if not is_postgres(conn):

        df.to_sql("pagos", conn, if_exists="replace", index=False)

    else:

        cursor = conn.cursor()

        cursor.execute("DELETE FROM pagos")

        for _, row in df.iterrows():

            cursor.execute("""
            INSERT INTO pagos (
                usuario_id,
                monto,
                fecha,
                estado,
                comprobante,
                admin_id,
                fecha_procesado
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                row.get("Usuario_ID"),
                row.get("Monto"),
                row.get("Fecha"),
                row.get("Estado"),
                row.get("Comprobante"),
                row.get("Admin_ID"),
                row.get("Fecha_procesado")
            ))

        conn.commit()

    conn.close()