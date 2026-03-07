from database import load_users, load_payments


# ==============================
# OBTENER ESTADO DE CUENTA
# ==============================

def get_account_status(user_id):

    users_df = load_users()
    payments_df = load_payments()

    if users_df.empty:
        return None

    # 🔧 asegurar tipos correctos
    users_df["ID"] = users_df["ID"].astype(int)

    if user_id not in users_df["ID"].values:
        return None

    user = users_df[users_df["ID"] == int(user_id)]

    monto_base = float(user.iloc[0]["Monto_base"])

    # 🔧 si no hay pagos aún
    if payments_df.empty:
        total_pagado = 0
    else:

        # 🔧 asegurar columnas y tipos
        payments_df["Usuario_ID"] = payments_df["Usuario_ID"].astype(int)
        payments_df["Monto"] = payments_df["Monto"].astype(float)
        payments_df["Estado"] = payments_df["Estado"].astype(str)

        pagos_usuario = payments_df[
            (payments_df["Usuario_ID"] == int(user_id)) &
            (payments_df["Estado"] == "Aprobado")
        ]

        total_pagado = pagos_usuario["Monto"].sum() if not pagos_usuario.empty else 0

    saldo_pendiente = monto_base - total_pagado

    return {
        "MontoBase": float(monto_base),
        "TotalPagado": float(total_pagado),
        "SaldoPendiente": float(saldo_pendiente)
    }