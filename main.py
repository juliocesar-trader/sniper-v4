import os
import time
import requests
import pandas as pd
import numpy as np
import talib # Biblioteca de análisis técnico para los nuevos indicadores
from datetime import datetime
from flask import Flask, jsonify, send_file

# ==============================================================================
# CORAZÓN ACTUALIZADO - SNIPER V4 MULTIESTRATEGIA
# ==============================================================================

app = Flask(__name__)
ARCHIVO_DATOS = 'historial_ia.csv'

# Verificar si el cuaderno ya existe para no borrar lo cosechado
if not os.path.exists(ARCHIVO_DATOS):
    df_base = pd.DataFrame(columns=['timestamp', 'divisa', 'hora', 'tipo_senal', 'precio_entrada', 'precio_final', 'resultado', 'rsi', 'atr', 'banda_sup', 'banda_inf', 'ema_200', 'macd_line', 'macd_signal', 'hora_numerica'])
    df_base.to_csv(ARCHIVO_DATOS, index=False)

def obtener_datos_mercado(divisa):
    """
    Simulación del escáner leyendo el mercado en vivo.
    Aquí se calculan los indicadores antiguos y los NUEVOS ojos de la IA.
    """
    # Simulamos un historial de precios para que funcionen los indicadores matemáticos
    precios = np.random.normal(1.2000, 0.0050, 300)
    
    # INDICADORES VIEJOS
    rsi = round(float(talib.RSI(precios, timeperiod=14)[-1]), 2)
    atr = round(float(talib.ATR(precios, precios, precios, timeperiod=14)[-1]), 6)
    banda_sup, _, banda_inf = talib.BBANDS(precios, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    b_sup = round(float(banda_sup[-1]), 6)
    b_inf = round(float(banda_inf[-1]), 6)
    
    # 🌟 NUEVOS INDICADORES (LOS OJOS NUEVOS DE LA IA)
    ema_200 = round(float(talib.EMA(precios, timeperiod=200)[-1]), 6)
    macd, macdsignal, _ = talib.MACD(precios, fastperiod=12, slowperiod=26, signalperiod=9)
    macd_line = round(float(macd[-1]), 6)
    macd_sig = round(float(macdsignal[-1]), 6)
    
    # Filtro de Horario (Convertimos la hora actual a un número que la IA entienda)
    ahora = datetime.now()
    hora_numerica = round(ahora.hour + (ahora.minute / 60.0), 2)
    
    return rsi, atr, b_sup, b_inf, ema_200, macd_line, macd_sig, hora_numerica

def registrar_operacion_ia(divisa, tipo, rsi, atr, b_sup, b_inf, ema_200, macd_line, macd_sig, hora_numerica):
    """
    Guarda la operación en el archivo CSV sin borrar lo anterior,
    añadiendo las columnas nuevas hacia la derecha.
    """
    ahora = datetime.now()
    timestamp = int(time.time())
    hora_str = ahora.strftime("%H:%M:%S")
    
    # Simulación de resultado (1=Ganada, 0=Perdida) para la cosecha
    resultado = np.random.choice([0, 1], p=[0.45, 0.55])
    precio_ent = 1.2050
    precio_fin = 1.2055 if resultado == 1 else 1.2045
    
    # Nueva fila con los datos viejos + los nuevos
    nueva_fila = [timestamp, divisa, hora_str, tipo, precio_ent, precio_fin, resultado, rsi, atr, b_sup, b_inf, ema_200, macd_line, macd_sig, hora_numerica]
    
    df = pd.read_csv(ARCHIVO_DATOS)
    df.loc[len(df)] = nueva_fila
    df.to_csv(ARCHIVO_DATOS, index=False)
    
    print(f"💾 Cosecha Expandida: {divisa} | {tipo} | RSI: {rsi} | EMA200: {ema_200} | Resultado: {resultado}")

@app.route('/descargar-datos-ia', methods=['GET'])
def descargar_datos():
    # Ruta de internet por donde Google Colab descarga todo el historial limpio
    return send_file(ARCHIVO_DATOS, mimetype='text/csv')

@app.route('/')
def inicio():
    return "🤖 SNIPER V4 IA - Servidor de Cosecha Multiestrategia Activo y Corriendo."

# Simulación del bucle del bot cazando señales en la nube
def bucle_bot():
    divisas = ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDJPY']
    while True:
        for divisa in divisas:
            rsi, atr, b_sup, b_inf, ema_200, macd_line, macd_sig, hora_numerica = obtener_datos_mercado(divisa)
            
            # El bot sigue disparando rápido (Filtro flojo) para acumular historial masivo
            if rsi >= 65:
                registrar_operacion_ia(divisa, 'VENTA', rsi, atr, b_sup, b_inf, ema_200, macd_line, macd_sig, hora_numerica)
            elif rsi <= 35:
                registrar_operacion_ia(divisa, 'COMPRA', rsi, atr, b_sup, b_inf, ema_200, macd_line, macd_sig, hora_numerica)
                
        time.sleep(10) # Escanea el mercado cada 10 segundos

if __name__ == '__main__':
    # Esto arranca el bot en segundo plano para que Render no se sature
    import threading
    threading.Thread(target=bucle_bot, daemon=True).start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
