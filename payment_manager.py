from database import load_users, save_users, load_payments, save_payments
from datetime import datetime, timedelta
import pandas as pd

from logger_actions import log_action
from logger import log_payment


# ==============================
# AGREGAR PAGO (USUARIO / ADMIN)
# ==============================

def add_payment(user_id, monto):
    users_df = load_users()
    payments_df = load_payments()

    if user_id not in users_df["ID"].values:
        print("Usuario no encontrado.")
        return

    # 🧾 aseguramos columna Comprobante
    if "Comprobante" not in payments_df.columns:
        payments_df["Comprobante"] = ""

    new_payment_id = 1 if payments_df.empty else payments_df["ID"].max() + 1
    fecha_pago = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    nuevo_pago = {
        "ID": new_payment_id,
        "Usuario_ID": user_id,
        "Monto": monto,
        "Fecha": fecha_pago,
        "Estado": "Pendiente",
        "Comprobante": ""
    }

    payments_df = pd.concat(
        [payments_df, pd.DataFrame([nuevo_pago])],
        ignore_index=True
    )

    save_payments(payments_df)

    log_payment(
        user_id=user_id,
        pago_id=new_payment_id,
        evento="PAGO_REGISTRADO",
        monto=monto
    )

    print("✅ Pago registrado correctamente. Estado: Pendiente")


# ==============================
# APROBAR PAGO (SOLO ADMIN)
# ==============================

# ==============================
# APROBAR PAGO (SOLO ADMIN)
# ==============================

def approve_payment(payment_id, sesion):

    if sesion["rol"] != "Admin":
        print("⛔ Acción no permitida. Requiere rol ADMIN.")
        return

    payments_df = load_payments()
    users_df = load_users()

    if payment_id not in payments_df["ID"].values:
        print("Pago no encontrado.")
        return

    # 🧾 Asegurar columnas de auditoría
    if "Admin_ID" not in payments_df.columns:
        payments_df["Admin_ID"] = ""
    if "Fecha_procesado" not in payments_df.columns:
        payments_df["Fecha_procesado"] = ""

    pago = payments_df[payments_df["ID"] == payment_id].iloc[0]

    # 🔒 Validar estado
    if pago["Estado"] != "Pendiente":
        print(f"⛔ No se puede aprobar un pago en estado '{pago['Estado']}'")
        return

    # 🔒 Validar comprobante
    if not pago.get("Comprobante"):
        print("⛔ No se puede aprobar un pago sin comprobante.")
        return

    # ✅ Aprobar
    payments_df.loc[payments_df["ID"] == payment_id, "Estado"] = "Aprobado"
    payments_df.loc[payments_df["ID"] == payment_id, "Admin_ID"] = str(sesion["id"])
    payments_df.loc[
        payments_df["ID"] == payment_id,
        "Fecha_procesado"
    ] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    user_id = int(pago["Usuario_ID"])

    ahora = datetime.now()
    user = users_df[users_df["ID"] == user_id].iloc[0]

    tipo_pago = user["Tipo_pago"]

    if tipo_pago == "Semanal":
        fecha_vencimiento = ahora + timedelta(days=7)
    elif tipo_pago == "Mensual":
        fecha_vencimiento = ahora + timedelta(days=28)
    else:
        fecha_vencimiento = None

    users_df.loc[users_df["ID"] == user_id, "Pago_confirmado"] = "Confirmado"
    users_df.loc[users_df["ID"] == user_id, "Estado"] = "Activo"
    users_df.loc[users_df["ID"] == user_id, "Fecha_ultimo_pago"] = ahora.strftime("%Y-%m-%d")
    users_df.loc[users_df["ID"] == user_id, "Fecha_vencimiento"] = (
        fecha_vencimiento.strftime("%Y-%m-%d") if fecha_vencimiento else "No vence"
    )

    save_payments(payments_df)
    save_users(users_df)


    estado_actual = payments_df.loc[
        payments_df["ID"] == payment_id,
        "Estado"
    ].values[0]

    if estado_actual == "Aprobado":
        print("⚠️ Este pago ya fue aprobado.")
        return
    
    log_action(
        actor_id=sesion["id"],
        rol=sesion["rol"],
        accion="APROBAR_PAGO",
        detalle=f"Pago ID {payment_id} aprobado para Usuario ID {user_id}"
    )

    log_payment(
        user_id=user_id,
        pago_id=payment_id,
        evento=f"PAGO_APROBADO por Admin ID {sesion['id']}",
        monto=float(pago["Monto"])
    )

    print(
    "✅ Pago registrado por S/ {monto}. "
    "Será revisado por un administrador."
    )

# ==============================
# RECHAZAR PAGO (SOLO ADMIN)
# ==============================

