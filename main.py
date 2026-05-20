import os
import time
import threading
import csv
from flask import Flask

# IMPORTACIÓN DEL PUENTE SEGÚN TU ESTÁNDAR
from credenciales import bot_telegram, conectar_broker, TELEGRAM_ID

# ==============================================================================
# CONFIGURACIÓN DE BASE DE DATOS PERSISTENTE PARA LA IA
# ==============================================================================
ARCHIVO_HISTORIAL = "historial_operaciones.csv"

if not os.path.exists(ARCHIVO_HISTORIAL):
    with open(ARCHIVO_HISTORIAL, "w", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow([
            "timestamp", "divisa", "hora", "tipo_senal", 
            "precio_entrada", "precio_final", "resultado", 
            "rsi", "atr", "banda_sup", "banda_inf"
        ])

# ==============================================================================
# SERVIDOR WEB FLASK (PROVEEDOR DE LINEA DE VIDA PARA RENDER)
# ==============================================================================
app = Flask(__name__)
iq_client = None  

@app.route('/')
def home():
    global iq_client
    if iq_client and iq_client.check_connect():
        estado = "🟢 PUENTE OPERANDO - CONECTADO A IQ OPTION"
        try: saldo = f"${iq_client.get_balance():,.2f} USD"
        except: saldo = "Cargando..."
    else:
        estado = "❌ PUENTE CAÍDO O DESCONECTADO"
        saldo = "$0.00"
    
    return f"<h2>🚀 Sniper V4 Modularizado</h2><p><b>Estado:</b> {estado}</p><p><b>Saldo:</b> {saldo}</p>", 200

def ejecutar_servidor_web():
    puerto = int(os.environ.get("PORT", 10000))
    print(f"📡 Iniciando servidor Web de soporte en puerto {puerto}...")
    app.run(host="0.0.0.0", port=puerto, debug=False, use_reloader=False)

# ==============================================================================
# ESCÁNER DIRECTO DE MUESTRA (TEST FORZADO)
# ==============================================================================
def escanear_mercados():
    global iq_client
    print("🎯 MODO TEST ACTIVADO: Forzando señales cada 30 segundos...")
    
    # Intentamos enviar una alerta inicial de confirmación directo al arrancar
    try:
        bot_telegram.send_message(TELEGRAM_ID, "🚀 *Sistema de Alertas Forzadas Inicializado con Éxito*", parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Error crítico enviando mensaje de arranque inicial: {e}")

    while True:
        try:
            divisa = "EURUSD"
            precio_cierre = 1.08500
            rsi, atr, banda_sup, banda_inf = 50.0, 0.00012, 1.08600, 1.08400
            senal = "🟢 COMPRA (TEST DE CONEXIÓN) 📈"
            
            mensaje = f"🧪 *TEST FRANCOTIRADOR*\n\n💱 Divisa: {divisa}\n⚡ Operación: {senal}\n⏱️ Expiración: 1 Minuto"
            bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
            print("📬 Señal de prueba enviada a Telegram.")
            
            # Registrar simulación de forma asíncrona
            threading.Thread(
                target=simular_operacion, 
                args=(divisa, precio_cierre, senal, rsi, atr, banda_sup, banda_inf),
                daemon=True
            ).start()
            
        except Exception as e:
            print(f"⚠️ Error en bucle de escáner: {e}")
            
        time.sleep(30)

def simular_operacion(divisa, precio_entrada, tipo_senal, rsi, atr, banda_sup, banda_inf):
    time.sleep(5)
    try:
        hora_registro = time.strftime("%H:%M:%S")
        timestamp = int(time.time())
        with open(ARCHIVO_HISTORIAL, mode="a", newline="") as f:
            escritor = csv.writer(f)
            escritor.writerow([
                timestamp, divisa, hora_registro, "COMPRA",
                precio_entrada, precio_entrada + 0.00002, 1,
                round(rsi, 2), round(atr, 6), round(banda_sup, 6), round(banda_inf, 6)
            ])
        print("💾 Datos del test guardados en el historial CSV.")
    except Exception as e:
        print(f"Error registrando simulación: {e}")

# ==============================================================================
# MANEJADOR DE COMANDOS (BOT DE TELEGRAM)
# ==============================================================================
@bot_telegram.message_handler(commands=['saldo'])
def enviar_saldo(message):
    global iq_client
    print(f"📥 Comando /saldo recibido de {message.chat.id}")
    if iq_client and iq_client.check_connect():
        try:
            bot_telegram.reply_to(message, f"💰 Saldo de Práctica Real: ${iq_client.get_balance():,.2f} USD")
        except Exception as e:
            bot_telegram.reply_to(message, f"⚠️ Error leyendo saldo: {e}")
    else:
        bot_telegram.reply_to(message, "❌ Puente desconectado temporalmente del broker.")

# ==============================================================================
# FLUJO DE ARRANQUE SECUENCIAL REESTRUCTURADO
# ==============================================================================
if __name__ == "__main__":
    print("⚡ Iniciando orquestación secuencial Sniper V4...")
    
    # 1. Eliminar cualquier Webhook colgado de configuraciones previas
    try: 
        bot_telegram.remove_webhook(drop_pending_updates=True)
        time.sleep(1)
    except Exception as e: 
        print(f"Aviso de Webhook: {e}")

    # 2. Conectar al broker de inmediato en el hilo principal
    print("🔌 Conectando con IQ Option...")
    iq_client = conectar_broker()

    # 3. Lanzar el Servidor Web (Flask) en un hilo secundario aislado
    t_web = threading.Thread(target=ejecutar_servidor_web, daemon=True)
    t_web.start()
    time.sleep(2)

    # 4. Lanzar el escáner de mercados forzado en otro hilo secundario aislado
    t_escaner = threading.Thread(target=escanear_mercados, daemon=True)
    t_escaner.start()

    # 5. ANCLAR EL HILO PRINCIPAL AL POLLING DE TELEGRAM
    # Esto obliga a Render a mantener todo el script vivo y despierto
    print("🚀 Servidores acoplados. Activando escucha continua de Telegram (Polling)...")
    while True:
        try:
            bot_telegram.polling(none_stop=True, skip_pending_updates=True, timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"🔄 Reiniciando Polling de Telegram de forma automática por desconexión: {e}")
            time.sleep(5)
