import os
import time
import threading
import csv
from flask import Flask

# IMPORTACIÓN DEL PUENTE SEGÚN TU NUEVO ESTÁNDAR
from credenciales import bot_telegram, conectar_broker, TELEGRAM_ID

# ==============================================================================
# CONFIGURACIÓN DE BASE DE DATOS PERSISTENTE PARA LA IA
# ==============================================================================
ARCHIVO_HISTORIAL = "historial_operaciones.csv"

# Si el archivo no existe en el servidor de Render, se inicializan las columnas
if not os.path.exists(ARCHIVO_HISTORIAL):
    with open(ARCHIVO_HISTORIAL, "w", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow([
            "timestamp", "divisa", "hora", "tipo_senal", 
            "precio_entrada", "precio_final", "resultado", 
            "rsi", "atr", "banda_sup", "banda_inf"
        ])

# ==============================================================================
# SERVIDOR WEB FLASK
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
    app.run(host="0.0.0.0", port=puerto)

# ==============================================================================
# ZONA DE ESTRATEGIAS Y ESCÁNER
# ==============================================================================
def calcular_indicadores(velas):
    cierres = [v['close'] for v in velas]
    altos = [v['max'] for v in velas]
    bajos = [v['min'] for v in velas]
    
    k = 2 / (100 + 1)
    ema = cierres[0]
    for c in cierres[1:]: ema = (c * k) + (ema * (1 - k))
        
    ultimas_20 = cierres[-20:]
    sma_20 = sum(ultimas_20) / 20
    varianza = sum((x - sma_20) ** 2 for x in ultimas_20) / 20
    desviacion = varianza ** 0.5
    
    ganancias, perdidas = 0, 0
    for i in range(len(cierres)-14, len(cierres)):
        cambio = cierres[i] - cierres[i-1]
        if cambio > 0: ganancias += cambio
        else: perdidas += abs(cambio)
    rs = (ganancias / 14) / ((perdidas / 14) + 1e-10)
    
    tr_tot = 0
    for i in range(len(velas)-14, len(velas)):
        tr_tot += max(altos[i] - bajos[i], abs(altos[i] - cierres[i-1]), abs(bajos[i] - cierres[i-1]))
        
    return ema, sma_20 + (2 * desviacion), sma_20 - (2 * desviacion), 100 - (100 / (1 + rs)), tr_tot / 14

def escanear_mercados():
    global iq_client
    divisas = ["EURUSD", "GBPUSD", "EURJPY", "AUDUSD"]
    print("🎯 Francotirador activado. Escaneando divisas...")
    
    while True:
        try:
            if iq_client and iq_client.check_connect():
                hora_actual = time.strftime("%H:%M")
                if "12:30" <= hora_actual <= "13:30":
                    time.sleep(60)
                    continue
                    
                for divisa in divisas:
                    try:
                        payouts = iq_client.get_all_profit()
                        payout = payouts.get(divisa, {}).get("turbo", 0)
                        if payout < 80: continue
                            
                        velas = iq_client.get_candles(divisa, 60, 110, time.time())
                        if not velas or len(velas) < 100: continue
                            
                        ema, banda_sup, banda_inf, rsi, atr = calcular_indicadores(velas)
                        ultima_vela = velas[-1]
                        precio_cierre = ultima_vela['close']
                        tamaño_vela = abs(precio_cierre - ultima_vela['open'])
                        
                        if tamaño_vela > (atr * 2.5): continue
                            
                        senal = None
                        if precio_cierre > ema and precio_cierre <= banda_inf and rsi < 25:
                            senal = "🟢 COMPRA (CALL) 📈"
                        elif precio_cierre < ema and precio_cierre >= banda_sup and rsi > 75:
                            senal = "🔴 VENTA (PUT) 📉"
                            
                        if senal:
                            mensaje = f"🎯 *¡SEÑAL FRANCOTIRADOR!*\n\n💱 Divisa: {divisa}\n⚡ Operación: {senal}\n⏱️ Expiración: 1 Minuto"
                            bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
                            
                            # Disparar hilo de simulación y guardado para recolectar datos de IA
                            threading.Thread(
                                target=simular_operacion, 
                                args=(divisa, precio_cierre, senal, rsi, atr, banda_sup, banda_inf),
                                daemon=True
                            ).start()
                            
                    except:
                        pass
        except:
            pass
        time.sleep(10)

def simular_operacion(divisa, precio_entrada, tipo_senal, rsi, atr, banda_sup, banda_inf):
    global iq_client
    time.sleep(62)
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
            
            with open(ARCHIVO_HISTORIAL, mode="a", newline="") as f:
                escritor = csv.writer(f)
                escritor.writerow([
                    timestamp, divisa, hora_registro, tipo_limpio,
                    precio_entrada, precio_final, resultado,
                    round(rsi, 2), round(atr, 6), round(banda_sup, 6), round(banda_inf, 6)
                ])
    except Exception as e:
        print(f"Error registrando simulación IA: {e}")

# ==============================================================================
# ESCUCHA DE COMANDOS DE TELEGRAM
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
        bot_telegram.reply_to(message, "❌ Puente desconectado temporalmente del broker.")

# ==============================================================================
# ARRANQUE ORQUESTADO ASÍNCRONO
# ==============================================================================
def inicializar_sistema():
    global iq_client
    print("🔌 Conectando con IQ Option en segundo plano...")
    iq_client = conectar_broker()
    
    if iq_client:
        threading.Thread(target=escanear_mercados, daemon=True).start()

if __name__ == "__main__":
    try: 
        bot_telegram.remove_webhook(drop_pending_updates=True)
        time.sleep(1)
    except: 
        pass

    # 1. Encender Servidor Web Flask
    threading.Thread(target=ejecutar_servidor_web, daemon=True).start()
    time.sleep(1)
    
    # 2. Lanzar la inicialización del broker y escáner
    threading.Thread(target=inicializar_sistema, daemon=True).start()
    
    print("⚡ Escucha de Telegram liberada. Activando Polling...")
    
    # 3. El hilo principal se queda EXCLUSIVAMENTE escuchando comandos sin interrupciones
    while True:
        try:
            bot_telegram.polling(none_stop=True, skip_pending_updates=True, timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"Reiniciando Polling por parpadeo de red: {e}")
            time.sleep(5)
