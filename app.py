from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from user_manager import (
    login_web,
    create_user_web,
    crear_admin_inicial
)
from datetime import datetime
from calculations import get_account_status
from payment_manager import (
    add_payment,
    approve_payment,
    reject_payment,
    attach_receipt,
    get_payment_summary_by_user,
    get_monthly_income
)
from database import load_payments, get_connection, initialize_database, load_users, save_users
from products import PRODUCTS
from folder_manager import assign_folder
from receipt_manager import create_receipt, get_all_receipts
from receipt_generator import generar_comprobante
import os
from werkzeug.utils import secure_filename
from utils import generar_password_temporal
from security import hash_password
import json
from functools import wraps
import sqlite3  # 🔹 necesario para initialize_database
import requests
# ===========================
# 🔹 Inicialización de la app
# ===========================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key")

# ===========================
# 🔹 Inicialización de la base y admin
# ===========================
print("DEBUG: app iniciando")
initialize_database()   # 🔹 Asegura que las tablas existan
crear_admin_inicial()
print("DEBUG: admin inicial verificado")   # 🔹 Crea admin inicial si no existe


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("rol") != "Admin":
            return redirect(url_for("dashboard"))

        return f(*args, **kwargs)

    return wrapper

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow}


# ==============================
# FIX GLOBAL PARA USERS (OBLIGATORIO)
# ==============================

def load_users_safe():
    users_df = load_users()

    # ID siempre int
    if "ID" in users_df.columns:
        users_df["ID"] = users_df["ID"].astype(int)

    # Flags SIEMPRE int (0 / 1)
    for col in ["Debe_cambiar_password", "Debe_elegir_plan"]:
        if col not in users_df.columns:
            users_df[col] = 0
        else:
            users_df[col] = users_df[col].fillna(0).astype(int)

    # ❌ NO GUARDAR AQUÍ
    return users_df

# ==============================
# LIMITAR REGISTROS POR IP
# ==============================

def puede_registrar_ip(ip):

    try:

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        SELECT COUNT(*)
        FROM registro_ips
        WHERE ip = %s
        AND fecha > NOW() - INTERVAL '7 days'
        """, (ip,))

        count = cur.fetchone()[0]

        conn.close()

        return count < 2

    except Exception as e:

        print("Error verificando IP:", e)
        return True

# ==============================
# GUARDAR IP DE REGISTRO
# ==============================

def registrar_ip(ip):

    try:

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO registro_ips (ip, fecha)
        VALUES (%s, NOW())
        """, (ip,))

        conn.commit()
        conn.close()

    except Exception as e:

        print("Error guardando IP:", e)

#------------------
# PROBAR
#-------------------
@app.route("/debug_users")
def debug_users():
    users_df = load_users()
    return users_df.to_html()

@app.route("/test")
def test():
    return "APP FUNCIONANDO"

# ==============================
# CONFIGURACIÓN DE SUBIDAS
# ==============================

UPLOAD_FOLDER = "uploads/comprobantes"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ==============================
# LOGIN
# ==============================

