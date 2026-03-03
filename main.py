from user_manager import (
    create_user,
    list_users,
    mostrar_catalogo,
    login,
    crear_admin_inicial,
    ver_estado_suscripciones
)

from payment_manager import (
    add_payment,
    approve_payment,
    reject_payment,
    list_payments,
    list_payments_by_user
)

from calculations import get_account_status
from folder_manager import assign_folder
from subscription_manager import actualizar_suscripciones


# ==============================
# CONTROL DE ROLES
# ==============================

def requiere_admin(sesion):
    if sesion["rol"] != "Admin":
        print("⛔ Acción no permitida. Requiere rol ADMIN.")
        return False
    return True


# ==============================
# REGISTRAR PAGO
# ==============================

def registrar_pago(sesion):
    try:
        monto = float(input("Monto a pagar: "))
        add_payment(sesion["id"], monto)
    except ValueError:
        print("Entrada inválida.")


# ==============================
# MOSTRAR ESTADO DE CUENTA
# ==============================

def mostrar_estado(sesion):
    estado = get_account_status(sesion["id"])

    if estado is None:
        print("Usuario no encontrado.")
        return

    print("\n===== ESTADO DE CUENTA =====")
    print(f"Monto Base: {estado['MontoBase']}")
    print(f"Total Pagado: {estado['TotalPagado']}")
    print(f"Saldo Pendiente: {estado['SaldoPendiente']}")


# ==============================
# MENÚ ADMIN
# ==============================

def menu_admin(sesion):
    while True:
        print("\n===== MENÚ ADMIN =====")
        print("1. Crear usuario")
        print("2. Registrar pago")
        print("3. Listar usuarios")
        print("4. Listar pagos")
        print("5. Mostrar catálogo")
        print("6. Aprobar pago")
        print("7. Rechazar pago")
        print("8. Ver estado de cuenta")
        print("9. Asignar carpeta")
        print("10. Ver estado de suscripciones")
        print("11. Ver historial de pagos de un usuario")
        print("12. Salir")

        opcion = input("Seleccione una opción: ")

        if opcion == "1":
            create_user()

        elif opcion == "2":
            registrar_pago(sesion)

        elif opcion == "3":
            list_users()

        elif opcion == "4":
            list_payments(sesion)

        elif opcion == "5":
            mostrar_catalogo()

        elif opcion == "6":
            payment_id = int(input("ID del pago: "))
            approve_payment(payment_id, sesion)

        elif opcion == "7":
            payment_id = int(input("ID del pago: "))
            reject_payment(payment_id, sesion)

        elif opcion == "8":
            mostrar_estado(sesion)

        elif opcion == "9":
            user_id = int(input("ID del usuario: "))
            assign_folder(user_id, sesion)

        elif opcion == "10":
            ver_estado_suscripciones()

        elif opcion == "11":
            user_id = int(input("ID del usuario: "))
            list_payments_by_user(user_id, sesion)

        elif opcion == "12":
            break

        else:
            print("Opción inválida.")


# ==============================
# MENÚ USUARIO
# ==============================

def menu_usuario(sesion):
    while True:
        print("\n===== MENÚ USUARIO =====")
        print("1. Registrar pago")
        print("2. Ver estado de cuenta")
        print("3. Ver historial de pagos")
        print("4. Mostrar catálogo")
        print("5. Salir")

        opcion = input("Seleccione una opción: ")

        if opcion == "1":
            registrar_pago(sesion)

        elif opcion == "2":
            mostrar_estado(sesion)

        elif opcion == "3":
            list_payments_by_user(sesion["id"], sesion)

        elif opcion == "4":
            mostrar_catalogo()

        elif opcion == "5":
            break

        else:
            print("Opción inválida.")


# ==============================
# MAIN
# ==============================

def main():
    crear_admin_inicial()
    actualizar_suscripciones()

    while True:
        print("\n===== SISTEMA =====")
        print("1. Crear cuenta")
        print("2. Iniciar sesión")
        print("3. Salir")

        opcion = input("Seleccione una opción: ")

        if opcion == "1":
            create_user()

        elif opcion == "2":
            sesion = login()

            if not sesion:
                continue

            print(f"\n✅ Bienvenido {sesion['nombre']} ({sesion['rol']})")

            if sesion["rol"] == "Admin":
                menu_admin(sesion)
            else:
                menu_usuario(sesion)

        elif opcion == "3":
            break

        else:
            print("Opción inválida.")


if __name__ == "__main__":
    main()