import json
from database import get_connection


# ==============================
# GUARDAR SOLICITUD
# ==============================

def guardar_solicitud_descuento(user_id, respuestas, archivos):

    conn = get_connection()
    cursor = conn.cursor()

    puntaje = calcular_puntaje(respuestas)

    cursor.execute("""
        INSERT INTO solicitudes_descuento
        (usuario_id, respuestas, puntaje, estado, archivos)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        user_id,
        json.dumps(respuestas),
        puntaje,
        "Pendiente",
        json.dumps(archivos)
    ))

    conn.commit()
    conn.close()

    return True


# ==============================
# CALCULAR PUNTAJE
# ==============================

def calcular_puntaje(r):

    puntaje = 0

    # P1
    p1 = int(r.get("p1", 0))
    if p1 <= 2: puntaje += 0
    elif p1 <= 4: puntaje += 1
    elif p1 <= 6: puntaje += 2
    else: puntaje += 3

    # P2
    vivienda_map = {
        "propio_pagado": 0,
        "propio_cuotas": 1,
        "alquilada": 2,
        "prestada": 3,
        "cuarto": 3
    }
    puntaje += vivienda_map.get(r.get("p2"), 0)

    # P3
    servicios = r.get("p3", [])
    puntaje += max(0, 4 - len(servicios))

    # P5
    ingreso_map = {
        "empresa": 0,
        "planilla": 1,
        "independiente": 2,
        "agricola": 3,
        "pension": 3,
        "sin_ingresos": 4
    }
    puntaje += ingreso_map.get(r.get("p5"), 0)

    # P6
    aportantes_map = {
        "3+": 0,
        "2": 1,
        "1": 2,
        "0": 3
    }
    puntaje += aportantes_map.get(r.get("p6"), 0)

    # P7
    ingreso_mensual_map = {
        "3500+": 0,
        "1800-3500": 1,
        "930-1800": 2,
        "500-930": 3,
        "0-500": 4
    }
    puntaje += ingreso_mensual_map.get(r.get("p7"), 0)

    # P8
    dificultades = r.get("p8", [])
    puntaje += min(4, len(dificultades))

    # P9
    colegio_map = {
        "privado_alto": 0,
        "privado_medio": 1,
        "privado_bajo": 2,
        "publico": 3
    }
    puntaje += colegio_map.get(r.get("p9"), 0)

    # P10
    academia_map = {
        "alto": 0,
        "medio": 1,
        "bajo": 2,
        "no": 3
    }
    puntaje += academia_map.get(r.get("p10"), 0)

    # P11
    trabajo_map = {
        "no": 0,
        "ocasional": 1,
        "propios": 2,
        "hogar": 3
    }
    puntaje += trabajo_map.get(r.get("p11"), 0)

    # P12
    compu_map = {
        "propia": 0,
        "compartida": 1,
        "no": 2
    }
    puntaje += compu_map.get(r.get("p12"), 0)

    return puntaje


# ==============================
# OBTENER SOLICITUDES
# ==============================

def obtener_solicitudes():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.id, s.usuario_id, u.nombre, s.puntaje, s.estado
        FROM solicitudes_descuento s
        JOIN usuarios u ON u.id = s.usuario_id
        ORDER BY s.id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    def calcular_descuento(puntaje):
        if puntaje >= 15:
            return 50
        elif puntaje >= 10:
            return 30
        elif puntaje >= 5:
            return 15
        return 0

    return [
        {
            "id": r[0],
            "usuario_id": r[1],
            "nombre": r[2],
            "puntaje": r[3],
            "estado": r[4],
            "descuento": calcular_descuento(r[3])
        }
        for r in rows
    ]


# ==============================
# APROBAR
# ==============================

def aprobar_solicitud(solicitud_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE solicitudes_descuento
        SET estado = 'Aprobado'
        WHERE id = %s
    """, (solicitud_id,))

    conn.commit()
    conn.close()

    return True


# ==============================
# RECHAZAR
# ==============================

def rechazar_solicitud(solicitud_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE solicitudes_descuento
        SET estado = 'Rechazado'
        WHERE id = %s
    """, (solicitud_id,))

    conn.commit()
    conn.close()

    return True

# ==============================
# ELIMINAR SOLICITUD
# ==============================

def eliminar_solicitud(solicitud_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM solicitudes_descuento
        WHERE id = %s
    """, (solicitud_id,))

    conn.commit()
    conn.close()

    return True