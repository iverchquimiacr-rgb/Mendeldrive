import json
from datetime import datetime
from database import load_users, save_users

# ==============================
# CALCULAR PUNTAJE
# ==============================
def calcular_puntaje(respuestas):

    puntaje = 0

    # BLOQUE 1
    p1 = respuestas.get("p1")
    puntaje += { "2":0, "3-4":1, "5-6":2, "7+":3 }.get(p1, 0)

    p2 = respuestas.get("p2")
    puntaje += {
        "propia_pagada":0,
        "propia_cuotas":1,
        "alquilada":2,
        "prestada":3,
        "cuarto":3
    }.get(p2, 0)

    servicios = respuestas.get("p3", [])
    puntaje += max(0, 4 - len(servicios))

    # BLOQUE 2
    puntaje += {
        "empresa":0,
        "planilla":1,
        "independiente":2,
        "campo":3,
        "pension":3,
        "sin_ingresos":4
    }.get(respuestas.get("p5"), 0)

    puntaje += {
        "3+":0,
        "2":1,
        "1":2,
        "0":3
    }.get(respuestas.get("p6"), 0)

    puntaje += {
        "3500+":0,
        "1800-3500":1,
        "930-1800":2,
        "500-930":3,
        "menos500":4
    }.get(respuestas.get("p7"), 0)

    p8 = respuestas.get("p8", [])
    for item in p8:
        if item == "alimentacion":
            puntaje += 2
        else:
            puntaje += 1

    puntaje = min(puntaje, 42)

    # BLOQUE 3
    puntaje += {
        "privado_alto":0,
        "privado_medio":1,
        "privado_bajo":2,
        "publico":3
    }.get(respuestas.get("p9"), 0)

    puntaje += {
        "alto":0,
        "medio":1,
        "bajo":2,
        "no_puede":3
    }.get(respuestas.get("p10"), 0)

    puntaje += {
        "no":0,
        "ocasional":1,
        "trabaja":2,
        "aporta":3
    }.get(respuestas.get("p11"), 0)

    puntaje += {
        "propia":0,
        "compartida":1,
        "no":2
    }.get(respuestas.get("p12"), 0)

    return puntaje


# ==============================
# CALCULAR DESCUENTO
# ==============================
def obtener_descuento(puntaje):

    if puntaje <= 10:
        return 0
    elif puntaje <= 18:
        return 25
    elif puntaje <= 26:
        return 50
    elif puntaje <= 34:
        return 75
    else:
        return 100


# ==============================
# GUARDAR SOLICITUD
# ==============================
def guardar_solicitud_descuento(user_id, respuestas, archivos):

    users_df = load_users()

    if user_id not in users_df["ID"].values:
        return False

    puntaje = calcular_puntaje(respuestas)
    descuento = obtener_descuento(puntaje)

    solicitud = {
        "estado": "Pendiente",
        "puntaje": puntaje,
        "descuento_sugerido": descuento,
        "respuestas": respuestas,
        "archivos": archivos,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    users_df.loc[
        users_df["ID"] == user_id,
        "Descuento_info"
    ] = json.dumps(solicitud)

    save_users(users_df)

    return True


# ==============================
# APROBAR DESCUENTO (ADMIN)
# ==============================
def aprobar_descuento(user_id, admin_id):

    users_df = load_users()

    user = users_df[users_df["ID"] == user_id].iloc[0]

    data = json.loads(user["Descuento_info"])

    data["estado"] = "Aprobado"
    data["admin_id"] = admin_id

    users_df.loc[users_df["ID"] == user_id, "Descuento_info"] = json.dumps(data)

    save_users(users_df)


# ==============================
# RECHAZAR DESCUENTO
# ==============================
def rechazar_descuento(user_id, admin_id):

    users_df = load_users()

    user = users_df[users_df["ID"] == user_id].iloc[0]

    data = json.loads(user["Descuento_info"])

    data["estado"] = "Rechazado"
    data["admin_id"] = admin_id

    users_df.loc[users_df["ID"] == user_id, "Descuento_info"] = json.dumps(data)

    save_users(users_df)