@app.route("/", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        try:
            user_id = int(request.form["user_id"])
            password = request.form["password"]

            # 1️⃣ Validar credenciales
            print("DEBUG login intentando:", user_id, password)

            resultado = login_web(user_id, password)

            print("DEBUG resultado login:", resultado)

            if not resultado:
                return render_template("login.html", error="Credenciales incorrectas")

            # 2️⃣ Cargar usuario
            users_df = load_users_safe()
            user_df = users_df[users_df["ID"] == user_id]

            if user_df.empty:
                return render_template("login.html", error="Usuario no encontrado")

            user = user_df.iloc[0]

            # 3️⃣ Guardar sesión
            session["user_id"] = int(user["ID"])
            session["nombre"] = str(user["Nombre"])
            session["rol"] = str(user["Rol"])

            # 🆕 Guardar si el usuario aún no tiene plan
            session["sin_plan"] = int(user["Carpetas_asignadas"]) == 0

            # 4️⃣ Forzar cambio de password si aplica
            if user.get("Debe_cambiar_password", False):
                session["forzar_cambio_password"] = True
                return redirect(url_for("cambiar_password"))

            # 🆕 Ahora SIEMPRE va al dashboard
            return redirect(url_for("dashboard"))

        except ValueError:
            error = "ID inválido"

    return render_template("login.html", error=error)
# ==============================
# REGISTRO PÚBLICO
# ==============================

@app.route("/registro", methods=["GET", "POST"])
def registro():

    error = None

    if request.method == "POST":

        ip = request.remote_addr

        if not puede_registrar_ip(ip):

            error = "Solo se permiten 2 registros por semana desde la misma red"

            return render_template(
                "registro.html",
                error=error,
                turnstile_site_key=os.environ.get("TURNSTILE_SITE_KEY")
            )

        nombre = request.form.get("nombre")
        password = request.form.get("password")

        # =====================
        # VALIDAR TURNSTILE
        # =====================

        turnstile_response = request.form.get("cf-turnstile-response")

        verify = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": os.environ.get("TURNSTILE_SECRET_KEY"),
                "response": turnstile_response
            }
        ).json()

        if not verify.get("success"):
            error = "Verificación captcha fallida"

            return render_template(
                "registro.html",
                error=error,
                turnstile_site_key=os.environ.get("TURNSTILE_SITE_KEY")
            )

        # =====================
        # VALIDACIONES
        # =====================

        if not nombre or not password:
            error = "Todos los campos son obligatorios"
            return render_template(
                "registro.html",
                error=error,
                turnstile_site_key=os.environ.get("TURNSTILE_SITE_KEY")
            )

        users_df = load_users_safe()

        # verificar si el nombre ya existe
        if nombre.lower() in users_df["Nombre"].str.lower().values:
            error = "El usuario ya existe"
            return render_template(
                "registro.html",
                error=error,
                turnstile_site_key=os.environ.get("TURNSTILE_SITE_KEY")
            )

        try:

            # crear usuario
            create_user_web(
                nombre=nombre,
                password=password,
                rol="Usuario"
            )

            # volver a cargar usuarios para obtener el ID creado
            users_df = load_users_safe()

            nuevo_usuario = users_df[
                users_df["Nombre"].str.lower() == nombre.lower()
            ].iloc[-1]

            user_id = int(nuevo_usuario["ID"])

            registrar_ip(ip)

            return redirect(url_for("registro_exitoso", user_id=user_id))

        except Exception as e:

            print("ERROR REGISTRO:", e)
            error = "No se pudo crear la cuenta"

    return render_template(
        "registro.html",
        error=error,
        turnstile_site_key=os.environ.get("TURNSTILE_SITE_KEY")
    )

# ==============================
# REGISTRO EXITOSO
# ==============================

@app.route("/registro_exitoso/<int:user_id>")
def registro_exitoso(user_id):

    return render_template(
        "registro_exitoso.html",
        user_id=user_id
    )

#--------------------
# RESET 
#--------------------
@app.route("/admin/system/reset_database")
def admin_reset_database():

    # Verificar sesión
    if "usuario_id" not in session:
        return "No autorizado", 403

    # Verificar rol admin
    if session.get("rol") != "Admin":
        return "Acceso solo para administradores", 403

    try:
        conn = get_connection()
        cur = conn.cursor()

        print("ADMIN RESET DATABASE iniciado")

        # Borrar datos
        cur.execute("TRUNCATE TABLE pagos RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE TABLE usuarios RESTART IDENTITY CASCADE")

        conn.commit()
        conn.close()

        # Recrear admin inicial
        crear_admin_inicial()

        print("ADMIN RESET DATABASE completado")

        return "Base de datos reiniciada correctamente"

    except Exception as e:
        print("Error en reset_database:", e)
        return f"Error: {e}", 500
# ==============================
# DASHBOARD
# ==============================

@app.route("/dashboard")
@login_required
def dashboard():

    if session.get("rol") == "Admin":
        return render_template(
            "dashboard_admin.html",
            nombre=session.get("nombre")
        )

    return render_template(
        "dashboard_user.html",
        nombre=session.get("nombre"),
        sin_plan=session.get("sin_plan", False)
    )


# ==============================
# 🟢 CATÁLOGO
# ==============================

@app.route("/catalogo")
def catalogo():
    if "user_id" not in session:
        return redirect(url_for("login"))

    productos = []

    for pid, p in PRODUCTS.items():
        productos.append({
            "id": pid,
            "nombre": p["nombre"],
            "precio": p["precio"],
            "descripcion": p["descripcion"],
            "vendible": p["vendible"],
            "link": p["link"]
        })

    return render_template(
        "catalogo.html",
        productos=productos,
        nombre=session["nombre"],
        rol=session["rol"]
    )

#-------------------------------
# INGRESOS
#------------------------------

@app.route("/admin/ingresos")
@admin_required
def admin_ingresos():

    if "rol" not in session or session["rol"] != "Admin":
        return redirect(url_for("login"))

    ingresos = get_monthly_income()

    labels = list(ingresos.keys())
    valores = list(ingresos.values())

    total = sum(valores)

    return render_template(
        "admin_ingresos.html",
        labels=labels,
        valores=valores,
        total=total
)
# ==============================
# ESTADO DE CUENTA
# ==============================

