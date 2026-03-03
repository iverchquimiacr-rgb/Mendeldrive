import pandas as pd
from datetime import datetime
import os


# ==============================
# CONFIGURACIÓN DE ARCHIVOS
# ==============================

ACCESS_LOG_FILE = "logs_access.csv"
ACTION_LOG_FILE = "logs_actions.csv"
PAYMENT_LOG_FILE = "logs_payments.csv"


# ==============================
# UTILIDAD BASE
# ==============================

def _append_log(file_path, data: dict):
    df_new = pd.DataFrame([data])

    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new

    df.to_csv(file_path, index=False)


# ==============================
# LOG DE ACCESOS (EXTENDIDO)
# ==============================

def log_access(
    user_id,
    nombre,
    rol,
    resultado="LOGIN_OK",
    motivo=""
):
    """
    Registra accesos al sistema.
    Compatible con llamadas antiguas y nuevas.
    """

    log = {
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "User_ID": user_id,
        "Nombre": nombre,
        "Rol": rol,
        "Resultado": resultado,
        "Motivo": motivo
    }

    _append_log(ACCESS_LOG_FILE, log)


# ==============================
# LOG DE ACCIONES
# ==============================

def log_action(user_id, rol, accion, detalle=""):
    log = {
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "User_ID": user_id,
        "Rol": rol,
        "Accion": accion,
        "Detalle": detalle
    }
    _append_log(ACTION_LOG_FILE, log)


# ==============================
# LOG DE PAGOS
# ==============================

def log_payment(user_id, pago_id, evento, monto=None):
    log = {
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "User_ID": user_id,
        "Pago_ID": pago_id,
        "Evento": evento,
        "Monto": monto
    }
    _append_log(PAYMENT_LOG_FILE, log)