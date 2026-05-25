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
# CARGA SEGURA DE VARIABLES
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

print("🔥 Sniper V5 - MODO PRUEBA DE FUEGO INSTANTÁNEA ACTIVADO 🔥")

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'options': {'defaultType': 'future'},
    'enableRateLimit': True
})
exchange.set_sandbox_mode(True)

PARES = ["BTC/USDT"]  # Probamos solo con BTC para rapidez

# ==============================================================================
# EJECUCIÓN FORZADA (PRUEBA DE DISPARO Y SALDO)
# ==============================================================================
def ejecutar_caceria_sniper(par):
    try:
        # 1. Consultar saldo inicial en la Demo
        balance = exchange.fetch_balance()
        saldo_inicial = balance['total'].get('USDT', 0.0)
        
        # Descarga rápida para calcular el ATR para los candados matemáticos
        candles = exchange.fetch_ohlcv(par, timeframe='1m', limit=20)
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['tr'] = np.maximum(df['high'] - df['low'], 
                              np.maximum(abs(df['high'] - df['close'].shift()), 
                                         abs(df['low'] - df['close'].shift())))
        atr = df['tr'].ewm(com=13, adjust=False).mean().iloc[-1]
        precio_actual = df['close'].iloc[-1]
        
        print(f"🎯 Forzando disparo de prueba en {par}... Saldo actual: ${saldo_inicial:.2f}")
        
        # Tamaño micro para la prueba
        monto_contrato = 0.001 
        
        # Forzamos una orden de COMPRA de mercado para probar los rieles
        orden = exchange.create_order(symbol=par, type='market', side='buy', amount=monto_contrato)
        precio_entrada = orden['price'] if 'price' in orden else precio_actual
        
        # Candados strictly 1:2
        distancia_sl = atr * 1.5
        distancia_tp = distancia_sl * 2.0
        stop_loss = precio_entrada - distancia_sl
        take_profit = precio_entrada + distancia_tp
        
        # 2. Consultar saldo inmediatamente después de abrir (para ver la comisión/margen)
        balance_post = exchange.fetch_balance()
        saldo_post = balance_post['total'].get('USDT', 0.0)
        
        informe = (
            f"🔥 *[PRUEBA DE FUEGO] ¡Disparo Exitoso!* 🔥\n\n"
            f"🔹 *Par:* {par}\n"
            f"🟩 *Acción:* COMPRA FORZADA (Prueba de Rieles)\n"
            f"📊 *Precio Entrada:* {precio_entrada:.2f}\n"
            f"🛑 *Stop Loss:* {stop_loss:.2f}\n"
            f"💰 *Take Profit:* {take_profit:.2f}\n\n"
            f"💳 *Saldo Inicial Demo:* ${saldo_inicial:.2f} USDT\n"
            f"📉 *Saldo Tras Apertura:* ${saldo_post:.2f} USDT\n\n"
            f"🚀 _El bot tiene acceso total de escritura en Binance Testnet._"
        )
        
        enviar_notificacion_telegram(informe)
        
        # Para no inundar la cuenta, detenemos el script tras el disparo exitoso
        os._exit(0)
        
    except Exception as e:
        error_msg = f"❌ *Fallo en la Prueba de Fuego*:\n`{str(e)}`"
        print(error_msg)
        enviar_notificacion_telegram(error_msg)
        os._exit(1)

def bucle_principal_sniper():
    # Espera 5 segundos tras arrancar y dispara la prueba
    time.sleep(5)
    ejecutar_caceria_sniper("BTC/USDT")

app = Flask(__name__)
@app.route('/')
def index(): return "Modo Prueba de Fuego corriendo."

if __name__ == "__main__":
    hilo_bot = threading.Thread(target=bucle_principal_sniper)
    hilo_bot.daemon = True
    hilo_bot.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