@app.route("/estado_cuenta")
def estado_cuenta():
    if "user_id" not in session:
        return redirect(url_for("login"))
        # Si no tiene plan, mostrar estado vacío
    if session.get("sin_plan"):
        return render_template(
            "estado_cuenta.html",
            saldo_pendiente=0,
            total_pagado=0
        )


    estado = get_account_status(session["user_id"])

    if estado is None:
        return "Usuario no encontrado"

    return render_template(
        "estado_cuenta.html",
        estado=estado,
        nombre=session["nombre"]
    )

# ==============================
# 🔴 ADMIN — LISTAR USUARIOS
# ==============================

@app.route("/admin/usuarios")
@admin_required
def admin_usuarios():

    if "user_id" not in session or session["rol"] != "Admin":
        return redirect(url_for("login"))

    users_df = load_users()
    pagos_df = load_payments()

    # 🔧 FIX CRÍTICO: asegurar que ID sea int
    users_df["ID"] = users_df["ID"].astype(int)

    # =========================
    # 🔎 BUSCADOR
    # =========================

    buscar = request.args.get("buscar")

    if buscar:

        buscar = buscar.strip().lower()

        users_df = users_df[
            users_df["Nombre"].str.lower().str.contains(buscar, na=False)
            |
            users_df["ID"].astype(str).str.contains(buscar)
        ]

    # =========================
    # CREAR LISTA USUARIOS
    # =========================

    usuarios = []

    for _, u in users_df.iterrows():

        user_id = int(u["ID"])

        estado = get_account_status(user_id)

        usuarios.append({
            "id": user_id,
            "nombre": str(u["Nombre"]),
            "estado": str(u["Estado"]),
            "tipo_pago": str(u["Tipo_pago"]),
            "carpetas": int(u["Carpetas_asignadas"]),
            "saldo": float(estado["SaldoPendiente"]) if estado else 0.0
        })

    return render_template(
        "usuarios_admin.html",
        usuarios=usuarios,
        nombre=str(session["nombre"])
    )

# ==============================
# 🔴 ADMIN — PERFIL DE USUARIO
# ==============================

@app.route("/admin/usuario/<int:user_id>")
@admin_required
def admin_ver_usuario(user_id):
    # 🔐 Seguridad
    if "user_id" not in session or session["rol"] != "Admin":
        return redirect(url_for("login"))

    # 📥 Cargar datos
    users_df = load_users()

    # 🔧 Normalizar tipos
    users_df["ID"] = users_df["ID"].astype(int)
    users_df["Carpetas_asignadas"] = users_df["Carpetas_asignadas"].fillna(0).astype(int)
    users_df["Monto_base"] = users_df["Monto_base"].fillna(0).astype(float)

    # 👤 Usuario
    user_df = users_df[users_df["ID"] == int(user_id)]
    if user_df.empty:
        return "Usuario no encontrado"

    user = user_df.iloc[0]

    # 💰 Estado de cuenta
    estado_cuenta = get_account_status(int(user_id)) or {
        "TotalPagado": 0,
        "SaldoPendiente": 0
    }

    perfil_data = {
        "id": int(user["ID"]),
        "nombre": str(user["Nombre"]),
        "rol": str(user["Rol"]),
        "tipo_pago": str(user["Tipo_pago"]),
        "estado": str(user["Estado"]),
        "carpetas_asignadas": int(user["Carpetas_asignadas"]),
        "carpetas_compradas": str(user["Carpetas_compradas"]),
        "monto_base": float(user["Monto_base"]),
        "total_pagado": float(estado_cuenta["TotalPagado"]),
        "saldo_pendiente": float(estado_cuenta["SaldoPendiente"])
    }

    return render_template(
        "perfil_admin.html",
        perfil=perfil_data,
        nombre=str(session["nombre"])
    )

# ==============================
# 🔴 ADMIN — PAGOS DE UN USUARIO
# ==============================

