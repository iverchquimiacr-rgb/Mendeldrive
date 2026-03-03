from database import load_users, save_users
from datetime import datetime
import pandas as pd


# ==============================
# ACTUALIZAR SUSCRIPCIONES
# ==============================

def actualizar_suscripciones():
    users_df = load_users()

    if users_df.empty:
        return

    hoy = datetime.now().date()

    # 🔒 ASEGURAR QUE SEA TEXTO
    users_df["Fecha_vencimiento"] = users_df["Fecha_vencimiento"].astype(str)

    # 🔄 CONVERTIR SOLO FECHAS VÁLIDAS
    users_df["Fecha_vencimiento_dt"] = pd.to_datetime(
        users_df["Fecha_vencimiento"],
        format="%Y-%m-%d",
        errors="coerce"
    )

    for idx, user in users_df.iterrows():

        tipo = user["Tipo_pago"]

        # Pago único nunca vence
        if tipo == "Unico":
            continue

        fecha_v = user["Fecha_vencimiento_dt"]

        # Sin fecha válida → no evaluar
        if pd.isna(fecha_v):
            continue

        if fecha_v.date() < hoy:
            users_df.at[idx, "Estado"] = "Vencido"
        else:
            users_df.at[idx, "Estado"] = "Activo"

    # 🧹 LIMPIEZA
    users_df.drop(columns=["Fecha_vencimiento_dt"], inplace=True)

    save_users(users_df)