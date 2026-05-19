import os
import sys
import json
import time
import threading
import telebot
from flask import Flask
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
iq_client = None

# Base de datos en memoria para el aprendizaje y optimización del bot
# Guarda estructura: {(divisa, hora): {"ganadas": 0, "perdidas": 0}}
HISTORIAL_SENALES = {}

# ==============================================================================
# 3. MÓDULO MATEMÁTICO: INDICADORES TÉCNICOS Y FILTROS FRANCOTIRADOR
# ==============================================================================
def calcular_indicadores(velas):
    """Calcula EMA, Bandas de Bollinger, RSI y ATR sobre una lista de velas"""
    cierres = [v['close'] for v in velas]
    altos = [v['max'] for v in velas]
    bajos = [v['min'] for v in velas]
    
    # 1. EMA (Media Móvil Exponencial) - Periodo 100
    periodo_ema = 100
    k = 2 / (periodo_ema + 1)
    ema = cierres[0]
    for c in cierres[1:]:
        ema = (c * k) + (ema * (1 - k))
        
    # 2. Bandas de Bollinger (Periodo 20, Desviación 2)
    ultimas_20 = cierres[-20:]
    sma_20 = sum(ultimas_20) / 20
    varianza = sum((x - sma_20) ** 2 for x in ultimas_20) / 20
    desviacion = varianza ** 0.5
    banda_sup = sma_20 + (2 * desviacion)
    banda_inf = sma_20 - (2 * desviacion)
    
    # 3. RSI (Índice de Fuerza Relativa) - Periodo 14
    ganancias = 0
    perdidas = 0
    for i in range(len(cierres)-14, len(cierres)):
        cambio = cierres[i] - cierres[i-1]
        if cambio > 0: ganancias += cambio
        else: perdidas += abs(cambio)
    rs = (ganancias / 14) / ((perdidas / 14) + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    
    # 4. ATR (Average True Range) - Medidor de Volatilidad (Periodo 14)
    tr_tot = 0
    for i in range(len(velas)-14, len(velas)):
        h_l = altos[i] - bajos[i]
        h_pc = abs(altos[i] - cierres[i-1])
        l_pc = abs(bajos[i] - cierres[i-1])
        tr_tot += max(h_l, h_pc, l_pc)
    atr = tr_tot / 14
    
    return ema, banda_sup, banda_inf, rsi, atr

# ==============================================================================
# 4. PROCESO DE MONITOREO DINÁMICO EN TIEMPO REAL
# ==============================================================================
def escanear_mercados():
    global iq_client
    # Lista de divisas principales a escanear de manera simultánea
    divisas = ["EURUSD", "GBPUSD", "EURJPY", "AUDUSD"]
    
    print("🎯 Francotirador activado. Escaneando divisas...")
    
    while True:
        if iq_client and iq_client.check_connect():
            hora_actual = time.strftime("%H:%M")
            
            # Filtro de Noticias / Horario de alta volatilidad impredecible
            # (Evita operar en aperturas bruscas o momentos conflictivos)
            if "12:30" <= hora_actual <= "13:30":
                time.sleep(60)
                continue
                
            for divisa in divisas:
                try:
                    # Filtro de Payout Mínimo (Mínimo 80%)
                    payouts = iq_client.get_all_profit()
                    payout = payouts.get(divisa, {}).get("turbo", 0)
                    if payout < 80:
                        continue
                        
                    # Obtener las últimas 110 velas de 1 minuto (60 segundos)
                    velas = iq_client.get_candles(divisa, 60, 110, time.time())
                    if not velas or len(velas) < 100:
                        continue
                        
                    ema, banda_sup, banda_inf, rsi, atr = calcular_indicadores(velas)
                    
                    ultima_vela = velas[-1]
                    precio_cierre = ultima_vela['close']
                    precio_apertura = ultima_vela['open']
                    tamaño_vela = abs(precio_cierre - precio_apertura)
                    
                    # Filtro Inteligente: Optimización por Base de Datos de Aprendizaje
                    clave_optimizacion = (divisa, hora_actual[:2]) # Agrupado por Hora
                    estadistica = HISTORIAL_SENALES.get(clave_optimizacion, {"ganadas": 0, "perdidas": 0})
                    totales = estadistica["ganadas"] + estadistica["perdidas"]
                    
                    # Si el registro demuestra que este par a esta hora pierde más del 50%, se bloquea
                    if totales > 4 and (estadistica["ganadas"] / totales) < 0.50:
                        continue
                    
                    # Filtro de Vela de Fuerza (Evita entrar si la vela es anormalmente grande)
                    if tamaño_vela > (atr * 2.5):
                        continue
                        
                    # --- COMPROBACIÓN DE DISPARO ---
                    senal = None
                    
                    # CONDICIÓN DE COMPRA (CALL): Tendencia alcista + Agotamiento abajo
                    if precio_cierre > ema and precio_cierre <= banda_inf and rsi < 25:
                        senal = "🟢 COMPRA (CALL) 📈"
                        
                    # CONDICIÓN DE VENTA (PUT): Tendencia bajista + Agotamiento arriba
                    elif precio_cierre < ema and precio_cierre >= banda_sup and rsi > 75:
                        senal = "🔴 VENTA (PUT) 📉"
                        
                    if senal:
                        # Enviar Alerta Inmediata a Telegram
                        mensaje = (
                            f"🎯 *¡SEÑAL FRANCOTIRADOR!*\n\n"
                            f"💱 Divisa: {divisa}\n"
                            f"⚡ Operación: {senal}\n"
                            f"⏱️ Expiración: 1 Minuto\n"
                            f"📊 Payout Activo: {payout}%\n"
                            f"🛡️ Filtros integrados: ATR y EMA pasados con éxito."
                        )
                        bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
                        
                        # Iniciar hilo de simulación para registrar efectividad y aprender del resultado
                        threading.Thread(target=simular_operacion, args=(divisa, precio_cierre, senal, clave_optimizacion)).start()
                        
                except Exception as e:
                    print(f"⚠️ Alerta menor en escaneo de {divisa}: {e}")
                    
        time.sleep(10) # Frecuencia de escaneo preventivo rápido

def simular_operacion(divisa, precio_entrada, tipo_senal, clave_optimizacion):
    """Simula el tiempo de expiración y guarda el resultado en la base de datos de aprendizaje"""
    global iq_client
    time.sleep(62) # Espera a que termine el minuto de la operación
    try:
        velas = iq_client.get_candles(divisa, 60, 1, time.time())
        precio_final = velas[-1]['close']
        
        ganó = False
        if "COMPRA" in tipo_senal and precio_final > precio_entrada: ganó = True
        elif "VENTA" in tipo_senal and precio_final < precio_entrada: ganó = True
        
        if clave_optimizacion not in HISTORIAL_SENALES:
            HISTORIAL_SENALES[clave_optimizacion] = {"ganadas": 0, "perdidas": 0}
            
        if ganó:
            HISTORIAL_SENALES[clave_optimizacion]["ganadas"] += 1
            print(f"🤖 Simulación Exitosa para {divisa}. Registrada como Ganada (ITM).")
        else:
            HISTORIAL_SENALES[clave_optimizacion]["perdidas"] += 1
            print(f"🤖 Simulación Fallida para {divisa}. Registrada como Perdida (OTM).")
            
    except Exception as e:
        print(f"No se pudo completar la simulación: {e}")

# ==============================================================================
# 5. CONEXIÓN AL BROKER IQ OPTION
# ==============================================================================
def conectar_iq_option():
    global iq_client
    try:
        print("💡 Conectando de forma oficial a IQ Option...")
        iq_client = IQ_Option(IQ_USER, IQ_PASS)
        status, reason = iq_client.connect()
        
        if status:
            print("🟢 Conexión exitosa y confirmed con IQ Option.")
            mensaje_exito = (
                "🤖 ¡Sniper V4 Online!\n\n"
                "🛡️ Estrategia de Triple Confirmación y Filtro ATR Activos.\n"
                "💎 El bot ya está rastreando el mercado en segundo plano."
            )
            bot_telegram.send_message(TELEGRAM_ID, mensaje_exito)
            
            # Lanzar el escáner de divisas de inmediato en un hilo de fondo
            hilo_escaner = threading.Thread(target=escanear_mercados)
            hilo_escaner.daemon = True
            hilo_escaner.start()
        else:
            print(f"❌ Falló la autenticación en el broker: {reason}")
            
    except Exception as e:
        print(f"❌ Error crítico en infraestructura de IQ Option: {str(e)}")

# ==============================================================================
# 6. MANEJADORES DE EVENTOS (TELEGRAM DISPATCHERS)
# ==============================================================================
@bot_telegram.message_handler(commands=['saldo'])
def enviar_saldo(message):
    global iq_client
    if iq_client and iq_client.check_connect():
        try:
            saldo_real_broker = iq_client.get_balance()
            respuesta = f"💰 Saldo de Práctica Real: ${saldo_real_broker:,.2f} USD\n🔒 Canal seguro 24/7 sin suspensiones."
        except Exception as error_saldo:
            respuesta = f"⚠️ Conectado, pero no se pudo leer el saldo: {str(error_saldo)}"
    else:
        respuesta = "❌ El bot no está conectado a IQ Option en este momento."
    bot_telegram.reply_to(message, respuesta)

# ==============================================================================
# 7. INICIALIZACIÓN Y ORQUESTACIÓN JERÁRQUICA (Sistema Anti-Choques Integrado)
# ==============================================================================
if __name__ == "__main__":
    print("🚀 Arrancando secuencia de inicialización Sniper V4...")
    
    hilo_web = threading.Thread(target=ejecutar_servidor_web)
    hilo_web.daemon = True
    hilo_web.start()
    print("🌐 Servidor Web levantado de manera prioritaria.")
    
    time.sleep(2)
    
    try:
        print("🧹 Purgando hilos de memoria y Webhooks duplicados...")
        bot_telegram.remove_webhook(drop_pending_updates=True)
    except Exception as e:
        print(f"⚠️ Nota de limpieza: {e}")
    
    time.sleep(2)
    
    hilo_iq = threading.Thread(target=conectar_iq_option)
    hilo_iq.daemon = True
    hilo_iq.start()
    
    print("⚡ Bot de Telegram listo y escuchando órdenes...")
    while True:
        try:
            # Reemplazo de infinity_polling por polling corregido para disolver errores 409
            bot_telegram.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            print(f"🔄 Reiniciando polling por desconexión: {e}")
            time.sleep(5)