@app.route("/admin/usuario/<int:user_id>/pagos")
@admin_required
def admin_pagos_usuario(user_id):
    # 🔐 Seguridad
    if "user_id" not in session or session["rol"] != "Admin":
        return redirect(url_for("login"))

    # 📥 Cargar datos
    pagos_df = load_payments()
    users_df = load_users()

    # 🔧 NORMALIZAR IDs (FIX CRÍTICO)
    users_df["ID"] = users_df["ID"].astype(int)
    pagos_df["Usuario_ID"] = pagos_df["Usuario_ID"].astype(int)
    pagos_df["ID"] = pagos_df["ID"].astype(int)
    pagos_df["Monto"] = pagos_df["Monto"].astype(float)

    # 👤 Usuario
    user_df = users_df[users_df["ID"] == int(user_id)]
    if user_df.empty:
        return "Usuario no encontrado"

    nombre_usuario = str(user_df.iloc[0]["Nombre"])

    # 💳 Pagos del usuario
    pagos_usuario = pagos_df[pagos_df["Usuario_ID"] == int(user_id)]

    pagos = []

    # 🔢 Totales
    total_aprobado = 0.0
    total_pendiente = 0.0
    total_rechazado = 0.0

    cant_aprobados = 0
    cant_pendientes = 0
    cant_rechazados = 0

    for _, p in pagos_usuario.iterrows():
        estado = str(p["Estado"])
        monto = float(p["Monto"])

        if estado == "Aprobado":
            total_aprobado += monto
            cant_aprobados += 1
        elif estado == "Pendiente":
            total_pendiente += monto
            cant_pendientes += 1
        elif estado == "Rechazado":
            total_rechazado += monto
            cant_rechazados += 1

        pagos.append({
            "id": int(p["ID"]),
            "fecha": str(p["Fecha"]),
            "monto": float(p["Monto"]),
            "estado": estado,
            "comprobante": str(p.get("Comprobante", ""))
        })

    resumen = {
        "total_aprobado": float(total_aprobado),
        "total_pendiente": float(total_pendiente),
        "total_rechazado": float(total_rechazado),
        "cant_aprobados": int(cant_aprobados),
        "cant_pendientes": int(cant_pendientes),
        "cant_rechazados": int(cant_rechazados)
    }

    return render_template(
        "pagos_usuario_admin.html",
        pagos=pagos,
        resumen=resumen,
        usuario=nombre_usuario,
        user_id=int(user_id),
        nombre=str(session["nombre"])
    )
# ==============================
# 🔴 ADMIN — RESET CONTRASEÑA
# ==============================

@app.route("/admin/usuario/<int:user_id>/reset_password")
@admin_required
def admin_reset_password(user_id):
    if "user_id" not in session or session["rol"] != "Admin":
        return redirect(url_for("login"))

    users_df = load_users()
    idx = users_df.index[users_df["ID"] == user_id]

    if idx.empty:
        return "Usuario no encontrado"

    # 🔐 Generar password temporal
    nueva_password = generar_password_temporal()

    # 🔒 Hashear
    password_hash = hash_password(nueva_password)

    # 💾 Guardar
    users_df.at[idx[0], "Password"] = password_hash

    # ✅ Activar usuario y permitir cambio de contraseña si es necesario
    users_df.loc[idx, "Debe_cambiar_password"] = 1   # fuerza al usuario a cambiar password al ingresar
    users_df.loc[idx, "Estado"] = "Activo"          # activa al usuario para que pueda loguearse

    save_users(users_df)

    return render_template(
        "password_reset_admin.html",
        password=nueva_password,
        user_id=user_id,
        nombre=session["nombre"]
    )

# ==============================
# 🔴 ADMIN — TABLA COMPROBANTES
# ==============================

@app.route("/admin/comprobantes")
@admin_required
def admin_comprobantes():

    buscar = request.args.get("buscar", "").lower()

    archivos = []

    if os.path.exists(UPLOAD_FOLDER):

        for f in os.listdir(UPLOAD_FOLDER):

            if not f.endswith(".png"):
                continue

            nombre_archivo = f.replace(".png","")

            partes = nombre_archivo.split("-")

            if len(partes) >= 3:

                year = partes[0]
                usuario = partes[1]
                codigo_id = partes[2]

            else:

                year = ""
                usuario = ""
                codigo_id = ""

            if buscar and buscar not in usuario.lower():
                continue

            archivos.append({
                "codigo": nombre_archivo,
                "usuario": usuario.replace("_"," "),
                "year": year,
                "id": codigo_id,
                "archivo": f,
                "usuario_id": usuario
            })

    archivos.sort(key=lambda x: x["codigo"], reverse=True)

    return render_template(
        "comprobantes_admin.html",
        comprobantes=archivos,
        nombre=session["nombre"],
        buscar=buscar
    )

# ==============================
# 👤 USUARIO CAMBIA CONTRASEÑA
# ==============================
@app.route("/cambiar_password", methods=["GET", "POST"])
def cambiar_password():
    if "user_id" not in session or not session.get("forzar_cambio_password"):
        return redirect(url_for("login"))

    if request.method == "POST":
        nueva = request.form["password"]

        # 🔹 Cargar usuarios correctamente
        users_df = load_users_safe()

        # 🔹 Obtener índice del usuario
        idx_list = users_df.index[users_df["ID"] == int(session["user_id"])]

        if idx_list.empty:
            return "Usuario no encontrado"

        idx = idx_list[0]

        # 🔐 Actualizar password
        users_df.at[idx, "Password"] = hash_password(nueva)

        # 🔒 Quitar flag (SIEMPRE INT)
        users_df.at[idx, "Debe_cambiar_password"] = 0

        save_users(users_df)

        # 🔓 Limpiar sesión
        session.pop("forzar_cambio_password", None)

        return redirect(url_for("dashboard"))

    return render_template("cambiar_password.html")

