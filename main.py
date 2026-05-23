import os
import time
import threading
import csv
import talib
import numpy as np
from datetime import datetime
from flask import Flask

# IMPORTACIÓN DEL PUENTE SEGÚN TU ESTÁNDAR
from credenciales import bot_telegram, conectar_broker, TELEGRAM_ID

# ==============================================================================
# BASE DE DATOS PERSISTENTE PARA LA EVOLUCIÓN DE LA IA (VERSION 4.5 EXPANDIDA)
# ==============================================================================
ARCHIVO_HISTORIAL = "historial_operaciones.csv"

# Si el archivo no existe, lo crea con la nueva cabecera de 17 columnas de alta precisión
if not os.path.exists(ARCHIVO_HISTORIAL):
    with open(ARCHIVO_HISTORIAL, "w", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow([
            "timestamp", "divisa", "hora", "tipo_senal", 
            "precio_entrada", "precio_final", "resultado", 
            "rsi", "atr", "banda_sup", "banda_inf",
            "ema_200", "macd_line", "macd_signal", 
            "slowk", "slowd", "adx", "distancia_ema", "hora_numerica"
        ])

# ==============================================================================
# SERVIDOR WEB FLASK (SOPORTE PARA RENDER Y EXTRACCIÓN DE DATOS)
# ==============================================================================
app = Flask(__name__)
iq_client = None  

@app.route('/')
def home():
    global iq_client
    if iq_client and iq_client.check_connect():
        estado = "🟢 IA EVOLUTIVA V4.5 - COSECHANDO ARSENAL CUANTITATIVO COMPLETO (MODO OTC)"
        try: saldo = f"${iq_client.get_balance():,.2f} USD"
        except: saldo = "Cargando..."
    else:
        estado = "❌ PUENTE DESCONECTADO"
        saldo = "$0.00"
    
    return f"<h2>🧠 Sniper V4.5 - Cosecha Premium IA (OTC)</h2><p><b>Estado:</b> {estado}</p><p><b>Saldo:</b> {saldo}</p>", 200

@app.route('/descargar-datos-ia')
def descargar_datos_ia():
    if os.path.exists(ARCHIVO_HISTORIAL):
        with open(ARCHIVO_HISTORIAL, "r") as f:
            contenido = f.read()
        return f"<pre>{contenido}</pre>", 200, {'Content-Type': 'text/plain; charset=utf-8'}
    return "⏳ El archivo aún no tiene datos registrados.", 404

def ejecutar_servidor_web():
    puerto = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=puerto, debug=False, use_reloader=False)

