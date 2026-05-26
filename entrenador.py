import os
import time
import requests
import zipfile
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
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

# Parámetros de Red
VENTANA_TIEMPO = 60
BATCH_SIZE = 128
EPOCHS_ESCUELA = 150  # Entrenamiento ultra profundo para buscar patrones globales
COMBATES_PPO = 5000   # Más peleas en el gimnasio para perfeccionar reflejos de riesgo

# ==============================================================================
# ARQUITECTURA DEL TRANSFORMER (CEREBRO TEÓRICO)
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

    def forward(self, x):
        return x + self.pe[:, :x.size(1)]

class TransformerAnalista(nn.Module):
    def __init__(self, num_caracteristicas=6, d_model=64, nhead=4, num_layers=3, dropout=0.3):
        super().__init__()
        self.proyeccion_entrada = nn.Linear(num_caracteristicas, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dropout=dropout, batch_first=True)
        # max_depth conceptual controlado mediante num_layers limitado y alto dropout
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

    def forward(self, x):
        x = self.proyeccion_entrada(x) * (64 ** 0.5)
        x = self.pos_encoder(x)
        return self.transformer_encoder(x)[:, -1, :]

class DatasetEscuela(Dataset):
    def __init__(self, datos_raw, ventana=60):
        self.medias = np.mean(datos_raw, axis=0)
        self.desviaciones = np.std(datos_raw, axis=0) + 1e-8
        self.datos = (datos_raw - self.medias) / self.desviaciones
        self.ventana = ventana

    def __len__(self):
        return len(self.datos) - self.ventana

    def __getitem__(self, idx):
        return torch.tensor(self.datos[idx : idx + self.ventana]), torch.tensor(self.datos[idx + self.ventana])

# ==============================================================================
# GIMNASIO OPERATIVO (AGENTE PPO DE TOMA DE DECISIONES)
# ==============================================================================
class MercadoGimnasio:
    def __init__(self, datos_raw, precios_close, ventana=60):
        self.datos_raw = datos_raw
        self.precios = precios_close
        self.ventana = ventana
        self.reset()

    def reset(self):
        self.paso_actual = np.random.randint(self.ventana, len(self.precios) - 100)
        return self.datos_raw[self.paso_actual - self.ventana : self.paso_actual]

    def step(self, accion):
        precio_ahora = self.precios[self.paso_actual]
        precio_siguiente = self.precios[self.paso_actual + 1]
        recompensa = 0.0
        
        if accion == 1: # COMPRA
            rendimiento = (precio_siguiente - precio_ahora) / precio_ahora
            recompensa = rendimiento * 100.0
            if rendimiento < 0: recompensa *= 3.0 # Penalización estricta por riesgo
        elif accion == 2: # VENTA
            rendimiento = (precio_ahora - precio_siguiente) / precio_ahora
            recompensa = rendimiento * 100.0
            if rendimiento < 0: recompensa *= 3.0
            
        self.paso_actual += 1
        terminado = (self.paso_actual >= len(self.precios) - 2)
        return self.datos_raw[self.paso_actual - self.ventana : self.paso_actual], recompensa, terminado

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
# MOTOR CENTRAL DE TRABAJO PESADO
# ==============================================================================
def descargar_datos_binance():
    url = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2026-01.zip"
    ruta_zip, ruta_csv = "data.zip", "BTCUSDT-1m-2026-01.csv"
    res = requests.get(url)
    if res.status_code == 200:
        with open(ruta_zip, "wb") as f: f.write(res.content)
        with zipfile.ZipFile(ruta_zip, "r") as z: z.extractall(".")
        os.remove(ruta_zip)
        df = pd.read_csv(ruta_csv, header=None)
        columnas = [0, 1, 2, 3, 4, 5, 9] # OHLCV + Taker Vol
        datos = df[columnas].values.astype(np.float32)
        os.remove(ruta_csv)
        return datos
    return None

def ejecutar_entrenamiento_completo():
    print("⏳ Descargando bloques históricos desde el nodo central...")
    alertar_telegram("🚀 *Fábrica de IA Iniciada:* Descargando datos masivos de Binance desde Render...")
    
    datos_mercado = descargar_datos_binance()
    if datos_mercado is None:
        alertar_telegram("❌ Error crítico al descargar datos de origen.")
        return
        
    precios_close = datos_mercado[:, 3] # Columna Close
    datos_features = datos_mercado[:, [0, 1, 2, 3, 4, 5]] # Quitamis marcas de tiempo para procesar
    
    # --- FASE 1: LA ESCUELA DE ANÁLISIS ---
    dataset = DatasetEscuela(datos_features, ventana=VENTANA_TIEMPO)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    
    escuela = TransformerAnalista()
    criterion = nn.MSELoss()
    optimizer_esc = optim.AdamW(escuela.parameters(), lr=0.0003, weight_decay=1e-3)
    
    alertar_telegram("🎓 *Fase 1 Activada:* El Transformer ha entrado a las clases intensivas de regularización.")
    
    for epoch in range(1, EPOCHS_ESCUELA + 1):
        escuela.train()
        loss_epoch = 0.0
        for lx, ly in dataloader:
            optimizer_esc.zero_grad()
            pred = escuela(lx)
            loss = criterion(pred, ly)
            loss.backward()
            optimizer_esc.step()
            loss_epoch += loss.item()
            
        if epoch % 25 == 0:
            alertar_telegram(f"📖 *Progreso Escuela:* Vuelta [{epoch}/{EPOCHS_ESCUELA}] | Error de patrones: {loss_epoch/len(dataloader):.5f}")

    # --- FASE 2: EL GIMNASIO DE RIESGO PPO ---
    entorno = MercadoGimnasio(datos_features, precios_close, ventana=VENTANA_TIEMPO)
    bot_ppo = AgentePPO()
    optimizer_ppo = optim.Adam(bot_ppo.parameters(), lr=0.0002)
    escuela.eval()
    
    alertar_telegram("🥊 *Fase 2 Activada:* El Agente PPO inicia combates tácticos en la simulación de mercado.")
    
    for combate in range(1, COMBATES_PPO + 1):
        obs = entorno.reset()
        recompensa_total = 0.0
        
        for _ in range(60): # Sesiones de 60 minutos alternas
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
            alertar_telegram(f"🏋️ *Progreso Gimnasio:* Combate [{combate}/{COMBATES_PPO}] | Factor de Rendimiento: {recompensa_total:.4f}")

    # --- FASE 3: CONSOLIDACIÓN Y GRADUACIÓN ---
    torch.save(escuela.state_dict(), "transformer_arquitecto.pt")
    torch.save(bot_ppo.state_dict(), "bot_ppo_graduado.pt")
    np.save("medias.npy", dataset.medias)
    np.save("desviaciones.npy", dataset.desviaciones)
    
    alertar_telegram("🏆 *¡IA PRECIOSA GRADUADA CON ÉXITO!* Los archivos neuronales base han sido inyectados localmente en el servidor. Proceso finalizado.")
    print("Graduación completada.")

# Webhook obligatorio de supervivencia para Render
app = Flask(__name__)
@app.route('/')
def index(): return "Fábrica de Inteligencia Artificial Activa y Trabajando..."

if __name__ == "__main__":
    hilo = threading.Thread(target=ejecutar_entrenamiento_completo)
    hilo.daemon = True
    hilo.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
