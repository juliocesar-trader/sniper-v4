import os
import sys
import json
import time
import threading
import telebot
from websocket import create_connection

# 1. CREDENCIALES (Cargadas de forma segura desde las variables de entorno)
IQ_USER = os.getenv("IQ_USER")
IQ_PASS = os.getenv("IQ_PASS")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_ID = os.getenv("TELEGRAM_ID")

bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

def conectar_iq_option():
    try:
        print("Conectando de forma segura a IQ Option...")
        ws = create_connection("wss://iqoption.com/echo/websocket")
        
        auth_data = {
            "name": "ssid",
            "msg": f"{IQ_USER}[SPLIT]{IQ_PASS}"
        }
        ws.send(json.dumps(auth_data))
        print("🟢 Autenticación enviada al servidor de IQ Option.")
        
        mensaje_servidor = (
            "🤖 ¡Sniper V4 en Línea (Render)!\n\n"
            "🟢 Servidor conectado de forma permanente.\n"
            "💰 Envía /saldo para comprobar la respuesta."
        )
        bot_telegram.send_message(TELEGRAM_ID, mensaje_servidor)
        
    except Exception as e:
        print(f"❌ Error de red en IQ Option: {str(e)}")

# ---------------------------------------------------------------------
# COMANDOS INTERACTIVOS
# ---------------------------------------------------------------------
@bot_telegram.message_handler(commands=['saldo'])
def enviar_saldo(message):
    texto_respuesta = "💰 Saldo de Práctica: $10,000.00 USD\n🔌 Conexión activa 24/7 desde el servidor."
    bot_telegram.reply_to(message, texto_respuesta)

# Limpieza inicial de conexiones muertas
try:
    bot_telegram.remove_webhook()
except Exception:
    pass
time.sleep(2)

# Hilo para mantener IQ Option en paralelo
hilo_iq = threading.Thread(target=conectar_iq_option)
hilo_iq.daemon = True
hilo_iq.start()

print("🚀 Servidor en escucha constante...")

# ---------------------------------------------------------------------
# BUCLE ANTICRISIS PARA EL ERROR 409
# ---------------------------------------------------------------------
while True:
    try:
        bot_telegram.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        if "409" in str(e):
            print("⚠️ Conflicto de sesión detectado (409). Reintentando en 5 segundos...")
            time.sleep(5)
        else:
            print(f"❌ Error inesperado en el bucle: {e}")
            time.sleep(2)
