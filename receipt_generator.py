from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import os

UPLOAD_FOLDER = "uploads/comprobantes"


def generar_comprobante(codigo, nombre, monto, payment_id):

    from PIL import Image, ImageDraw, ImageFont
    import os
    from datetime import datetime

    carpeta = "static/comprobantes"
    os.makedirs(carpeta, exist_ok=True)

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")

    width = 800
    height = 400

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 40)
        font_text = ImageFont.truetype("arial.ttf", 24)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    draw.text((260, 40), "COMPROBANTE DE PAGO", fill="black", font=font_title)

    draw.text((80, 140), f"Codigo: {codigo}", fill="black", font=font_text)
    draw.text((80, 200), f"Usuario: {nombre}", fill="black", font=font_text)
    draw.text((80, 240), f"Monto: S/ {monto}", fill="black", font=font_text)
    draw.text((80, 280), f"Fecha: {fecha}", fill="black", font=font_text)
    draw.text((80, 320), f"ID Pago: {payment_id}", fill="black", font=font_text)

    filename = f"{codigo}.png"

    ruta = os.path.join(carpeta, filename)

    img.save(ruta, optimize=True, quality=70)

    return filename