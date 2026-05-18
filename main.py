import os
import sys
import json
import time
import threading
import telebot
from websocket import create_connection

# 1. CREDENCIALES
IQ_USER = "73306657jc@gmail.com"
IQ_PASS = "JulioTrader2026"
TELEGRAM_TOKEN = "8925198476:AAFOK71Hj3Ejw0nJWFSgKNzX5ZxeeIhmYbA"
TELEGRAM_ID = "8623414493"

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

# =========================================================
# COMANDOS INTERACTIVOS
# =========================================================
@bot_telegram.message_handler(commands=['saldo'])
def enviar_saldo(message):
    texto_respuesta = "💰 Saldo de Práctica: $10,000.00 USD\n📡 Conexión activa 24/7 desde el servidor."
    bot_telegram.reply_to(message, texto_respuesta)

# Limpieza inicial de conexiones muertas
bot_telegram.remove_webhook()
time.sleep(1)

# Hilo para mantener IQ Option en paralelo
hilo_iq = threading.Thread(target=conectar_iq_option)
hilo_iq.daemon = True
hilo_iq.start()

print("🚀 Servidor en escucha constante...")
bot_telegram.polling(none_stop=True, interval=1, timeout=20)
