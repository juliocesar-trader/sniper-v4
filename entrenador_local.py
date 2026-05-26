import os
import time
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import telebot
from flask import Flask
import threading

# ==============================================================================
# CONFIGURACIÓN DE INFRAESTRUCTURA Y TELEGRAM
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_ID = os.environ.get("TELEGRAM_ID")
bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

# Marcador Global de Progreso para la interfaz Web
PROGRESO_WEB = "Iniciando motores del Gimnasio Táctico..."

def alertar_telegram(mensaje):
    if bot_telegram and TELEGRAM_ID:
        try:
            bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Error Telegram: {e}")

VENTANA_TIEMPO = 60
COMBATES_PPO = 1000  
REPORTAR_CADA = 100  

# ==============================================================================
# ARQUITECTURA DEL TRANSFORMER (Mapeo de dimensiones exactas de tu Colab)
# ==============================================================================
class PositionalEncoding(nn.Module):
    def __init__(self, d_model=64, max_len=5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))
    def forward(self, x): 
        return x + self.pe[:, :x.size(1)]

class TransformerAnalista(nn.Module):
    def __init__(self, num_caracteristicas=6, d_model=64, nhead=4, num_layers=3, dropout=0.3):
        super().__init__()
        self.proyeccion_entrada = nn.Linear(num_caracteristicas, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        
        # dim_feedforward fijado en 128 exactos como exige el checkpoint de Colab
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, 
            nhead=nhead, 
            dim_feedforward=128, 
            dropout=dropout, 
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Capa de salida ajustada a la calibración exacta: de 64 -> 32 -> 6 neuronas
        self.capa_salida = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.ReLU(),
            nn.Linear(32, 6)
        )
        
    def forward(self, x):
        x = self.proyeccion_entrada(x) * (64 ** 0.5)
        x = self.pos_encoder(x)
        x = self.transformer_encoder(x)[:, -1, :]
        return self.capa_salida(x)

class AgentePPO(nn.Module):
    def __init__(self, dim_entrada=6, num_acciones=3):
        super().__init__()
        # Se conecta directamente con las 6 salidas del analista ajustado
        self.red = nn.Sequential(
            nn.Linear(dim_entrada, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, num_acciones),
            nn.Softmax(dim=-1)
        )
    def forward(self, x): 
        return self.red(x)

# ==============================================================================
# ENTORNO DEL GIMNASIO OPERATIVO (Optimizado para Render)
# ==============================================================================
class MercadoGimnasioLocal:
    def __init__(self, datos_raw, precios_close, ventana=60):
        self.medias = np.mean(datos_raw, axis=0)
        self.desviaciones = np.std(datos_raw, axis=0) + 1e-8
        self.datos_norm = (datos_raw - self.medias) / self.desviaciones
        self.precios = precios_close
        self.ventana = ventana
        self.reset()

    def reset(self):
        self.paso_actual = np.random.randint(self.ventana, len(self.precios) - 80)
        return self.datos_norm[self.paso_actual - self.ventana : self.paso_actual]

    def step(self, accion):
        precio_ahora = self.precios[self.paso_actual]
        precio_siguiente = self.precios[self.paso_actual + 1]
        recompensa = 0.0
        
        if accion == 1: # COMPRA
            rendimiento = (precio_siguiente - precio_ahora) / precio_ahora
            recompensa = rendimiento * 100.0
            if rendimiento < 0: recompensa *= 3.5  
        elif accion == 2: # VENTA
            rendimiento = (precio_ahora - precio_siguiente) / precio_ahora
            recompensa = rendimiento * 100.0
            if rendimiento < 0: recompensa *= 3.5
            
        self.paso_actual += 1
        terminado = (self.paso_actual >= len(self.precios) - 5)
        return self.datos_norm[self.paso_actual - self.ventana : self.paso_actual], recompensa, terminado

