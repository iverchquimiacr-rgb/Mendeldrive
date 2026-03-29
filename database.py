import os
import sqlite3
import psycopg2
import pandas as pd
from sqlalchemy import create_engine

DB_NAME = "database.db"

# ==============================
# MOTOR SQLALCHEMY
# ==============================
def get_engine():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return create_engine(database_url)  # PostgreSQL
    else:
        return create_engine(f"sqlite:///{DB_NAME}")  # SQLite local

# ==============================
# CONEXIÓN DIRECTA
# ==============================
def get_connection():
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        try:
            print("Using PostgreSQL database")
            conn = psycopg2.connect(database_url, sslmode="require")
            return conn
        except Exception as e:
            print("PostgreSQL connection error:", e)
            raise

    else:
        print("Using SQLite local database")
        return sqlite3.connect(DB_NAME)

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
                # ==============================
        # COMPROBANTES
        # ==============================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS comprobantes (
            id SERIAL PRIMARY KEY,
            codigo TEXT,
            usuario_id INTEGER,
            nombre TEXT,
            monto REAL,
            fecha TEXT
        )
        """)
        # ==============================
        # REGISTRO DE IPS (ANTI SPAM)
        # ==============================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS registro_ips (
            id SERIAL PRIMARY KEY,
            ip TEXT,
           fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS comprobantes (
            ID INTEGER PRIMARY KEY,
            Codigo TEXT,
            Usuario_ID INTEGER,
            Nombre TEXT,
            Monto REAL,
            Fecha TEXT
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS registro_ips (
           ID INTEGER PRIMARY KEY,
           IP TEXT,
           Fecha TEXT
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
    
    print("🚨 NORMALIZE PAYMENTS EJECUTADA")
    
    if df.empty:
        return df

    print("DEBUG PAGOS COLUMNAS RAW:", df.columns.tolist())

    # 🔹 limpieza completa de columnas
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "")
    )

    print("DEBUG PAGOS COLUMNAS LIMPIAS:", df.columns.tolist())

    rename_map = {
        "id": "ID",
        "usuario_id": "Usuario_ID",
        "monto": "Monto",
        "fecha": "Fecha",
        "estado": "Estado",
        "comprobante": "Comprobante",
        "admin_id": "Admin_ID",
        "fecha_procesado": "Fecha_procesado"
    }

    df = df.rename(columns=rename_map)

    print("DEBUG PAGOS COLUMNAS FINAL:", df.columns.tolist())

    return df

# ==============================
# USUARIOS
# ==============================
def load_users():
    """
    Carga los usuarios desde la base de datos SQLite y asegura tipos y columnas necesarias.
    """
    initialize_database()
    engine = get_engine()
    df = pd.read_sql("SELECT * FROM usuarios", engine)  # 🔹 SQLAlchemy usado solo para lectura
    df = normalize_users_columns(df)

    # Asegurar columnas necesarias con valores por defecto
    columnas_necesarias = {
        "Rol": "Usuario",
        "Debe_cambiar_password": 0,
        "Debe_elegir_plan": 0,
        "Password": "",
        "Descuento_info": ""   # ✅ NUEVO CAMPO
    }

    for col, default in columnas_necesarias.items():
        if col not in df.columns:
            df[col] = default

    # 🔹 Forzar ID como entero
    if "ID" in df.columns:
        df["ID"] = df["ID"].astype(int)

    return df

def save_users(df):
    conn = get_connection()
    cursor = conn.cursor() if is_postgres(conn) else None

    if not is_postgres(conn):
        engine = get_engine()  # 🔹 SQLAlchemy para SQLite simple
        df.to_sql("usuarios", engine, if_exists="replace", index=False)
    else:
        # PostgreSQL upsert sin tocar lógica
        for _, row in df.iterrows():
            user_id = row.get("ID")
            if user_id is None:
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
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
            else:
                cursor.execute("""
                INSERT INTO usuarios (
                    id,
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
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id)
                DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    password = EXCLUDED.password,
                    tipo_pago = EXCLUDED.tipo_pago,
                    carpetas_compradas = EXCLUDED.carpetas_compradas,
                    carpetas_asignadas = EXCLUDED.carpetas_asignadas,
                    monto_base = EXCLUDED.monto_base,
                    pago_confirmado = EXCLUDED.pago_confirmado,
                    fecha_registro = EXCLUDED.fecha_registro,
                    estado = EXCLUDED.estado,
                    fecha_ultimo_pago = EXCLUDED.fecha_ultimo_pago,
                    fecha_vencimiento = EXCLUDED.fecha_vencimiento,
                    rol = EXCLUDED.rol,
                    debe_cambiar_password = EXCLUDED.debe_cambiar_password,
                    debe_elegir_plan = EXCLUDED.debe_elegir_plan
                """, (
                    row.get("ID"),
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

    print("DEBUG PAGOS COLUMNAS:", df.columns.tolist())

    # 🔧 normalizar nombres de columnas (PostgreSQL -> formato app)
    column_map = {
        "id": "ID",
        "usuario_id": "Usuario_ID",
        "monto": "Monto",
        "fecha": "Fecha",
        "estado": "Estado",
        "comprobante": "Comprobante",
        "admin_id": "Admin_ID",
        "fecha_procesado": "Fecha_procesado"
    }

    df = df.rename(columns=column_map)

    # 🔧 evitar NaN que luego rompen PostgreSQL
    if "Admin_ID" in df.columns:
        df["Admin_ID"] = df["Admin_ID"].fillna("")

    if "Fecha_procesado" in df.columns:
        df["Fecha_procesado"] = df["Fecha_procesado"].fillna("")

    if "Comprobante" in df.columns:
        df["Comprobante"] = df["Comprobante"].fillna("")

    return df

def save_payments(df):
    conn = get_connection()

    # 🔹 Normalizar nombres de columnas
    column_map = {
        "ID": "id",
        "Usuario_ID": "usuario_id",
        "Monto": "monto",
        "Fecha": "fecha",
        "Estado": "estado",
        "Comprobante": "comprobante",
        "Admin_ID": "admin_id",
        "Fecha_procesado": "fecha_procesado"
    }

    df = df.rename(columns=column_map)

    # 🔹 limpiar NaN
    df = df.where(pd.notnull(df), None)

    # 🔹 eliminar id para postgres
    if "id" in df.columns:
        df = df.drop(columns=["id"])

    # 🔹 resetear índice
    df = df.reset_index(drop=True)

    # 🔹 asegurar tipos
    if "monto" in df.columns:
        df["monto"] = df["monto"].astype(float)

    if "usuario_id" in df.columns:
        df["usuario_id"] = df["usuario_id"].astype(int)

    if "admin_id" in df.columns:

        def clean_admin_id(x):
            if pd.isna(x) or x in ["", "nan"]:
                return None
            try:
                x = int(x)
                if x > 2147483647:
                    return None
                return x
            except:
                return None

        df["admin_id"] = df["admin_id"].apply(clean_admin_id)

    if "fecha_procesado" in df.columns:
        df["fecha_procesado"] = df["fecha_procesado"].apply(
            lambda x: None if pd.isna(x) or x in ["", "nan"] else x
        )

    if not is_postgres(conn):
        # 🔹 SQLite
        engine = get_engine()
        df.to_sql("pagos", engine, if_exists="replace", index=False)

    else:
        # 🔹 PostgreSQL
        cursor = conn.cursor()

        cursor.execute("TRUNCATE TABLE pagos RESTART IDENTITY")

        for _, row in df.iterrows():

            usuario_id = None if pd.isna(row["usuario_id"]) else int(row["usuario_id"])
            monto = None if pd.isna(row["monto"]) else float(row["monto"])
            admin_id = None if pd.isna(row["admin_id"]) else int(row["admin_id"])

            cursor.execute("""
                INSERT INTO pagos
                (usuario_id, monto, fecha, estado, comprobante, admin_id, fecha_procesado)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                usuario_id,
                monto,
                row["fecha"],
                row["estado"],
                row["comprobante"],
                admin_id,
                row["fecha_procesado"]
            ))

        conn.commit()

    conn.close()