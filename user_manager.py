from database import load_users, save_users
from products import PRODUCTS
from datetime import datetime
from security import hash_password, verify_password
import pandas as pd

# ✅ IMPORT CORRECTO
from logger import log_access


# ==============================
# CREAR ADMIN INICIAL (AUTO)
# ==============================

def crear_admin_inicial():
    users_df = load_users()

    if not users_df[users_df["Rol"] == "Admin"].empty:
        return

    admin_password = "admin123"
    admin_hash = hash_password(admin_password)

    new_id = 1 if users_df.empty else users_df["ID"].max() + 1

    admin = {
        "ID": new_id,
        "Nombre": "Administrador",
        "Password": admin_hash,
        "Tipo_pago": "Unico",
        "Carpetas_compradas": "Sistema",
        "Carpetas_asignadas": 0,
        "Monto_base": 0,
        "Pago_confirmado": "Confirmado",
        "Fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Estado": "Activo",
        "Fecha_ultimo_pago": "",
        "Fecha_vencimiento": "No vence",
        "Rol": "Admin",
        "Debe_cambiar_password": 0,
        "Debe_elegir_plan": 0
    }

    df_admin = pd.DataFrame([admin])
    save_users(df_admin)

    print("\n🛡️ ADMIN INICIAL CREADO")
    print(f"🆔 ID: {new_id}")
    print("🔑 Password: admin123")


# ==============================
# LOGIN (CONSOLA)
# ==============================

def login():
    users_df = load_users()

    try:
        user_id = int(input("ID: "))
        password = input("Password: ")

        if user_id not in users_df["ID"].values:
            print("Usuario no encontrado.")
            log_access(
                user_id=user_id,
                nombre="DESCONOCIDO",
                rol="",
                resultado="LOGIN_FAIL",
                motivo="Usuario no existe"
            )
            return None

        user = users_df[users_df["ID"] == user_id].iloc[0]
        rol = user.get("Rol", "Usuario")

        if not verify_password(password, user["Password"]):
            print("Password incorrecto.")
            log_access(
                user_id=user["ID"],
                nombre=user["Nombre"],
                rol=rol,
                resultado="LOGIN_FAIL",
                motivo="Password incorrecto"
            )
            return None

        log_access(
            user_id=user["ID"],
            nombre=user["Nombre"],
            rol=rol,
            resultado="LOGIN_OK"
        )

        return {
            "id": user["ID"],
            "nombre": user["Nombre"],
            "rol": rol
        }

    except ValueError:
        print("Entrada inválida.")
        log_access(
            user_id="INVALID",
            nombre="INVALID",
            rol="",
            resultado="LOGIN_FAIL",
            motivo="Entrada inválida"
        )
        return None


# ==============================
# LOGIN (WEB)
# ==============================

def login_web(user_id, password):
    users_df = load_users()

    if users_df.empty:
        return None

    if "ID" in users_df.columns:
        users_df["ID"] = users_df["ID"].astype(int)

    try:
        user_id = int(user_id)

        if user_id not in users_df["ID"].values:
            log_access(
                user_id=user_id,
                nombre="DESCONOCIDO",
                rol="",
                resultado="LOGIN_FAIL",
                motivo="Usuario no existe (web)"
            )
            return None

        user = users_df[users_df["ID"] == user_id].iloc[0]
        rol = user.get("Rol", "Usuario")

        if not verify_password(password, user["Password"]):
            log_access(
                user_id=user["ID"],
                nombre=user["Nombre"],
                rol=rol,
                resultado="LOGIN_FAIL",
                motivo="Password incorrecto (web)"
            )
            return None

        log_access(
            user_id=user["ID"],
            nombre=user["Nombre"],
            rol=rol,
            resultado="LOGIN_OK (web)"
        )

        return {
            "id": user["ID"],
            "nombre": user["Nombre"],
            "rol": rol
        }

    except Exception:
        log_access(
            user_id="INVALID",
            nombre="INVALID",
            rol="",
            resultado="LOGIN_FAIL",
            motivo="Error en login web"
        )
        return None


# ==============================
# MOSTRAR CATÁLOGO COMPLETO
# ==============================

def mostrar_catalogo():
    print("\n===== CATÁLOGO DE CARPETAS =====")
    for producto in PRODUCTS.values():
        print("\n--------------------------------")
        print(f"Nombre: {producto['nombre']}")
        print(f"Precio Único: S/ {producto['precio']}")
        print(f"Descripción: {producto['descripcion']}")
        print(f"Link: {producto['link']}")


# ==============================
# MOSTRAR PRODUCTOS VENDIBLES
# ==============================

