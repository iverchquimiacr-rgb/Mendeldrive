from database import load_users, save_users
from calculations import get_account_status


# ==============================
# ASIGNAR CARPETA (SOLO ADMIN)
# ==============================

def assign_folder(user_id, sesion):

    if sesion["rol"] != "Admin":
        print("⛔ Acción no permitida. Requiere rol ADMIN.")
        return

    users_df = load_users()

    if users_df.empty:
        print("No existen usuarios registrados.")
        return

    if user_id not in users_df["ID"].values:
        print("Usuario no encontrado.")
        return

    user = users_df[users_df["ID"] == user_id].iloc[0]

    # Verificar estado activo
    if user["Estado"] != "Activo":
        print("Usuario inactivo.")
        return

    # Verificar pago confirmado
    if user["Pago_confirmado"] != "Confirmado":
        print("El usuario no tiene pago confirmado.")
        return

    # Verificar saldo pendiente
    estado = get_account_status(user_id)

    if estado is None:
        print("Error al verificar estado financiero.")
        return

    if estado["SaldoPendiente"] > 0:
        print("El usuario aún tiene saldo pendiente.")
        return

    # Verificar límite de carpetas
    carpetas_actuales = user["Carpetas_asignadas"]

    if carpetas_actuales >= 3:
        print("El usuario ya tiene el máximo de 3 carpetas.")
        return

    # Asignar carpeta
    users_df.loc[
        users_df["ID"] == user_id,
        "Carpetas_asignadas"
    ] = carpetas_actuales + 1

    save_users(users_df)

    print("✅ Carpeta asignada correctamente.")
    print(f"📂 Total carpetas: {carpetas_actuales + 1}")