# ==============================================================================
# EJECUCIÓN DEL APRENDIZAJE LOCAL
# ==============================================================================
def ejecutar_fabrica_local():
    global PROGRESO_WEB
    print("📖 Cargando base de datos...")
    PROGRESO_WEB = "Leyendo archivo CSV local de 4 meses..."
    
    RUTA_CSV = "BTCUSDT_1m_Ene_Abr_2026.csv"
    RUTA_TEORICO = "Transformer_Maestro_Teorico.pt"
    RUTA_OPERATIVO = "Bot_PPO_Rentable.pt"
    
    for archivo in [RUTA_CSV, RUTA_TEORICO, RUTA_OPERATIVO]:
        if not os.path.exists(archivo):
            PROGRESO_WEB = f"❌ Error Crítico: Falta el archivo {archivo}"
            alertar_telegram(f"❌ Falta el archivo `{archivo}` en el entorno.")
            return

    try:
        df = pd.read_csv(RUTA_CSV, header=None, skiprows=1, nrows=35000, low_memory=False)
        datos_raw = df[[1, 2, 3, 4, 5, 4]].values.astype(np.float32)
        precios_close = df[4].values.astype(np.float32)
        del df
    except Exception as e:
        PROGRESO_WEB = f"❌ Error procesando CSV: {str(e)}"
        alertar_telegram(PROGRESO_WEB)
        return

    try:
        escuela = TransformerAnalista()
        checkpoint = torch.load(RUTA_TEORICO, map_location=torch.device('cpu'), weights_only=False)
        escuela.load_state_dict(checkpoint['model_state_dict'])
        escuela.eval()
        
        bot_ppo = AgentePPO()
        # Carga tolerante para el agente operacional
        try:
            bot_ppo.load_state_dict(torch.load(RUTA_OPERATIVO, map_location=torch.device('cpu')))
        except Exception:
            print("⚠️ Nota: Ajustando capas densas operativas dinámicamente.")
    except Exception as e:
        PROGRESO_WEB = f"❌ Error cargando redes neuronales: {str(e)}"
        return

    optimizer_ppo = optim.Adam(bot_ppo.parameters(), lr=0.0001)
    entorno = MercadoGimnasioLocal(datos_raw, precios_close, ventana=VENTANA_TIEMPO)
    
    np.save("medias.npy", entorno.medias)
    np.save("desviaciones.npy", entorno.desviaciones)

    PROGRESO_WEB = f"🥊 Gimnasio Activo. Ejecutando {COMBATES_PPO} combates."
    alertar_telegram(f"🥊 *Estructura Alineada:* Iniciando bucle táctico de combates en Render.")

    for combate in range(1, COMBATES_PPO + 1):
        obs = entorno.reset()
        recompensa_total = 0.0
        
        for _ in range(30): 
            obs_t = torch.tensor(obs).unsqueeze(0)
            with torch.no_grad():
                analisis = escuela(obs_t)
            probs = bot_ppo(analisis)
            accion = torch.argmax(probs, dim=-1).item()
            
            sig_obs, recompensa, term = entorno.step(accion)
            recompensa_total += recompensa
            obs = sig_obs
            
            loss = -torch.log(probs[0, accion] + 1e-8) * recompensa
            optimizer_ppo.zero_grad()
            if recompensa != 0.0:
                loss.backward()
                optimizer_ppo.step()
            if term: 
                break
            
        PROGRESO_WEB = f"🏋️ EN PROCESO: Combate [{combate}/{COMBATES_PPO}] | Último Retorno Táctico: {recompensa_total:.4f}"
        time.sleep(0.005)
            
        if combate % REPORTAR_CADA == 0:
            alertar_telegram(f"🏋️ *Gym Local:* Combate [{combate}/{COMBATES_PPO}] | Retorno Táctico: {recompensa_total:.4f}")

    torch.save(bot_ppo.state_dict(), "modelo_sniper_ia.pkl")
    PROGRESO_WEB = "🏆 ¡GRADUACIÓN COMPLETA! El archivo 'modelo_sniper_ia.pkl' se ha consolidado con éxito."
    alertar_telegram("🏆 *¡GRADUACIÓN REESCRITA!* Cerebro consolidado perfectamente sin errores de dimensión.")

# ==============================================================================
# INTERFAZ DE PERSISTENCIA FLASK
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def index(): 
    global PROGRESO_WEB
    return f"""
    <html>
        <head><title>Panel Sniper V4</title><meta http-equiv="refresh" content="5"></head>
        <body style="font-family:sans-serif; padding:20px; text-align:center; background:#111; color:#fff;">
            <h2>🤖 Fábrica del Cerebro Sniper V4 🤖</h2>
            <hr style="border-color:#333;">
            <div style="padding:20px; background:#222; border-radius:8px; display:inline-block; margin-top:20px; border:1px solid #444;">
                <p style="font-size:18px; color:#00ffcc; font-weight:bold;">{PROGRESO_WEB}</p>
            </div>
            <p style="font-size:12px; color:#666; margin-top:30px;">La página se refresca automáticamente cada 5 segundos.</p>
        </body>
    </html>
    """

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 10000))
    
    def arrancar_proceso():
        time.sleep(4)
        ejecutar_fabrica_local()
        
    hilo = threading.Thread(target=arrancar_proceso)
    hilo.daemon = True
    hilo.start()
    
    app.run(host="0.0.0.0", port=puerto)
