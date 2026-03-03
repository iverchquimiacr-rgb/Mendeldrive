# security.py
from werkzeug.security import generate_password_hash, check_password_hash

def hash_password(password):
    """
    Genera un hash seguro para la contraseña.
    """
    return generate_password_hash(password)

def verify_password(password, hashed):
    """
    Verifica si la contraseña coincide con el hash.
    """
    return check_password_hash(hashed, password)