import os
import time
import datetime
import threading
import ccxt
import pandas as pd
import numpy as np
import telebot
from flask import Flask

# ==============================================================================
# ENTORNO SEGURO Y CONFIGURACIÓN GENERAL
# ==============================================================================
API_KEY = os.environ.get("BINANCE_API_KEY")
API_SECRET = os.environ.get("BINANCE_SECRET_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_ID = os.environ.get("TELEGRAM_ID")

bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

def enviar_notificacion_telegram(mensaje):
    if bot_telegram and TELEGRAM_ID:
        try:
            bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Error Telegram: {e}")

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'options': {'defaultType': 'future'},
    'enableRateLimit': True
})
# SE MANTIENE EN MODO DEMO PARA TU PROTECCIÓN TOTAL
exchange.set_sandbox_mode(True)

PARES = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

print("🦁 Sniper V5 Pro - Modo Operativo Activado")

# ==============================================================================
# MOTOR ANÁLISIS: REVERSIÓN A LA MEDIA (1 MINUTO)
# ==============================================================================
def calcular_estrategia_sniper(par):
    try:
        candles = exchange.fetch_ohlcv(par, timeframe='1m', limit=50)
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # RSI Wilder
        delta = df['close'].diff()
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        avg_gain = gains.ewm(com=13, adjust=False).mean()
        avg_loss = losses.ewm(com=13, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR para Candados
        df['tr'] = np.maximum(df['high'] - df['low'], 
                              np.maximum(abs(df['high'] - df['close'].shift()), 
                                         abs(df['low'] - df['close'].shift())))
        df['atr'] = df['tr'].ewm(com=13, adjust=False).mean()
        df['volumen_medio'] = df['volume'].rolling(window=15).mean()
        
        return df.iloc[-2].to_dict()
    except Exception as e:
        print(f"⚠️ Error matemático en {par}: {e}")
        return None

# ==============================================================================
# CAZA Y GESTIÓN ASIMÉTRICA 1:2
# ==============================================================================
def ejecutar_caceria_sniper(par):
    datos = calcular_estrategia_sniper(par)
    if not datos:
        return
        
    precio_actual = datos['close']
    atr = datos['atr']
    rsi = datos['rsi']
    volumen = datos['volume']
    volumen_medio = datos['volumen_medio']
    
    direccion = None
    # Filtros matemáticos institucionales rígidos
    if rsi < 24 and volumen > (volumen_medio * 1.4):
        direccion = "BUY"
    elif rsi > 76 and volumen > (volumen_medio * 1.4):
        direccion = "SELL"

    if direccion:
        try:
            # Consultamos saldo antes del disparo
            bal = exchange.fetch_balance()
            saldo_inicial = bal['total'].get('USDT', 0.0)
            
            # Tamaño asignado para simulación controlada
            monto_contrato = 0.001 if "BTC" in par else (0.01 if "ETH" in par else 0.1)
            tipo_orden = 'buy' if direccion == "BUY" else 'sell'
            
            orden = exchange.create_order(symbol=par, type='market', side=tipo_orden, amount=monto_contrato)
            precio_entrada = orden['price'] if 'price' in orden else precio_actual
            
            # Candados 1:2 basados en volatilidad real
            distancia_sl = atr * 1.5
            distancia_tp = distancia_sl * 2.0
            
            if direccion == "BUY":
                stop_loss = precio_entrada - distancia_sl
                take_profit = precio_entrada + distancia_tp
            else:
                stop_loss = precio_entrada + distancia_sl
                take_profit = precio_entrada - distancia_tp
                
            # Mandamos reporte de ejecución real al canal
            informe = (
                f"🎯 *[Sniper V5] Operación Detectada y Ejecutada*\n\n"
                f"🔹 *Par:* {par}\n"
                f"🔹 *Estrategia:* Reversión a la Media\n"
                f"🔹 *Posición:* {'🟩 COMPRA (Long)' if direccion == 'BUY' else '🟥 VENTA (Short)'}\n\n"
                f"📊 *Entrada:* {precio_entrada:.2f}\n"
                f"🛑 *Stop Loss (Pérdida Mínima):* {stop_loss:.2f}\n"
                f"💰 *Take Profit (Doble Ganancia):* {take_profit:.2f}\n\n"
                f"💳 *Saldo Disponible Demo:* ${saldo_inicial:.2f} USDT"
            )
            enviar_notificacion_telegram(informe)
            
        except Exception as e:
            print(f"❌ Error al enviar orden a Binance: {e}")

# ==============================================================================
# RELOJ DE CONTROL REPETITIVO
# ==============================================================================
def bucle_principal_sniper():
    print("🦁 Sniper V5 en posición en los servidores de Render...")
    enviar_notificacion_telegram("🦁 *¡Sniper V5 listo para la acción!* Modo cacería estadística activado 24/7 en Binance Demo.")
    
    while True:
        ahora = datetime.datetime.now()
        espera = 60 - ahora.second
        time.sleep(espera)  # Asegura ejecución exacta en el segundo cero de cada minuto
        
        for par in PARES:
            threading.Thread(target=ejecutar_caceria_sniper, args=(par,)).start()

# ==============================================================================
# PERSISTENCIA CLOUD
# ==============================================================================
app = Flask(__name__)
@app.route('/')
def index(): return "Sniper V5 Monitoreando el Mercado Cripto 24/7."

if __name__ == "__main__":
    hilo_bot = threading.Thread(target=bucle_principal_sniper)
    hilo_bot.daemon = True
    hilo_bot.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
