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
import os
from werkzeug.utils import secure_filename
from utils import generar_password_temporal
from security import hash_password
import json
from functools import wraps
import sqlite3  # 🔹 necesario para initialize_database

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

            print("DEBUG login intentando:", user_id, password)

            # 1️⃣ Validar credenciales
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

            # 3️⃣ Guardar sesión (VERSIÓN SEGURA)
            session.clear()   # 🔹 importante para evitar sesiones viejas

            session["usuario_id"] = int(user["ID"])
            session["nombre"] = str(user["Nombre"])
            session["rol"] = str(user["Rol"]).strip()   # 🔹 evita errores por espacios

            print("DEBUG SESSION LOGIN:", dict(session))

            # 4️⃣ Forzar cambio de password si aplica
            if user.get("Debe_cambiar_password", False):
                session["forzar_cambio_password"] = True
                return redirect(url_for("cambiar_password"))

            # 5️⃣ Si no tiene carpetas
            if int(user["Carpetas_asignadas"]) == 0:
                return redirect(url_for("seleccionar_planes"))

            return redirect(url_for("dashboard"))

        except ValueError:
            error = "ID inválido"

    return render_template("login.html", error=error)

#--------------------
# RESET 
#--------------------
@app.route("/admin/system/reset_database")
def admin_reset_database():

    print("DEBUG SESSION RESET:", dict(session))

    # 1️⃣ Verificar sesión
    if "usuario_id" not in session:
        return "No autorizado", 403

    # 2️⃣ Verificar rol admin
    if str(session.get("rol", "")).strip() != "Admin":
        return "Acceso solo para administradores", 403

    # 3️⃣ Confirmación extra para evitar resets accidentales
    if request.args.get("confirm") != "YES":
        return "Agrega ?confirm=YES para confirmar el reset"

    conn = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        print("ADMIN RESET DATABASE iniciado")

        # 4️⃣ Limpiar tablas
        cur.execute("TRUNCATE TABLE pagos RESTART IDENTITY CASCADE;")
        cur.execute("TRUNCATE TABLE usuarios RESTART IDENTITY CASCADE;")

        conn.commit()

        print("Tablas truncadas correctamente")

    except Exception as e:
        if conn:
            conn.rollback()
        print("Error en reset_database:", e)
        return f"Error: {e}", 500

    finally:
        if conn:
            conn.close()

    # 5️⃣ Recrear admin inicial
    try:
        crear_admin_inicial()
        print("Admin inicial recreado")
    except Exception as e:
        print("Error creando admin inicial:", e)
        return f"Error recreando admin: {e}", 500

    print("ADMIN RESET DATABASE completado")

    return "Base de datos reiniciada correctamente"

# ==============================
# DASHBOARD
# ==============================

@app.route("/dashboard")
@login_required
def dashboard():

    if session["rol"] == "Admin":
        return render_template("dashboard_admin.html", nombre=session["nombre"])
    else:
        return render_template("dashboard_user.html", nombre=session["nombre"])


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

    usuarios = []

    for _, u in users_df.iterrows():
        user_id = int(u["ID"])

        estado = get_account_status(user_id)

        usuarios.append({
            "id": user_id,                                 # int puro
            "nombre": str(u["Nombre"]),                    # str puro
            "estado": str(u["Estado"]),                    # str puro
            "tipo_pago": str(u["Tipo_pago"]),              # str puro
            "carpetas": int(u["Carpetas_asignadas"]),      # int puro
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

        return redirect(url_for("seleccionar_planes"))

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

    mensaje = None

    if request.method == "POST":
        try:
            monto = float(request.form["monto"])
            add_payment(session["user_id"], monto)
            mensaje = "Pago registrado correctamente. Ahora sube tu comprobante."
        except ValueError:
            mensaje = "Monto inválido"

    return render_template(
        "registrar_pago.html",
        nombre=session["nombre"],
        mensaje=mensaje
    )


# ==============================
# 🧾 SUBIR COMPROBANTE ASOCIADO A PAGO
# ==============================

@app.route("/subir_comprobante", methods=["GET", "POST"])
def subir_comprobante():
    if "user_id" not in session:
        return redirect(url_for("login"))

    mensaje = None
    pagos_df = load_payments()

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

                # IMPORTANTE: guardar solo el nombre del archivo
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

    pagos_usuario = pagos_df[
        pagos_df["Usuario_ID"] == session["user_id"]
    ]

    pagos = []

    for _, pago in pagos_usuario.iterrows():
        pagos.append({
            "id": int(pago["ID"]),
            "fecha": pago["Fecha"],
            "monto": pago["Monto"],
            "estado": pago["Estado"],
            "comprobante": pago.get("Comprobante", "")
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

    pagos = []

    for _, pago in pagos_df.iterrows():
        user = users_df[users_df["ID"] == pago["Usuario_ID"]].iloc[0]
        pagos.append({
            "id": int(pago["ID"]),
            "usuario": user["Nombre"],
            "usuario_id": int(user["ID"]),
            "monto": pago["Monto"],
            "fecha": pago["Fecha"],
            "estado": pago["Estado"],
            "comprobante": pago.get("Comprobante", "")
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

    if pago.empty or not pago.iloc[0].get("Comprobante"):
        return "❌ No se puede aprobar un pago sin comprobante"

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
            total = 4

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
