from database import load_users, load_payments


# ==============================
# OBTENER ESTADO DE CUENTA
# ==============================

def get_account_status(user_id):
    users_df = load_users()
    payments_df = load_payments()

    if users_df.empty:
        return None

    if user_id not in users_df["ID"].values:
        return None

    user = users_df[users_df["ID"] == user_id]

    monto_base = user.iloc[0]["Monto_base"]

    # Filtrar pagos aprobados
    pagos_usuario = payments_df[
        (payments_df["Usuario_ID"] == user_id) &
        (payments_df["Estado"] == "Aprobado")
    ]

    total_pagado = pagos_usuario["Monto"].sum() if not pagos_usuario.empty else 0

    saldo_pendiente = monto_base - total_pagado

    return {
        "MontoBase": monto_base,
        "TotalPagado": total_pagado,
        "SaldoPendiente": saldo_pendiente
    }
