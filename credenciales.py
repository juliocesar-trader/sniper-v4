import os
import json
import telebot
from iqoptionapi.stable_api import IQ_Option

# 1. Carga de Variables de Entorno Seguras (Para IQ Option y Telegram)
IQ_USER = os.getenv("IQ_USER")
IQ_PASS = os.getenv("IQ_PASS")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_ID = os.getenv("TELEGRAM_ID")

# 2. Inicialización limpia del bot de Telegram
bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

def conectar_broker():
    """Establece y retorna la conexión limpia con el Broker"""
    print("💡 Iniciando conexión segura con IQ Option...")
    try:
        client = IQ_Option(IQ_USER, IQ_PASS)
        status, reason = client.connect()
        if status:
            print("🟢 Puente con IQ Option establecido con éxito.")
            return client
        else:
            print(f"❌ Error de autenticación en el Broker: {reason}")
            return None
    except Exception as e:
        print(f"❌ Error crítico en el módulo de conexión: {e}")
        return None

def obtener_json_credenciales_google():
    """Lee de forma local y segura el archivo JSON de Google para evitar fallas en Render"""
    ruta_json = "claves_google.json"
    
    if os.path.exists(ruta_json):
        try:
            with open(ruta_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error al procesar el archivo claves_google.json: {e}")
            return None
            
    print("❌ Error crítico: El archivo 'claves_google.json' no existe en la carpeta.")
    return None
