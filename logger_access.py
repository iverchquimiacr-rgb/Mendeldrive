import pandas as pd
from datetime import datetime
import os

ACCESS_LOG_FILE = "access_logs.csv"


def log_access(user_id, resultado, motivo="", rol=""):

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    nuevo_log = {
        "Fecha": fecha,
        "Usuario_ID": user_id,
        "Resultado": resultado,
        "Motivo": motivo,
        "Rol": rol
    }

    if os.path.exists(ACCESS_LOG_FILE):
        df = pd.read_csv(ACCESS_LOG_FILE)
    else:
        df = pd.DataFrame(columns=nuevo_log.keys())

    df = pd.concat([df, pd.DataFrame([nuevo_log])], ignore_index=True)
    df.to_csv(ACCESS_LOG_FILE, index=False)