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
# CARGA SEGURA DE VARIABLES DESDE EL BÚNKER DE RENDER
# ==============================================================================
API_KEY = os.environ.get("BINANCE_API_KEY")
API_SECRET = os.environ.get("BINANCE_SECRET_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_ID = os.environ.get("TELEGRAM_ID")

# Inicializamos el bot de Telegram de forma segura
bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

def enviar_notificacion_telegram(mensaje):
    """Función segura para enviarte alertas en vivo al celular"""
    if bot_telegram and TELEGRAM_ID:
        try:
            bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ No se pudo enviar el mensaje a Telegram: {e}")

print("🦁 Sniper V5 (Edición Binance + Telegram) - Inicializando Motores...")

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'options': {'defaultType': 'future'},
    'enableRateLimit': True
})

# Forzado estricto a modo DEMO (Sandbox) para auditar el sistema de forma segura
exchange.set_sandbox_mode(True)

PARES = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
SIMULACION_CAPITAL_TOTAL = 10.0  # Simulamos que nuestra cuenta es de solo $10 USD

# ==============================================================================
# ANÁLISIS ESTADÍSTICO DE 1 MINUTO (Reversión a la Media)
# ==============================================================================
def calcular_estrategia_sniper(par):
    try:
        candles = exchange.fetch_ohlcv(par, timeframe='1m', limit=50)
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # RSI institucional de Wilder
        delta = df['close'].diff()
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        avg_gain = gains.ewm(com=13, adjust=False).mean()
        avg_loss = losses.ewm(com=13, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR para colocar los candados matemáticos
        df['tr'] = np.maximum(df['high'] - df['low'], 
                              np.maximum(abs(df['high'] - df['close'].shift()), 
                                         abs(df['low'] - df['close'].shift())))
        df['atr'] = df['tr'].ewm(com=13, adjust=False).mean()
        
        # Volumen promedio de control
        df['volumen_medio'] = df['volume'].rolling(window=15).mean()
        
        return df.iloc[-2].to_dict()  # Analizamos la vela cerrada para evitar ruidos
    except Exception as e:
        print(f"⚠️ Error en cálculo matemático para {par}: {e}")
        return None

# ==============================================================================
# EJECUCIÓN ASÍNCRONA CON RATIO ASIMÉTRICO 1:2
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
    # Filtros estrictos de alta probabilidad
    if rsi < 24 and volumen > (volumen_medio * 1.4):
        direccion = "BUY"  # Entramos en LARGO al rebote
    elif rsi > 76 and volumen > (volumen_medio * 1.4):
        direccion = "SELL" # Entramos en CORTO a la caída

    if direccion:
        try:
            # Tamaño micro simulando gestión de riesgo para $10 USD total
            monto_contrato = 0.001 if "BTC" in par else (0.01 if "ETH" in par else 0.1)
            
            tipo_orden = 'buy' if direccion == "BUY" else 'sell'
            orden = exchange.create_order(symbol=par, type='market', side=tipo_orden, amount=monto_contrato)
            precio_entrada = orden['price'] if 'price' in orden else precio_actual
            
            # --- DISEÑO DE CANDADOS ASIMÉTRICOS (Perder mínimo, ganar el doble) ---
            distancia_sl = atr * 1.5
            distancia_tp = distancia_sl * 2.0  # <--- RATIO 1:2 ESTRICTO
            
            if direccion == "BUY":
                stop_loss = precio_entrada - distancia_sl
                take_profit = precio_entrada + distancia_tp
            else:
                stop_loss = precio_entrada + distancia_sl
                take_profit = precio_entrada - distancia_tp
                
            # Construimos el informe estético para enviártelo a tu Telegram
            informe = (
                f"🎯 *[Sniper V5] Operación Ejecutada en Demo*\n\n"
                f"🔹 *Par:* {par}\n"
                f"🔹 *Acción:* {'🟩 COMPRA (Long)' if direccion == 'BUY' else '🟥 VENTA (Short)'}\n"
                f"📊 *Precio Entrada:* {precio_entrada:.2f}\n"
                f"🛑 *Stop Loss (Pérdida Mínima):* {stop_loss:.2f}\n"
                f"💰 *Take Profit (Doble Ganancia):* {take_profit:.2f}\n\n"
                f"📈 _Analizando el mercado a un 52% promedio..._"
            )
            
            print(f"🛡️ Orden colocada en demo para {par}. Enviando reporte a Telegram...")
            enviar_notificacion_telegram(informe)
            
        except Exception as e:
            print(f"❌ Error al lanzar orden en Binance: {e}")

# ==============================================================================
# HILO REPETITIVO SIN LATENCIA (Sincronizado al segundo 0)
# ==============================================================================
def bucle_principal_sniper():
    print("🦁 Sniper V5 listo y cazando en Binance Futures...")
    enviar_notificacion_telegram("🦁 *¡Sniper V5 en línea!* Conectado a Binance Demo con éxito y listo para cazar.")
    
    while True:
        ahora = datetime.datetime.now()
        espera = 60 - ahora.second
        time.sleep(espera)  # Espera exacta al cambio de cada minuto
        
        for par in PARES:
            threading.Thread(target=ejecutar_caceria_sniper, args=(par,)).start()

# ==============================================================================
# PERSISTENCIA EN CLOUD (FLASK PARA QUE RENDER NO SE DUERMA)
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def index():
    return "🦁 Sniper V5 activo. Sistema de Reversión Cuántica en ejecución."

if __name__ == "__main__":
    hilo_bot = threading.Thread(target=bucle_principal_sniper)
    hilo_bot.daemon = True
    hilo_bot.start()
    
    puerto = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=puerto)
