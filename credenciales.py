import os
import telebot
from iqoptionapi.stable_api import IQ_Option

# 1. Carga de Variables de Entorno Seguras
IQ_USER = os.getenv("IQ_USER")
IQ_PASS = os.getenv("IQ_PASS")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_ID = os.getenv("TELEGRAM_ID")

# 2. Inicialización del objeto de Telegram
bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True)

def conectar_broker():
    """Establece y retorna la conexión limpia con el Broker"""
    print("💡 Iniciando conexión segura con IQ Option...")
    try:
        client = IQ_Option(IQ_USER, IQ_PASS)
        status, reason = client.connect()
        if status:
            print("🟢 Puente con IQ Option establecido con éxito.")
            bot_telegram.send_message(TELEGRAM_ID, "🤖 ¡Puente Sniper V4 Online y verificado!")
            return client
        else:
            print(f"❌ Error de autenticación en el Broker: {reason}")
            return None
    except Exception as e:
        print(f"❌ Error crítico en el módulo de conexión: {e}")
        return None