# ==============================
# 👤 PERFIL DE USUARIO (FIXED)
# ==============================

@app.route("/perfil")
def perfil():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # 🔐 Carga segura (ID como int)
    users_df = load_users_safe()

    user_df = users_df[users_df["ID"] == int(session["user_id"])]

    if user_df.empty:
        return "Usuario no encontrado"

    user = user_df.iloc[0]

    estado_cuenta = get_account_status(int(session["user_id"]))

    # 🔹 Carpetas disponibles
    carpetas_disponibles = []
    for pid, p in PRODUCTS.items():
        carpetas_disponibles.append({
            "nombre": p["nombre"],
            "link": p["link"]
        })

    perfil_data = {
        "id": int(user["ID"]),
        "nombre": user["Nombre"],
        "rol": user["Rol"],
        "tipo_pago": user["Tipo_pago"],
        "estado": user["Estado"],
        "carpetas_asignadas": int(user["Carpetas_asignadas"]),

        # ⚠️ Texto, NO convertir a int
        "carpetas_compradas": user["Carpetas_compradas"],

        "monto_base": float(user["Monto_base"]),
        "total_pagado": estado_cuenta["TotalPagado"] if estado_cuenta else 0,
        "saldo_pendiente": estado_cuenta["SaldoPendiente"] if estado_cuenta else 0,
        "carpetas": carpetas_disponibles
    }
    # ==============================
    # 💳 RESUMEN DE PAGOS (UX PERFIL)
    # ==============================

    pagos_df = load_payments()

    # 🔧 FIX CRÍTICO: normalizar tipos
    if not pagos_df.empty:
        pagos_df["Usuario_ID"] = pagos_df["Usuario_ID"].astype(int)
        pagos_df["Monto"] = pagos_df["Monto"].astype(float)
        pagos_df["Estado"] = pagos_df["Estado"].astype(str)

    pagos_usuario = pagos_df[
        pagos_df["Usuario_ID"] == int(session["user_id"])
    ]

    total_aprobado = float(
        pagos_usuario[pagos_usuario["Estado"] == "Aprobado"]["Monto"].sum()
    ) if not pagos_usuario.empty else 0.0

    total_pendiente = float(
        pagos_usuario[pagos_usuario["Estado"] == "Pendiente"]["Monto"].sum()
    ) if not pagos_usuario.empty else 0.0

    total_rechazado = float(
        pagos_usuario[pagos_usuario["Estado"] == "Rechazado"]["Monto"].sum()
    ) if not pagos_usuario.empty else 0.0

    resumen = {
        "aprobado": total_aprobado,
        "pendiente": total_pendiente,
        "rechazado": total_rechazado,
        # 💡 Neto incluye adelantos (pagos negativos)
        "neto": total_aprobado + total_pendiente
    }
    return render_template(
    "perfil.html",
    perfil=perfil_data,
    nombre=session["nombre"],
    rol=session["rol"],
    resumen=resumen
)
# ==============================
# REGISTRAR PAGO
# ==============================

@app.route("/registrar_pago", methods=["GET", "POST"])
def registrar_pago():
    if "user_id" not in session:
        return redirect(url_for("login"))
    # 🔒 Bloquear si no tiene plan
    if session.get("sin_plan"):
        return render_template(
            "accion_bloqueada.html",
            mensaje="Debes elegir un plan antes de registrar pagos."
        )
    mensaje = None
    comprobante_url = None
    archivo_comprobante = None

    if request.method == "POST":
        try:
            monto = float(request.form["monto"])
            add_payment(session["user_id"], monto)

            # generar codigo de comprobante
            codigo = create_receipt(
                session["user_id"],
                session["nombre"],
                monto
            )

            # obtener ultimo pago
            pagos_df = load_payments()
            ultimo_pago = pagos_df[
                pagos_df["Usuario_ID"] == session["user_id"]
            ].iloc[-1]
            payment_id = int(ultimo_pago["ID"])

            # generar imagen comprobante
            archivo_comprobante = generar_comprobante(
                codigo,
                session["nombre"],
                monto,
                payment_id
            )

            # asociar comprobante al pago
            attach_receipt(payment_id, archivo_comprobante)

            # URL para previsualizar
            comprobante_url = url_for(
                "static",
                filename=f"comprobantes/{archivo_comprobante}"
            )

            mensaje = "Pago registrado correctamente. Comprobante generado."

        except ValueError:
            mensaje = "Monto inválido"

    return render_template(
        "registrar_pago.html",
        nombre=session["nombre"],
        mensaje=mensaje,
        comprobante_url=comprobante_url,
        archivo_comprobante=archivo_comprobante
    )
