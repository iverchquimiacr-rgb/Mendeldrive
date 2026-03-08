import sqlite3
from pathlib import Path

DB_PATH = "database.db"

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

def main():
    # Conectar a la base de datos (si existe, se sobreescribe al borrar tablas)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # ⚠️ Borrar tablas existentes para empezar desde cero
    cursor.execute("DROP TABLE IF EXISTS usuarios")
    cursor.execute("DROP TABLE IF EXISTS pagos")
    conn.commit()
    
    # Crear tablas vacías
    create_tables(conn)
    
    print("✔ Base de datos reiniciada y tablas vacías")
    conn.close()

if __name__ == "__main__":
    main()