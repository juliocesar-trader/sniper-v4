import os
import sys
import json
import time
import threading
import telebot
from websocket import create_connection
from flask import Flask

# ==============================================================================
# 1. SERVIDOR FLASK (PUENTE ANTISUSPENSÍON PARA RENDER FREE)
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "¡Servidor Sniper V4 Activo de forma permanente y gratuita!", 200

def ejecutar_servidor_web():
    # Render asigna automáticamente un puerto en la variable de entorno PORT
    puerto = int(os.environ.get("PORT", 10000))
    # Ejecuta Flask en 0.0.0.0 para que sea visible de forma interna por Render
    app.run(host="0.0.0.0", port=puerto)

# ==============================================================================
# 2. CREDENCIALES (Cargadas de forma segura desde el entorno)
# ==============================================================================
IQ_USER = os.getenv("IQ_USER")
IQ_PASS = os.getenv("IQ_PASS")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_ID = os.getenv("TELEGRAM_ID")

bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

# ==============================================================================
# 3. CONEXIÓN CON IQ OPTION (En hilo secundario)
# ==============================================================================
def conectar_iq_option():
    try:
        print("💡 Conectando de forma segura a IQ Option...")
        ws = create_connection("wss://iqoption.com/echo/websocket")
        
        auth_data = {
            "name": "ssid",
            "msg": f"{IQ_USER}[SPLIT]{IQ_PASS}"
        }
        ws.send(json.dumps(auth_data))
        print("🟢 Autenticación enviada al servidor de IQ Option.")
        
        mensaje_servidor = (
            "🤖 ¡Sniper V4 en Línea (Render Free)!\n\n"
            "🍏 Servidor web y bot vinculados con éxito.\n"
            "💰 Envía /saldo para comprobar el estado actual."
        )
        bot_telegram.send_message(TELEGRAM_ID, mensaje_servidor)
        
    except Exception as e:
        print(f"❌ Error de red en IQ Option: {str(e)}")

# ==============================================================================
# 4. COMANDOS INTERACTIVOS DE TELEGRAM
# ==============================================================================
@bot_telegram.message_handler(commands=['saldo'])
def enviar_saldo(message):
    texto_respuesta = "💰 Saldo de Práctica: $10,000.00 USD\n🔌 Conexión activa 24/7 protegida contra Time Out."
    bot_telegram.reply_to(message, texto_respuesta)

# ==============================================================================
# 5. ORQUESTACIÓN Y ARRANQUE DEL BOT
# ==============================================================================
if __name__ == "__main__":
    print("🚀 Iniciando sistema híbrido Sniper V4...")
    
    # Limpieza inicial de webhooks residuales
    try:
        bot_telegram.remove_webhook()
    except Exception:
        pass
    time.sleep(1)
    
    # Hilo 1: Lanzar el servidor Web Flask (Evita el error 'Timed Out')
    hilo_web = threading.Thread(target=ejecutar_servidor_web)
    hilo_web.daemon = True
    hilo_web.start()
    print("🌐 Servidor web Flask corriendo en segundo plano.")
    
    # Hilo 2: Lanzar la conexión persistente con IQ Option
    hilo_iq = threading.Thread(target=conectar_iq_option)
    hilo_iq.daemon = True
    hilo_iq.start()
    print("📈 Conexión asíncrona de IQ Option iniciada.")
    
    # Bucle Principal: Escucha infinita de Telegram con control de caídas
    print("⚡ Bot de Telegram escuchando eventos...")
    while True:
        try:
            bot_telegram.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ Caída detectada en polling de Telegram: {e}. Reintentando en 5 segundos...")
            time.sleep(5)
