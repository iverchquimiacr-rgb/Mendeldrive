from database import load_users, load_payments
from datetime import datetime

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

    user = users_df[users_df["ID"] == int(user_id)].iloc[0]

    # 🔹 datos base
    monto_base = float(user.get("Monto_base", 0))
    tipo_pago = str(user.get("Tipo_pago", "Unico"))

    # 🔹 pagos aprobados
    total_pagado = 0.0

    if not payments_df.empty:

        payments_df["Usuario_ID"] = payments_df["Usuario_ID"].astype(int)
        payments_df["Monto"] = payments_df["Monto"].astype(float)
        payments_df["Estado"] = payments_df["Estado"].astype(str)

        pagos_usuario = payments_df[
            (payments_df["Usuario_ID"] == int(user_id)) &
            (payments_df["Estado"] == "Aprobado")
        ]

        if not pagos_usuario.empty:
            total_pagado = float(pagos_usuario["Monto"].sum())

    # ==============================
    # 🔥 CÁLCULO SEGÚN TIPO DE PAGO
    # ==============================

    if tipo_pago in ["Semanal", "Mensual"]:

        fecha_registro = user.get("Fecha_registro", "")
        hoy = datetime.now()

        try:
            fecha_inicio = datetime.strptime(fecha_registro[:10], "%Y-%m-%d")
        except:
            fecha_inicio = hoy

        # 🔹 calcular ciclos transcurridos
        dias = (hoy - fecha_inicio).days

        if tipo_pago == "Semanal":
            ciclos = max(1, dias // 7)
        else:  # Mensual
            ciclos = max(1, dias // 28)

        deuda_total = ciclos * monto_base
        saldo_pendiente = deuda_total - total_pagado

    else:
        # 🔹 pago único (lógica original)
        saldo_pendiente = monto_base - total_pagado

    # 🔹 evitar negativos (muy importante)
    saldo_pendiente = max(0.0, saldo_pendiente)

    return {
        "MontoBase": float(monto_base),
        "TotalPagado": float(total_pagado),
        "SaldoPendiente": float(saldo_pendiente)
    }