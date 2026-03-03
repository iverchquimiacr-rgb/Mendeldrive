import pandas as pd
from datetime import datetime
import os


def log_action(actor_id, rol, accion, detalle):
    archivo = "logs_actions.csv"

    registro = {
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Actor_ID": actor_id,
        "Rol": rol,
        "Accion": accion,
        "Detalle": detalle
    }

    df = pd.DataFrame([registro])

    if os.path.exists(archivo):
        df.to_csv(archivo, mode="a", header=False, index=False)
    else:
        df.to_csv(archivo, index=False)