# ==============================
# RECHAZAR PAGO (SOLO ADMIN)
# ==============================

def reject_payment(payment_id, sesion):

    if sesion["rol"] != "Admin":
        print("⛔ Acción no permitida. Requiere rol ADMIN.")
        return

    payments_df = load_payments()

    if payment_id not in payments_df["ID"].values:
        print("Pago no encontrado.")
        return

    # 🧾 Asegurar columnas de auditoría
    if "Admin_ID" not in payments_df.columns:
        payments_df["Admin_ID"] = ""
    if "Fecha_procesado" not in payments_df.columns:
        payments_df["Fecha_procesado"] = ""

    pago = payments_df[payments_df["ID"] == payment_id].iloc[0]

    # 🔒 Validar estado
    if pago["Estado"] != "Pendiente":
        print(f"⛔ No se puede rechazar un pago en estado '{pago['Estado']}'")
        return

    payments_df.loc[payments_df["ID"] == payment_id, "Estado"] = "Rechazado"
    payments_df.loc[payments_df["ID"] == payment_id, "Admin_ID"] = str(sesion["id"])
    payments_df.loc[
        payments_df["ID"] == payment_id,
        "Fecha_procesado"
    ] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_payments(payments_df)

    user_id = int(pago["Usuario_ID"])

    log_action(
        actor_id=sesion["id"],
        rol=sesion["rol"],
        accion="RECHAZAR_PAGO",
        detalle=f"Pago ID {payment_id} rechazado"
    )

    log_payment(
        user_id=user_id,
        pago_id=payment_id,
        evento=f"PAGO_RECHAZADO por Admin ID {sesion['id']}",
        monto=float(pago["Monto"])
    )

    print("❌ Pago rechazado correctamente.")


# ==============================
# LISTAR TODOS LOS PAGOS (ADMIN)
# ==============================

def list_payments(sesion):

    if sesion["rol"] != "Admin":
        print("⛔ Acción no permitida. Requiere rol ADMIN.")
        return

    payments_df = load_payments()

    if payments_df.empty:
        print("No hay pagos registrados.")
        return

    print("\n===== LISTA DE PAGOS =====")
    print(payments_df)


# ==============================
# HISTORIAL DE PAGOS POR USUARIO
# ==============================

def list_payments_by_user(user_id, sesion):

    payments_df = load_payments()

    if sesion["rol"] != "Admin" and sesion["id"] != user_id:
        print("⛔ No puedes ver pagos de otro usuario.")
        return

    pagos_usuario = payments_df[
        payments_df["Usuario_ID"] == user_id
    ]

    if pagos_usuario.empty:
        print("No hay pagos registrados para este usuario.")
        return

    print("\n===== HISTORIAL DE PAGOS =====")
    print(pagos_usuario[["ID", "Fecha", "Monto", "Estado"]])


# ==============================
# 🧾 ASOCIAR COMPROBANTE A PAGO
# ==============================

def attach_receipt(payment_id, file_path):
    payments_df = load_payments()

    if "Comprobante" not in payments_df.columns:
        payments_df["Comprobante"] = ""

    # 🔧 SOLUCIÓN CLAVE: forzar tipo texto
    payments_df["Comprobante"] = payments_df["Comprobante"].astype("object")

    if payment_id not in payments_df["ID"].values:
        print("Pago no encontrado.")
        return False

    payments_df.loc[
        payments_df["ID"] == payment_id,
        "Comprobante"
    ] = file_path

    save_payments(payments_df)
    return True

#----------
# BACK END - HELPER
#---------
def get_payment_summary_by_user(user_id):
    payments_df = load_payments()

    if payments_df.empty:
        return {
            "aprobado": 0.0,
            "pendiente": 0.0,
            "rechazado": 0.0,
            "neto": 0.0
        }

    payments_df["Usuario_ID"] = payments_df["Usuario_ID"].astype(int)
    payments_df["Monto"] = payments_df["Monto"].astype(float)
    payments_df["Estado"] = payments_df["Estado"].astype(str)

    pagos = payments_df[payments_df["Usuario_ID"] == int(user_id)]

    if pagos.empty:
        return {
            "aprobado": 0.0,
            "pendiente": 0.0,
            "rechazado": 0.0,
            "neto": 0.0
        }

    aprobado = pagos[pagos["Estado"] == "Aprobado"]["Monto"].sum()
    pendiente = pagos[pagos["Estado"] == "Pendiente"]["Monto"].sum()
    rechazado = pagos[pagos["Estado"] == "Rechazado"]["Monto"].sum()

    return {
        "aprobado": float(aprobado),
        "pendiente": float(pendiente),
        "rechazado": float(rechazado),
        "neto": float(aprobado + pendiente)
    }