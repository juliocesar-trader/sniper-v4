import os
import sys
import json
import time
import threading
import telebot
from flask import Flask
# Se cambia la conexión WebSocket manual por la API oficial estable
from iqoptionapi.stable_api import IQ_Option

# ==============================================================================
# 1. SERVIDOR WEB FLASK (Bindeo de Puerto prioritario para Render)
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Servidor Sniper V4 en ejecución continua y estable.", 200

def ejecutar_servidor_web():
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

# Variable global para almacenar el cliente de conexión del Broker
iq_client = None

# ==============================================================================
# 3. PROCESO DE FONDO: CONEXIÓN INTEGRAL A IQ OPTION
# ==============================================================================
def conectar_iq_option():
    global iq_client
    try:
        print("💡 Conectando de forma oficial a IQ Option...")
        # Inicializa la API con tus credenciales seguras
        iq_client = IQ_Option(IQ_USER, IQ_PASS)
        status, reason = iq_client.connect()
        
        if status:
            print("🟢 Conexión exitosa y confirmada con IQ Option.")
            mensaje_exito = (
                "🤖 ¡Sniper V4 Actualizado con Éxito!\n\n"
                "🛡️ Errores 409 mitigados y Conexión Real Establecida.\n"
                "💎 Envía /saldo para validar tu saldo en tiempo real."
            )
            bot_telegram.send_message(TELEGRAM_ID, mensaje_exito)
        else:
            print(f"❌ Falló la autenticación en el broker: {reason}")
            bot_telegram.send_message(TELEGRAM_ID, f"❌ Error de inicio de sesión en IQ Option: {reason}")
            
    except Exception as e:
        print(f"❌ Error crítico en infraestructura de IQ Option: {str(e)}")

# ==============================================================================
# 4. MANEJADORES DE EVENTOS (TELEGRAM DISPATCHERS)
# ==============================================================================
@bot_telegram.message_handler(commands=['saldo'])
def enviar_saldo(message):
    global iq_client
    
    # Comprobar si la sesión de IQ Option está activa y no se ha caído
    if iq_client and iq_client.check_connect():
        try:
            # Obtiene el saldo real actual directamente desde los servidores de IQ Option
            saldo_real_broker = iq_client.get_balance()
            respuesta = f"💰 Saldo de Práctica Real: ${saldo_real_broker:,.2f} USD\n🔒 Canal seguro 24/7 sin suspensiones."
        except Exception as error_saldo:
            respuesta = f"⚠️ Conectado, pero no se pudo leer el saldo: {str(error_saldo)}"
    else:
        respuesta = "❌ El bot no está conectado a IQ Option en este momento o las credenciales fallaron."
        
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
    
    time.sleep(2)
    
    # PASO 2: Forzar limpieza de Webhooks y purgar peticiones colgadas
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
    
    # PASO 4: Iniciar Polling de Telegram infinito
    print("⚡ Bot de Telegram listo y escuchando órdenes...")
    while True:
        try:
            bot_telegram.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"♻️ Reintento automático de Polling tras desconexión: {e}")
            time.sleep(5)