# ==============================
# 🧾 SUBIR COMPROBANTE ASOCIADO A PAGO
# ==============================

@app.route("/subir_comprobante", methods=["GET", "POST"])
def subir_comprobante():

    if "user_id" not in session:
        return redirect(url_for("login"))

    # 🔒 Bloquear si no tiene plan
    if session.get("sin_plan"):
        return render_template(
            "accion_bloqueada.html",
            mensaje="Debes elegir un plan antes de subir comprobantes."
        )
    mensaje = None
    pagos_df = load_payments()

    # 🔒 asegurar tipo correcto
    pagos_df["ID"] = pagos_df["ID"].astype(int)

    pagos_pendientes = pagos_df[
        (pagos_df["Usuario_ID"] == session["user_id"]) &
        (pagos_df["Estado"] == "Pendiente")
    ]

    if request.method == "POST":
        try:
            payment_id = int(request.form["payment_id"])
        except (ValueError, KeyError):
            mensaje = "ID de pago inválido"
            return render_template(
                "subir_comprobante.html",
                nombre=session["nombre"],
                mensaje=mensaje,
                pagos=pagos_pendientes.to_dict("records")
            )

        # ==============================
        # VALIDACIÓN DE SEGURIDAD
        # ==============================

        if payment_id not in pagos_pendientes["ID"].values:
            mensaje = "Pago no válido o no pertenece a este usuario"
            return render_template(
                "subir_comprobante.html",
                nombre=session["nombre"],
                mensaje=mensaje,
                pagos=pagos_pendientes.to_dict("records")
            )

        # ==============================

        if "archivo" not in request.files:
            mensaje = "No se envió ningún archivo"
        else:
            archivo = request.files["archivo"]

            if archivo.filename == "":
                mensaje = "Archivo no seleccionado"

            elif archivo and allowed_file(archivo.filename):

                filename = secure_filename(archivo.filename)

                # nombre único del archivo
                nombre_final = f"user_{session['user_id']}_pago_{payment_id}_{filename}"

                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

                ruta = os.path.join(app.config["UPLOAD_FOLDER"], nombre_final)

                archivo.save(ruta)

                # guardar nombre del archivo en la base de datos
                attach_receipt(payment_id, nombre_final)

                mensaje = "Comprobante asociado correctamente al pago"

            else:
                mensaje = "Formato no permitido"

    return render_template(
        "subir_comprobante.html",
        nombre=session["nombre"],
        mensaje=mensaje,
        pagos=pagos_pendientes.to_dict("records")
    )

# ==============================
# 🔵 HISTORIAL DE PAGOS (USUARIO)
# ==============================
@app.route("/mis_pagos")
def mis_pagos():

    if "user_id" not in session:
        return redirect(url_for("login"))

    pagos_df = load_payments()

    pagos_df["ID"] = pagos_df["ID"].astype(int)
    pagos_df["Usuario_ID"] = pagos_df["Usuario_ID"].astype(int)

    pagos_usuario = pagos_df[
        pagos_df["Usuario_ID"] == session["user_id"]
    ]

    # 🔎 BUSCADOR

    buscar = request.args.get("buscar")

    if buscar:

        buscar = buscar.strip()

        if buscar.isdigit():

            pagos_usuario = pagos_usuario[
                pagos_usuario["ID"] == int(buscar)
            ]

    pagos = []

    for _, pago in pagos_usuario.iterrows():

        pagos.append({
            "id": int(pago["ID"]),
            "fecha": str(pago["Fecha"]),
            "monto": float(pago["Monto"]),
            "estado": str(pago["Estado"]),
            "comprobante": str(pago.get("Comprobante", ""))
        })

    return render_template(
        "mis_pagos.html",
        pagos=pagos,
        nombre=session["nombre"]
    )


# ==============================
# 🔴 ADMIN — LISTAR PAGOS
# ==============================
@app.route("/admin/pagos")
@admin_required
def admin_pagos():

    if "user_id" not in session or session["rol"] != "Admin":
        return redirect(url_for("login"))

    pagos_df = load_payments()
    users_df = load_users()

    # 🔧 NORMALIZAR IDS
    pagos_df["ID"] = pagos_df["ID"].astype(int)
    pagos_df["Usuario_ID"] = pagos_df["Usuario_ID"].astype(int)
    users_df["ID"] = users_df["ID"].astype(int)

    # =========================
    # 🔎 BUSCAR POR ID
    # =========================

    buscar = request.args.get("buscar")

    if buscar:

        buscar = buscar.strip()

        if buscar.isdigit():
            pagos_df = pagos_df[
                pagos_df["ID"] == int(buscar)
            ]

    # =========================
    # CREAR LISTA PAGOS
    # =========================

    pagos = []

    for _, pago in pagos_df.iterrows():

        user = users_df[
            users_df["ID"] == pago["Usuario_ID"]
        ].iloc[0]

        pagos.append({
            "id": int(pago["ID"]),
            "usuario": str(user["Nombre"]),
            "usuario_id": int(user["ID"]),
            "monto": float(pago["Monto"]),
            "fecha": str(pago["Fecha"]),
            "estado": str(pago["Estado"]),
            "comprobante": str(pago.get("Comprobante", ""))
        })

    return render_template(
        "pagos_admin.html",
        pagos=pagos,
        nombre=session["nombre"]
    )


