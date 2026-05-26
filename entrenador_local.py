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

def alertar_telegram(mensaje):
    if bot_telegram and TELEGRAM_ID:
        try:
            bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Error Telegram: {e}")

VENTANA_TIEMPO = 60
COMBATES_PPO = 4000  # Sesión robusta sobre tus datos locales

# ==============================================================================
# ARQUITECTURA DEL TRANSFORMER (Mapeo exacto de pesos de Colab)
# ==============================================================================
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))
    def forward(self, x): return x + self.pe[:, :x.size(1)]

class TransformerAnalista(nn.Module):
    def __init__(self, num_caracteristicas=6, d_model=64, nhead=4, num_layers=3, dropout=0.3):
        super().__init__()
        self.proyeccion_entrada = nn.Linear(num_caracteristicas, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dropout=dropout, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
    def forward(self, x):
        x = self.proyeccion_entrada(x) * (64 ** 0.5)
        x = self.pos_encoder(x)
        return self.transformer_encoder(x)[:, -1, :]

class AgentePPO(nn.Module):
    def __init__(self, d_model=64, num_acciones=3):
        super().__init__()
        self.red = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, num_acciones),
            nn.Softmax(dim=-1)
        )
    def forward(self, x): return self.red(x)

# ==============================================================================
# GIMNASIO OPERATIVO REAL (Usando tu base de datos unificada de 4 meses)
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
        self.paso_actual = np.random.randint(self.ventana, len(self.precios) - 120)
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
# EJECUCIÓN MAESTRA (Transfer Learning + CSV Local)
# ==============================================================================
def ejecutar_fabrica_local():
    print("📖 Cargando base de datos e inyectando cerebros pre-entrenados...")
    alertar_telegram("📦 *Fábrica Local Activa:* Leyendo archivo CSV de 4 meses e importando redes neuronales...")
    
    RUTA_CSV = "BTCUSDT_1m_Ene_Abr_2026.csv"
    RUTA_TEORICO = "Transformer_Maestro_Teorico.pt"
    RUTA_OPERATIVO = "Bot_PPO_Rentable.pt"
    
    for archivo in [RUTA_CSV, RUTA_TEORICO, RUTA_OPERATIVO]:
        if not os.path.exists(archivo):
            alertar_telegram(f"❌ Error crítico: Falta el archivo `{archivo}` en la raíz de GitHub.")
            return

    # 1. Leer los datos locales de forma ultra eficiente (Mapeo corregido de 6 columnas)
    try:
        # skiprows=1 salta las cabeceras de texto; low_memory=False estabiliza los tipos de datos
        df = pd.read_csv(RUTA_CSV, header=None, skiprows=1, low_memory=False)
        
        # Extraemos las columnas numéricas exactas presentes en tu archivo consolidado:
        # [Open, High, Low, Close, Volume] y duplicamos la columna 4 (Close) para completar las 6 características
        datos_raw = df[[1, 2, 3, 4, 5, 4]].values.astype(np.float32)
        precios_close = df[4].values.astype(np.float32)
        
        del df # Liberamos memoria RAM del servidor web inmediatamente
    except Exception as e:
        alertar_telegram(f"❌ Error al procesar el CSV local: {str(e)}")
        return

    # 2. Reconstruir y cargar el Transformer Analista de Colab
    try:
        escuela = TransformerAnalista()
        checkpoint = torch.load(RUTA_TEORICO, map_location=torch.device('cpu'), weights_only=False)
        escuela.load_state_dict(checkpoint['model_state_dict'])
        escuela.eval()
    except Exception as e:
        alertar_telegram(f"❌ Error cargando Transformer de Colab: {str(e)}")
        return

    # 3. Reconstruir y cargar el Agente de toma de decisiones PPO
    try:
        bot_ppo = AgentePPO()
        bot_ppo.load_state_dict(torch.load(RUTA_OPERATIVO, map_location=torch.device('cpu')))
    except Exception as e:
        alertar_telegram(f"❌ Error cargando Agente PPO de Colab: {str(e)}")
        return

    optimizer_ppo = optim.Adam(bot_ppo.parameters(), lr=0.0001)
    entorno = MercadoGimnasioLocal(datos_raw, precios_close, ventana=VENTANA_TIEMPO)
    
    alertar_telegram("🥊 *Gimnasio en Alta Definición:* Entrenando reflejos tácticos directamente sobre los 4 meses históricos...")

    # Guardamos las medias y desviaciones locales para el main de trading en vivo posterior
    np.save("medias.npy", entorno.medias)
    np.save("desviaciones.npy", entorno.desviaciones)

    # 4. Bucle de simulación táctica del Gimnasio
    for combate in range(1, COMBATES_PPO + 1):
        obs = entorno.reset()
        recompensa_total = 0.0
        
        for _ in range(60): 
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
            if term: break
            
        if combate % 1000 == 0:
            alertar_telegram(f"🏋️ *Gym Local:* Combate [{combate}/{COMBATES_PPO}] | Retorno Táctico: {recompensa_total:.4f}")

    # Guardar el cerebro final hiper-optimizado listo para producción
    torch.save(bot_ppo.state_dict(), "modelo_sniper_ia.pkl")
    alertar_telegram("🏆 *¡GRADUACIÓN ABSOLUTA CON CSV LOCAL!* El modelo `modelo_sniper_ia.pkl` ha asimilado los 4 meses y está listo.")
    print("Proceso finalizado con éxito.")

# ==============================================================================
# INTERFAZ DE PERSISTENCIA FLASK
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def index(): 
    return "Fábrica basada en Datos Locales corriendo de manera estable."

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 10000))
    
    def arrancar_proceso():
        time.sleep(10)
        ejecutar_fabrica_local()
        
    hilo = threading.Thread(target=arrancar_proceso)
    hilo.daemon = True
    hilo.start()
    
    app.run(host="0.0.0.0", port=puerto)
