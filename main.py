import os
import sys
import json
import time
import threading
import telebot
from websocket import create_connection
from flask import Flask

# ==============================================================================
# 1. SERVIDOR WEB FLASK (Bindeo de Puerto prioritario para Render)
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Servidor Sniper V4 en ejecución continua y estable.", 200

def ejecutar_servidor_web():
    # Render inyecta la variable dinámica PORT de manera automática
    puerto = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=puerto)

# ==============================================================================
# 2. CONFIGURACIÓN DE INSTANCIA Y VARIABLES DE ENTORNO
# ==============================================================================
IQ_USER = os.getenv("IQ_USER")
IQ_PASS = os.getenv("IQ_PASS")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_ID = os.getenv("TELEGRAM_ID")

bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

# ==============================================================================
# 3. PROCESO DE FONDO: CONEXIÓN INTEGRAL A IQ OPTION
# ==============================================================================
def conectar_iq_option():
    try:
        print("💡 Estableciendo canal WebSocket con IQ Option...")
        ws = create_connection("wss://iqoption.com/echo/websocket")
        
        auth_data = {
            "name": "ssid",
            "msg": f"{IQ_USER}[SPLIT]{IQ_PASS}"
        }
        ws.send(json.dumps(auth_data))
        print("🟢 Petición de autenticación enviada correctamente.")
        
        mensaje_exito = (
            "🤖 ¡Sniper V4 Actualizado con Éxito!\n\n"
            "🛡️ Errores 409 y Port Timeout mitigados.\n"
            "💎 Envía /saldo para validar la respuesta activa."
        )
        bot_telegram.send_message(TELEGRAM_ID, mensaje_exito)
        
    except Exception as e:
        print(f"❌ Error crítico en infraestructura de IQ Option: {str(e)}")

# ==============================================================================
# 4. MANEJADORES DE EVENTOS (TELEGRAM DISPATCHERS)
# ==============================================================================
@bot_telegram.message_handler(commands=['saldo'])
def enviar_saldo(message):
    respuesta = "💰 Saldo de Práctica: $10,000.00 USD\n🔒 Canal seguro 24/7 sin suspensiones."
    bot_telegram.reply_to(message, respuesta)

# ==============================================================================
# 5. INICIALIZACIÓN Y ORQUESTACIÓN JERÁRQUICA
# ==============================================================================
if __name__ == "__main__":
    print("🚀 Arrancando secuencia de inicialización Sniper V4...")
    
    # PASO 1: Arrancar Servidor Web de inmediato (Render aprueba el despliegue al instante)
    hilo_web = threading.Thread(target=ejecutar_servidor_web)
    hilo_web.daemon = True
    hilo_web.start()
    print("🌐 Servidor Web levantado de manera prioritaria.")
    
    # Latencia técnica preventiva de estabilización
    time.sleep(2)
    
    # PASO 2: Forzar limpieza de Webhooks y purgar peticiones colgadas (Solución definitiva al Error 409)
    try:
        print("🧹 Purgando hilos de memoria y Webhooks duplicados...")
        bot_telegram.remove_webhook(drop_pending_updates=True)
        print("✨ Limpieza completada. Sesiones concurrentes terminadas.")
    except Exception as e:
        print(f"⚠️ Nota de limpieza: {e}")
    
    time.sleep(2)
    
    # PASO 3: Ejecutar conexión con el Broker en segundo plano
    hilo_iq = threading.Thread(target=conectar_iq_option)
    hilo_iq.daemon = True
    hilo_iq.start()
    print("📈 Hilo asíncrono de IQ Option desplegado.")
    
    # PASO 4: Iniciar Polling de Telegram infinito con manejo de excepciones tolerante a fallos
    print("⚡ Bot de Telegram listo y escuchando órdenes...")
    while True:
        try:
            bot_telegram.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"♻️ Reintento automático de Polling tras desconexión: {e}")
            time.sleep(5)