# ==============================
# 🔴 ADMIN — APROBAR / RECHAZAR
# ==============================

@app.route("/admin/aprobar/<int:payment_id>")
def aprobar_pago_web(payment_id):

    if "user_id" not in session or session["rol"] != "Admin":
        return redirect(url_for("login"))

    pagos_df = load_payments()
    pago = pagos_df[pagos_df["ID"] == payment_id]

    # 🔎 Solo verificamos que el pago exista
    if pago.empty:
        return "❌ Pago no encontrado"

    sesion = {
        "id": session["user_id"],
        "rol": session["rol"]
    }

    # 1️⃣ Aprobar pago
    approve_payment(payment_id, sesion)

    # 2️⃣ Intentar asignar carpeta automáticamente
    user_id = int(pago.iloc[0]["Usuario_ID"])
    assign_folder(user_id, sesion)

    return redirect(url_for("admin_pagos"))


@app.route("/admin/rechazar/<int:payment_id>")
def rechazar_pago_web(payment_id):

    if "user_id" not in session or session["rol"] != "Admin":
        return redirect(url_for("login"))

    sesion = {
        "id": session["user_id"],
        "rol": session["rol"]
    }

    reject_payment(payment_id, sesion)

    return redirect(url_for("admin_pagos"))

# ==============================
# 🔴 VER COMPROBANTES
# ==============================

@app.route("/admin/comprobantes/<int:user_id>")
def ver_comprobantes(user_id):
    if "user_id" not in session or session["rol"] != "Admin":
        return redirect(url_for("login"))

    archivos = []

    if os.path.exists(UPLOAD_FOLDER):
        for f in os.listdir(UPLOAD_FOLDER):
            if f.startswith(f"user_{user_id}_"):
                archivos.append(f)

    return render_template(
        "ver_comprobantes.html",
        archivos=archivos,
        user_id=user_id
    )


@app.route("/uploads/comprobantes/<path:filename>")
def descargar_comprobante(filename):

    if "user_id" not in session:
        return redirect(url_for("login"))

    # admin puede ver cualquier comprobante
    if session.get("rol") == "Admin":
        return send_from_directory(UPLOAD_FOLDER, filename)

    # usuario solo puede ver sus archivos
    if filename.startswith(f"user_{session['user_id']}_"):
        return send_from_directory(UPLOAD_FOLDER, filename)

    return redirect(url_for("dashboard"))
#=============================
# ELIMINAR COMPROBANTE
#=============================

