import os
import time
import threading
from flask import Flask

# IMPORTACIÓN DEL PUENTE SEGÚN TU NUEVO ESTÁNDAR
from credenciales import bot_telegram, conectar_broker, TELEGRAM_ID

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
HISTORIAL_SENALES = {}

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
                    tamaño_vela = abs(ultima_vela['close'] - ultima_vela['open'])
                    
                    clave = (divisa, hora_actual[:2])
                    est = HISTORIAL_SENALES.get(clave, {"ganadas": 0, "perdidas": 0})
                    tot = est["ganadas"] + est["perdidas"]
                    if tot > 4 and (est["ganadas"] / tot) < 0.50: continue
                    if tamaño_vela > (atr * 2.5): continue
                        
                    senal = None
                    if ultima_vela['close'] > ema and ultima_vela['close'] <= banda_inf and rsi < 25:
                        senal = "🟢 COMPRA (CALL) 📈"
                    elif ultima_vela['close'] < ema and ultima_vela['close'] >= banda_sup and rsi > 75:
                        senal = "🔴 VENTA (PUT) 📉"
                        
                    if senal:
                        mensaje = f"🎯 *¡SEÑAL FRANCOTIRADOR!*\n\n💱 Divisa: {divisa}\n⚡ Operación: {senal}\n⏱️ Expiración: 1 Minuto"
                        bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
                except:
                    pass
        time.sleep(10)

# ==============================================================================
# ESCUCHA DE COMANDOS DE TELEGRAM (Vinculados localmente al proceso principal)
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
# ARRANQUE ORQUESTADO
# ==============================================================================
if __name__ == "__main__":
    try: 
        bot_telegram.remove_webhook(drop_pending_updates=True)
    except: 
        pass

    # 1. Encender Servidor Web
    threading.Thread(target=ejecutar_servidor_web, daemon=True).start()
    time.sleep(2)
    
    # 2. Conectar puente con el Broker
    iq_client = conectar_broker()
    
    if iq_client:
        # 3. Encender escáner si la conexión fue exitosa
        threading.Thread(target=escanear_mercados, daemon=True).start()
    
    print("⚡ Procesos modulares enlazados. Activando Polling del Bot...")
    
    # 4. El bucle corre aquí en main, donde están declarados los handlers de comandos
    while True:
        try:
            bot_telegram.polling(none_stop=True, interval=2, timeout=20, restart_on_change=True, skip_pending_updates=True)
        except Exception as e:
            print(f"Reiniciando Polling: {e}")
            time.sleep(5)