# ==============================================================================
# MATEMÁTICAS DE MERCADO (INDICADORES BASE + NUEVOS OJOS DE LA IA)
# ==============================================================================
def calcular_indicadores_avanzados(velas):
    # Protegemos el sistema pidiendo un mínimo de 250 velas para cálculo estable de EMA200
    if len(velas) < 250:
        return 0, 0, 0, 50, 0, 0, 0, 0, 0, 0, 0, 0, 0
    
    cierres = np.array([v['close'] for v in velas], dtype=float)
    altos = np.array([v['max'] for v in velas], dtype=float)
    bajos = np.array([v['min'] for v in velas], dtype=float)
    precio_cierre_actual = moc_cierre = cierres[-1]
    
    # 1. Indicadores Base Matemáticos (Originales del Bot)
    ultimas_20 = cierres[-20:]
    sma_20 = sum(ultimas_20) / 20
    varianza = sum((x - sma_20) ** 2 for x in ultimas_20) / 20
    desviacion = varianza ** 0.5
    b_sup = sma_20 + (2 * desviacion)
    b_inf = sma_20 - (2 * desviacion)
    
    ganancias, perdidas = 0, 0
    for i in range(len(cierres)-14, len(cierres)):
        cambio = cierres[i] - cierres[i-1]
        if cambio > 0: ganancias += cambio
        else: perdidas += abs(cambio)
    rs = (ganancias / 14) / ((perdidas / 14) + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    
    tr_tot = 0
    for i in range(len(velas)-14, len(velas)):
        tr_tot += max(altos[i] - bajos[i], abs(altos[i] - cierres[i-1]), abs(bajos[i] - cierres[i-1]))
    atr = tr_tot / 14
        
    # 2. 🌟 FILTRO DE TENDENCIA MAESTRA (EMA 200)
    ema_200 = round(float(talib.EMA(cierres, timeperiod=200)[-1]), 6)
    
    # 3. 🌟 IMPULSO CORREGIDO (MACD ESTÁNDAR CON HISTORIAL COMPLETO)
    macd, macdsignal, _ = talib.MACD(cierres, fastperiod=12, slowperiod=26, signalperiod=9)
    macd_line = round(float(macd[-1]), 6) if not np.isnan(macd[-1]) else 0.0
    macd_sig = round(float(macdsignal[-1]), 6) if not np.isnan(macdsignal[-1]) else 0.0
    
    # 4. 🌟 NUEVOS OJOS: MOMENTUM DE REVERSIÓN (ESTOCÁSTICO)
    slowk, slowd = talib.STOCH(altos, bajos, cierres, fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
    stoch_k = round(float(slowk[-1]), 2) if not np.isnan(slowk[-1]) else 50.0
    stoch_d = round(float(slowd[-1]), 2) if not np.isnan(slowd[-1]) else 50.0
    
    # 5. 🌟 NUEVOS OJOS: FUERZA DE LA TENDENCIA (ADX)
    adx_valores = talib.ADX(altos, bajos, cierres, timeperiod=14)
    adx = round(float(adx_valores[-1]), 2) if not np.isnan(adx_valores[-1]) else 0.0
    
    # 6. 🌟 NUEVOS OJOS: EFECTO LIGA (DISTANCIA EN PIPS A LA EMA 200)
    distancia_ema = round(float(precio_cierre_actual - ema_200), 6)
    
    # 7. Horario Numérico Profesional
    ahora = datetime.now()
    hora_numerica = round(ahora.hour + (ahora.minute / 60.0), 2)
    
    return b_sup, b_inf, rsi, atr, ema_200, macd_line, macd_sig, stoch_k, stoch_d, adx, distancia_ema, hora_numerica

# ==============================================================================
# ESCÁNER DE ALIMENTACIÓN: CONEXIÓN REAL A MERCADO + COSECHA EXPANDIDA
# ==============================================================================
def escanear_mercados():
    global iq_client
    # 🛠️ MODIFICACIÓN SÚPER SNIPER: ACTIVACIÓN DE DIVISAS EN MERCADO OTC DE FIN DE SEMANA
    divisas = ["EURUSD-OTC", "GBPUSD-OTC", "EURJPY-OTC", "AUDUSD-OTC"]
    print("🧠 Sniper V4.5 Activo: Cosechando el arsenal cuantitativo completo en OTC...")
    
    try:
        bot_telegram.send_message(TELEGRAM_ID, "🚀 *Súper Cosecha Inteligente V4.5 Iniciada (Modo OTC)*\nEl bot está cazando escenarios reales de fin de semana inyectando la matriz cuántica completa.", parse_mode="Markdown")
    except:
        pass

    while True:
        if iq_client and iq_client.check_connect():
            for divisa in divisas:
                try:
                    # CLAVE BRUTAL: Solicitamos 300 velas para que den todos los cálculos matemáticos a la perfección
                    velas = iq_client.get_candles(divisa, 60, 300, time.time())
                    if not velas or len(velas) < 250: continue
                    
                    # Ejecutamos los cálculos cuantitativos con la inyección avanzada
                    b_sup, b_inf, rsi, atr, ema_200, macd_line, macd_sig, stoch_k, stoch_d, adx, distancia_ema, hora_numerica = calcular_indicadores_avanzados(velas)
                    precio_cierre = velas[-1]['close']
                    
                    senal = None
                    if rsi > 65 or precio_cierre >= b_sup:
                        senal = "🔴 VENTA (ESCENARIO IA) 📉"
                    elif rsi < 35 or precio_cierre <= b_inf:
                        senal = "🟢 COMPRA (ESCENARIO IA) 📈"
                    
                    if senal:
                        # Formateamos el ADX visualmente para que sepas el estado del mercado en tu cel
                        estado_tendencia = "Tendencia Fuerte" if adx > 25 else "Mercado Lateral/Sano"
                        
                        mensaje = (f"🧠 *ESCENARIO DETECTADO ({divisa})*\n"
                                   f"⚡ Tipo: {senal}\n"
                                   f"📊 RSI: {round(rsi,1)} | ATR: {round(atr,6)}\n"
                                   f"🎯 MACD: {round(macd_line,5)} | ADX: {round(adx,1)} ({estado_tendencia})\n"
                                   f"🔄 Estocástico K: {round(stoch_k,1)} | D: {round(stoch_d,1)}")
                        
                        bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
                        
                        # Mandamos a guardar los datos de forma asíncrona incluyendo la nueva estructura completa
                        threading.Thread(
                            target=simular_operacion, 
                            args=(divisa, precio_cierre, senal, rsi, atr, b_sup, b_inf, ema_200, macd_line, macd_sig, stoch_k, stoch_d, adx, distancia_ema, hora_numerica),
                            daemon=True
                        ).start()
                        
                except Exception as e:
                    print(f"Error analizando {divisa}: {e}")
                time.sleep(2)
        else:
            print("🔌 Esperando conexión del broker...")
        time.sleep(15)

def simular_operacion(divisa, precio_entrada, tipo_senal, rsi, atr, banda_sup, banda_inf, ema_200, macd_line, macd_sig, stoch_k, stoch_d, adx, distancia_ema, hora_numerica):
    global iq_client
    time.sleep(61) # Esperamos el vencimiento exacto de la vela de 1 minuto
    try:
        if iq_client and iq_client.check_connect():
            velas = iq_client.get_candles(divisa, 60, 1, time.time())
            if not velas: return
            
            precio_final = velas[-1]['close']
            hora_registro = time.strftime("%H:%M:%S")
            timestamp = int(time.time())
            
            ganó = False
            if "COMPRA" in tipo_senal and precio_final > precio_entrada: ganó = True
            elif "VENTA" in tipo_senal and precio_final < precio_entrada: ganó = True
            
            resultado = 1 if ganó else 0
            tipo_limpio = "COMPRA" if "COMPRA" in tipo_senal else "VENTA"
            
            # Escritura limpia en el CSV persistente de las 17 columnas cuantitativas
            with open(ARCHIVO_HISTORIAL, mode="a", newline="") as f:
                escritor = csv.writer(f)
                escritor.writerow([
                    timestamp, divisa, hora_registro, tipo_limpio,
                    precio_entrada, precio_final, resultado,
                    round(rsi, 2), round(atr, 6), round(banda_sup, 6), round(banda_inf, 6),
                    round(ema_200, 6), round(macd_line, 6), round(macd_sig, 6),
                    round(stoch_k, 2), round(stoch_d, 2), round(adx, 2), round(distancia_ema, 6), round(hora_numerica, 2)
                ])
    except Exception as e:
        print(f"Error en registro evolutivo: {e}")

# ==============================================================================
# ESCUCHA DE COMANDOS
# ==============================================================================
@bot_telegram.message_handler(commands=['saldo'])
def enviar_saldo(message):
    global iq_client
    if iq_client and iq_client.check_connect():
        try:
            bot_telegram.reply_to(message, f"💰 Saldo de Práctica Real: ${iq_client.get_balance():,.2f} USD")
        except Exception as e:
            bot_telegram.reply_to(message, f"⚠️ Error leyendo saldo: {e}")
    else:
        bot_telegram.reply_to(message, "❌ Puente desconectado del broker.")

# ==============================================================================
# ARRANQUE GLOBAL
# ==============================================================================
if __name__ == "__main__":
    try: 
        bot_telegram.remove_webhook(drop_pending_updates=True)
        time.sleep(1)
    except: 
        pass

    print("🔌 Conectando con IQ Option...")
    iq_client = conectar_broker()

    threading.Thread(target=ejecutar_servidor_web, daemon=True).start()
    time.sleep(2)

    threading.Thread(target=escanear_mercados, daemon=True).start()

    print("🚀 Servidores acoplados. Activando Polling de Telegram...")
    while True:
        try:
            bot_telegram.polling(none_stop=True, skip_pending_updates=True, timeout=20, long_polling_timeout=10)
        except Exception as e:
            time.sleep(5)