def mostrar_productos_vendibles():
    print("\n===== CARPETAS DISPONIBLES PARA COMPRA =====")
    for key, producto in PRODUCTS.items():
        if producto["vendible"]:
            print(f"{key}. {producto['nombre']} - S/ {producto['precio']}")


# ==============================
# CREAR USUARIO
# ==============================

def create_user():
    users_df = load_users()

    try:
        nombre = input("Nombre del usuario: ").strip()
        password = input("Password: ").strip()
        password_hash = hash_password(password)

        print("\nTipos de pago disponibles:")
        print("1. Semanal")
        print("2. Mensual")
        print("3. Único")

        tipo_opcion = input("Seleccione tipo de pago: ")
        tipo_pago = {"1": "Semanal", "2": "Mensual", "3": "Unico"}.get(tipo_opcion)

        if not tipo_pago:
            print("Tipo inválido.")
            return

        mostrar_productos_vendibles()
        seleccion = input("Seleccione carpetas (ej: 1,2): ")
        seleccion_ids = [int(x.strip()) for x in seleccion.split(",")]

        nombres = [PRODUCTS[s]["nombre"] for s in seleccion_ids]

        total = (
            1 if tipo_pago == "Semanal"
            else 3 if tipo_pago == "Mensual"
            else sum(PRODUCTS[s]["precio"] for s in seleccion_ids)
        )

        if users_df.empty or "ID" not in users_df.columns:
            new_id = 1
        else:
            new_id = int(users_df["ID"].max()) + 1
        nuevo_usuario = {
            "ID": new_id,
            "Nombre": nombre,
            "Password": password_hash,
            "Rol": "Usuario",
            "Tipo_pago": tipo_pago,
            "Carpetas_compradas": ", ".join(nombres),
            "Carpetas_asignadas": len(nombres),
            "Monto_base": total,
            "Pago_confirmado": "No",
            "Fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Estado": "Activo",
            "Fecha_ultimo_pago": "",
            "Fecha_vencimiento": ""
        }

        users_df = pd.concat([users_df, pd.DataFrame([nuevo_usuario])], ignore_index=True)
        save_users(users_df)

        print("\n✅ Usuario creado correctamente")
        print(f"🆔 ID asignado: {new_id}")
        print(f"💰 Total a pagar: S/ {total}")

    except Exception as e:
        print("Error:", e)


# ==============================
# LISTAR USUARIOS
# ==============================

def list_users():
    users_df = load_users()
    print(users_df)


# ==============================
# VER ESTADO DE SUSCRIPCIONES
# ==============================

def ver_estado_suscripciones():
    users_df = load_users()

    if users_df.empty:
        print("No hay usuarios registrados.")
        return

    hoy = datetime.now().date()
    print("\n===== ESTADO DE SUSCRIPCIONES =====")

    for _, user in users_df.iterrows():

        if user["Tipo_pago"] == "Unico":
            print(f"{user['Nombre']} -> Activo permanente")
            continue

        vencimiento = user["Fecha_vencimiento"]

        if not isinstance(vencimiento, str) or vencimiento.strip() == "":
            print(f"{user['Nombre']} -> Sin vencimiento")
            continue

        try:
            fecha_v = datetime.strptime(vencimiento, "%Y-%m-%d").date()
        except ValueError:
            print(f"{user['Nombre']} -> Fecha inválida")
            continue

        if hoy <= fecha_v:
            print(f"{user['Nombre']} -> Al día (vence {vencimiento})")
        else:
            print(f"{user['Nombre']} -> ❌ VENCIDO desde {vencimiento}")
#-------------------------------
# CREAR USUARIO EN WEB
#-------------------------------
def create_user_web(nombre, password, rol="Usuario"):
    users_df = load_users()

    password_hash = hash_password(password)

    new_id = 1 if users_df.empty else users_df["ID"].max() + 1

    nuevo_usuario = {
        "ID": new_id,
        "Nombre": nombre,
        "Password": password_hash,
        "Rol": rol,
        "Tipo_pago": "Mensual",
        "Carpetas_compradas": "",
        "Carpetas_asignadas": 0,
        "Monto_base": 0,
        "Pago_confirmado": "No",
        "Fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Estado": "Activo",
        "Fecha_ultimo_pago": "",
        "Fecha_vencimiento": "",
        "Debe_cambiar_password": 1,
        "Debe_elegir_plan": 1
    }

    users_df = pd.concat(
        [users_df, pd.DataFrame([nuevo_usuario])],
        ignore_index=True
    )

    save_users(users_df)

    return nuevo_usuario