@app.route("/admin/eliminar_comprobante/<int:comp_id>", methods=["POST"])
@admin_required
def eliminar_comprobante(comp_id):

    conn = get_connection()
    cur = conn.cursor()

    # obtener archivo desde pagos
    cur.execute(
        "SELECT comprobante FROM pagos WHERE id = %s",
        (comp_id,)
    )
    row = cur.fetchone()

    if row and row[0]:

        archivo = row[0]

        ruta = os.path.join("static/comprobantes", archivo)

        if os.path.exists(ruta):
            os.remove(ruta)

    # quitar referencia del pago
    cur.execute(
        "UPDATE pagos SET comprobante = NULL WHERE id = %s",
        (comp_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/admin/comprobantes")

#=============================
# MIS COMPROBANTES (USUARIO)
#=============================

@app.route("/mis_comprobantes")
@login_required
def mis_comprobantes():

    user_id = session["user_id"]

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, fecha, comprobante
        FROM pagos
        WHERE user_id = %s
        AND comprobante IS NOT NULL
        ORDER BY fecha DESC
    """, (user_id,))

    rows = cur.fetchall()

    comprobantes = []

    for r in rows:
        comprobantes.append({
            "id": r[0],
            "fecha": r[1],
            "archivo": r[2]
        })

    cur.close()
    conn.close()

    return render_template(
        "mis_comprobantes.html",
        comprobantes=comprobantes,
        nombre=session.get("nombre")
    )

#=============================
# ELIMINAR PAGO
#=============================

@app.route("/admin/eliminar_pago/<int:pago_id>", methods=["POST"])
@admin_required
def eliminar_pago(pago_id):

    conn = get_connection()
    cur = conn.cursor()

    # buscar comprobante
    cur.execute(
        "SELECT comprobante FROM pagos WHERE id = %s",
        (pago_id,)
    )

    row = cur.fetchone()

    if row and row[0]:

        ruta = os.path.join("static/comprobantes", row[0])

        if os.path.exists(ruta):
            os.remove(ruta)

    # eliminar pago
    cur.execute(
        "DELETE FROM pagos WHERE id = %s",
        (pago_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/admin/pagos")
#=============================
# ELIMINAR USUARIO
#=============================

@app.route("/admin/eliminar_usuario/<int:user_id>", methods=["POST"])
@admin_required
def eliminar_usuario(user_id):

    # no borrar al admin logueado
    if user_id == session.get("user_id"):
        return redirect("/admin/usuarios")

    conn = get_connection()
    cur = conn.cursor()

    # verificar rol
    cur.execute(
        "SELECT rol FROM usuarios WHERE id = %s",
        (user_id,)
    )

    user = cur.fetchone()

    if user and user[0] == "Admin":
        conn.close()
        return redirect("/admin/usuarios")

    # obtener comprobantes de pagos
    cur.execute(
        "SELECT comprobante FROM pagos WHERE usuario_id = %s",
        (user_id,)
    )

    comprobantes = cur.fetchall()

    for c in comprobantes:

        if c[0]:

            ruta = os.path.join("static/comprobantes", c[0])

            if os.path.exists(ruta):
                os.remove(ruta)

    # eliminar pagos
    cur.execute(
        "DELETE FROM pagos WHERE usuario_id = %s",
        (user_id,)
    )

    # eliminar usuario
    cur.execute(
        "DELETE FROM usuarios WHERE id = %s",
        (user_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/admin/usuarios")
# ==============================
# CREAR USUARIO EN WEB
# ==============================

@app.route("/crear_usuario", methods=["GET", "POST"])
def crear_usuario():

    if not requiere_admin_web():
        return redirect("/dashboard")

    if request.method == "POST":
        nombre = request.form["nombre"]
        password = request.form["password"]
        rol = request.form.get("rol", "Usuario")

        create_user_web(nombre, password, rol)

        return redirect("/dashboard")

    return render_template("crear_usuario.html")

def requiere_admin_web():
    if "rol" not in session or session["rol"] != "Admin":
        return False
    return True
#-------------------------------
# SELECCIONAR PLANES
#-------------------------------

@app.route("/seleccionar_planes", methods=["GET", "POST"])
def seleccionar_planes():

    if "user_id" not in session:
        return redirect(url_for("login"))

    users_df = load_users_safe()
    user_id = session["user_id"]

    user_df = users_df[users_df["ID"] == user_id]
    if user_df.empty:
        return redirect(url_for("login"))

    user = user_df.iloc[0]

    # ⛔ No permitir reingreso
    if int(user["Carpetas_asignadas"]) > 0:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        tipo_pago = request.form.get("tipo_pago")
        seleccion = request.form.getlist("carpetas")

        # 🚨 Validaciones
        if tipo_pago not in ["Semanal", "Mensual", "Unico"]:
            return render_template(
                "seleccionar_planes.html",
                productos=PRODUCTS,
                error="Debes seleccionar un tipo de pago"
            )

        if len(seleccion) == 0 or len(seleccion) > 3:
            return render_template(
                "seleccionar_planes.html",
                productos=PRODUCTS,
                error="Debes seleccionar entre 1 y 3 carpetas"
            )

        nombres = []
        total = 0

        for key in seleccion:
            producto = PRODUCTS.get(int(key))
            if producto:
                nombres.append(producto["nombre"])

                # 💰 SOLO SUMA SI ES PAGO ÚNICO
                if tipo_pago == "Unico":
                    total += producto["precio"]

        # 💳 Montos fijos
        # CAMBIAR PRECIOS SEMANAL MENSUAL MODIFICAR COSTO
        if tipo_pago == "Semanal":
            total = 1.5
        elif tipo_pago == "Mensual":
            total = 5

        idx = user_df.index[0]

        users_df.at[idx, "Tipo_pago"] = tipo_pago
        users_df.at[idx, "Carpetas_compradas"] = ", ".join(nombres)
        users_df.at[idx, "Carpetas_asignadas"] = len(nombres)
        users_df.at[idx, "Monto_base"] = total
        users_df.at[idx, "Pago_confirmado"] = "No"

        save_users(users_df)

        return redirect(url_for("dashboard"))

    return render_template(
        "seleccionar_planes.html",
        productos=PRODUCTS
    )

# ==============================
# LOGOUT
# ==============================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
