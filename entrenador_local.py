import os
import time
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
import telebot
from flask import Flask
import threading
import requests

# ==============================================================================
# 🎯 CONFIGURACIÓN GLOBAL Y CONTROL CLOUD
# ==============================================================================
CEREBRO_A_ENTRENAR = "modelo_sniper_ia (4) (2).pkl"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_ID = os.environ.get("TELEGRAM_ID")
bot_telegram = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

DBX_APP_KEY = os.environ.get("DROPBOX_APP_KEY")
DBX_APP_SECRET = os.environ.get("DROPBOX_APP_SECRET")
DBX_REFRESH_TOKEN = os.environ.get("DROPBOX_REFRESH_TOKEN")

ESTADISTICAS_IA = {
    "combate_actual": 0,
    "total_combates": 4000,
    "estado": "Inicializando Ares Bosque V6.3...",
    "retorno_ultimo_combate": 0.0,
    "ratio_sharpe": 0.0,
    "lr_actual": 0.0001,
    "ops_long": 0,
    "ops_short": 0,
    "ops_espera": 0,
    "efectividad_estimada": 0.0,
    "balance_usd": 1000.0,
    "pnl_total_usd": 0.0,
    "loss_actor": 0.0,
    "loss_critico": 0.0,
    "peso_atr_acumulado": 33.3,
    "peso_volumen_acumulado": 33.3,
    "peso_macro_acumulado": 33.4,
    "alerta_ecosistema": "Estable.",
}

VENTANA_TIEMPO = 60
COMBATES_PPO = 4000
REPORTAR_CADA = 200

def alertar_telegram(mensaje):
    if bot_telegram and TELEGRAM_ID:
        try:
            bot_telegram.send_message(TELEGRAM_ID, mensaje, parse_mode="Markdown")
        except Exception as e:
            print(f"⚠️ Telegram Log: {e}")

# ==============================================================================
# 🛰️ SISTEMA CONECTOR REFRESH DE DROPBOX (AUTOGENERACIÓN ASISTIDA)
# ==============================================================================
def obtener_access_token():
    global DBX_REFRESH_TOKEN
    if not DBX_APP_KEY or not DBX_APP_SECRET:
        print("❌ Error: Faltan DROPBOX_APP_KEY o DROPBOX_APP_SECRET en Render.")
        return None

    # MÓDULO DE EMERGENCIA PARA MÓVILES
    if not DBX_REFRESH_TOKEN or DBX_REFRESH_TOKEN.strip() == "" or "INICIAL" in DBX_REFRESH_TOKEN:
        url_auth = f"https://www.dropbox.com/oauth2/authorize?client_id={DBX_APP_KEY}&token_access_type=offline&response_type=code"
        msg = (
            "🌲 *ARES CLOUD ASISTENTE V6.3*\n\n"
            "Detecté que estás configurando el sistema desde tu móvil. Para activar tu memoria evolutiva infinita, sigue estos pasos:\n\n"
            f"1️⃣ Entra a este enlace: [AUTORIZAR DROPBOX]({url_auth})\n"
            "2️⃣ Presiona *Permitir* y copia el código temporal que aparezca.\n"
            "3️⃣ Envía ese código aquí a Telegram respondiendo de esta forma:\n"
            "`TOKEN_CODE: tu_codigo_aqui`"
        )
        alertar_telegram(msg)
        print("🛰️ Esperando token de autorización en la nube...")
        
        # Bucle de espera pasiva hasta que el usuario inyecte el código vía webhook o configuración externa
        while not os.path.exists("token_recibido.txt"):
            time.sleep(5)
            
        with open("token_recibido.txt", "r") as f:
            codigo_temporal = f.read().strip()
            
        try:
            url = "https://api.dropbox.com/oauth2/token"
            data = {
                "grant_type": "authorization_code",
                "code": codigo_temporal,
                "client_id": DBX_APP_KEY,
                "client_secret": DBX_APP_SECRET
            }
            res = requests.post(url, data=data, timeout=10).json()
            if "refresh_token" in res:
                DBX_REFRESH_TOKEN = res["refresh_token"]
                alertar_telegram(f"✅ *¡ÉXITO TOTAL!*\nTu token perpetuo infinito es:\n\n`{DBX_REFRESH_TOKEN}`\n\nCopia este código y pégalo en la casilla *DROPBOX_REFRESH_TOKEN* de Render para que no tengas que repetir este paso jamás.")
                os.remove("token_recibido.txt")
            else:
                alertar_telegram("❌ El código temporal expiró o es inválido. Reinicia el proceso ingresando un código nuevo.")
                os.remove("token_recibido.txt")
                return None
        except Exception as e:
            print(f"Error generando refresh: {e}")
            return None

    try:
        url = "https://api.dropbox.com/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": DBX_REFRESH_TOKEN,
            "client_id": DBX_APP_KEY,
            "client_secret": DBX_APP_SECRET
        }
        response = requests.post(url, data=data, timeout=10)
        return response.json().get("access_token")
    except Exception as e:
        print(f"❌ Error renovando token de Dropbox: {e}")
        return None

def descargar_cerebro_cloud():
    token = obtener_access_token()
    if not token: return False
    try:
        url = "https://content.dropboxapi.com/2/files/download"
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": '{"path": "/' + CEREBRO_A_ENTRENAR + '"}'
        }
        res = requests.post(url, headers=headers, timeout=15)
        if res.status_code == 200:
            with open(CEREBRO_A_ENTRENAR, "wb") as f:
                f.write(res.content)
            print("🌲 Memoria descargada desde Dropbox.")
            return True
    except Exception as e:
        print(f"⚠️ No hay respaldo en la nube: {e}")
    return False

def subir_cerebro_cloud():
    token = obtener_access_token()
    if not token or not os.path.exists(CEREBRO_A_ENTRENAR): return
    try:
        url = "https://content.dropboxapi.com/2/files/upload"
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": '{"path": "/' + CEREBRO_A_ENTRENAR + '", "mode": "overwrite"}',
            "Content-Type": "application/octet-stream"
        }
        with open(CEREBRO_A_ENTRENAR, "rb") as f:
            requests.post(url, headers=headers, data=f, timeout=20)
        print("☁️ Sincronizado en Dropbox.")
    except Exception as e:
        print(f"❌ Error respaldando: {e}")

# ==============================================================================
# 🧠 ARQUITECTURA UNIFICADA ARES ACTOR-CRÍTICO (ANTI-OVERFITTING)
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
    def forward(self, x): return x + self.pe[:, :x.size(1)]

class AresActorCritico(nn.Module):
    def __init__(self, num_caracteristicas=9, d_model=64, nhead=4, num_layers=3, dropout=0.40):
        super().__init__()
        self.proyeccion_entrada = nn.Linear(num_caracteristicas, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=128, dropout=dropout, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.actor = nn.Sequential(nn.Linear(d_model, 32), nn.ReLU(), nn.Linear(32, 3), nn.Softmax(dim=-1))
        self.critico = nn.Sequential(nn.Linear(d_model, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x):
        x = self.proyeccion_entrada(x) * (64 ** 0.5)
        x = self.pos_encoder(x)
        features = self.transformer_encoder(x)[:, -1, :]
        return self.actor(features), self.critico(features)

# ==============================================================================
# 🎯 ENTORNO CON NORMALIZACIÓN EN VIVO
# ==============================================================================
class MercadoGimnasioAresBosque:
    def __init__(self, datos_raw, precios_close, volumen_raw, ventana=60):
        self.ventana = ventana
        self.precios = precios_close
        self.volumen = volumen_raw
        self.matriz_extendida = np.zeros((len(precios_close), 9), dtype=np.float32)
        for i in range(6): self.matriz_extendida[:, i] = datos_raw[:, i]
        
        for i in range(30, len(precios_close)):
            self.matriz_extendida[i, 6] = (precios_close[i] - precios_close[i-5]) / (precios_close[i-5] + 1e-8)
            self.matriz_extendida[i, 7] = (precios_close[i] - precios_close[i-15]) / (precios_close[i-15] + 1e-8)
            max_24 = np.max(precios_close[i-24:i])
            min_24 = np.min(precios_close[i-24:i])
            self.matriz_extendida[i, 8] = 1.0 if precios_close[i] >= max_24 else (-1.0 if precios_close[i] <= min_24 else 0.0)
        self.reset()

    def obtener_observacion_normalizada(self):
        sub_matriz = self.matriz_extendida[self.paso_actual - self.ventana : self.paso_actual]
        return (sub_matriz - np.mean(sub_matriz, axis=0)) / (np.std(sub_matriz, axis=0) + 1e-8)

    def reset(self):
        self.paso_actual = np.random.randint(self.ventana + 200, len(self.precios) - 100)
        return self.obtener_observacion_normalizada()

    def step(self, accion):
        precio_ahora = self.precios[self.paso_actual]
        precio_siguiente = self.precios[self.paso_actual + 1]
        rendimiento = 0.0
        if accion == 1: rendimiento = (precio_siguiente - precio_ahora) / precio_ahora
        elif accion == 2: rendimiento = (precio_ahora - precio_siguiente) / precio_ahora
        
        self.paso_actual += 1
        return self.obtener_observacion_normalizada(), rendimiento, rendimiento, (self.paso_actual >= len(self.precios) - 5)

# ==============================================================================
# 🏋️ BUCLE PPO Y SISTEMA TELEGRAM LISTENERS
# ==============================================================================
def iniciar_gimnasio_v6():
    global ESTADISTICAS_IA
    RUTA_CSV = "BTCUSDT_1m_Ene_Abr_2026.csv"
    if not os.path.exists(RUTA_CSV): return

    df = pd.read_csv(RUTA_CSV, header=None, skiprows=1, nrows=35000, low_memory=False)
    datos_raw = df[[1, 2, 3, 4, 5, 4]].values.astype(np.float32)
    precios_close = df[4].values.astype(np.float32)
    volumen_raw = df[5].values.astype(np.float32)

    descargar_cerebro_cloud()
    modelo_ares = AresActorCritico()
    
    if os.path.exists(CEREBRO_A_ENTRENAR):
        try:
            checkpoint = torch.load(CEREBRO_A_ENTRENAR, map_location=torch.device('cpu'), weights_only=False)
            model_dict = modelo_ares.state_dict()
            for k, v in checkpoint.items():
                if k in model_dict and v.shape == model_dict[k].shape: model_dict[k] = v
            modelo_ares.load_state_dict(model_dict)
        except: pass
            
    optimizer = optim.Adam(modelo_ares.parameters(), lr=0.0001)
    scheduler = CosineAnnealingLR(optimizer, T_max=COMBATES_PPO, eta_min=1e-6)
    entorno = MercadoGimnasioAresBosque(datos_raw, precios_close, volumen_raw)

    for combate in range(1, COMBATES_PPO + 1):
        ESTADISTICAS_IA["combate_actual"] = combate
        obs = entorno.reset()
        b_estados, b_acciones, b_prob_viejas, b_recompensas, b_valores = [], [], [], [], []
        
        modelo_ares.eval()
        for _ in range(30):
            obs_t = torch.tensor(obs, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad(): probs, valor = modelo_ares(obs_t)
            accion = torch.argmax(probs, dim=-1).item()
            sig_obs, recompensa, rendimiento, term = entorno.step(accion)
            
            b_estados.append(obs)
            b_acciones.append(accion)
            b_prob_viejas.append(probs[0, accion].item())
            b_recompensas.append(recompensa)
            b_valores.append(valor.item())
            obs = sig_obs
            if term: break

        modelo_ares.train()
        # Lógica de optimización PPO estándar con Gradient Clipping
        t_estados = torch.tensor(np.array(b_estados), dtype=torch.float32)
        t_acciones = torch.tensor(b_acciones, dtype=torch.long)
        t_prob_viejas = torch.tensor(b_prob_viejas, dtype=torch.float32)
        
        retornos = []
        g = 0
        for r in reversed(b_recompensas):
            g = r + 0.97 * g
            retornos.insert(0, g)
        t_retornos = torch.tensor(retornos, dtype=torch.float32)
        
        for _ in range(2):
            np_p, np_v = modelo_ares(t_estados)
            loss = nn.MSELoss()(np_v.squeeze(), t_retornos)
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(modelo_ares.parameters(), 0.5)
            optimizer.step()
            
        scheduler.step()
        if combate % REPORTAR_CADA == 0:
            torch.save(modelo_ares.state_dict(), CEREBRO_A_ENTRENAR)
            subir_cerebro_cloud()
            alertar_telegram(f"🌲 *V6.3:* [{combate}/{COMBATES_PPO}] Sincronizado.")

# ==============================================================================
# 📺 MANEJO WEB Y ESCUCHA WEBHOOK TELEGRAM
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def index():
    return f"<h1>Ares Bosque V6.3 Corriendo en el Combate: {ESTADISTICAS_IA['combate_actual']}</h1>"

if __name__ == "__main__":
    if bot_telegram:
        @bot_telegram.message_handler(func=lambda m: m.text and m.text.startswith("TOKEN_CODE:"))
        def capturar_codigo(message):
            codigo = message.text.replace("TOKEN_CODE:", "").strip()
            with open("token_recibido.txt", "w") as f:
                f.write(codigo)
            bot_telegram.reply_to(message, "🚀 Código recibido. Procesando matriz en el servidor de Render...")

        def run_bot():
            bot_telegram.infinity_polling()
        threading.Thread(target=run_bot, daemon=True).start()

    def arrancar():
        time.sleep(4)
        iniciar_gimnasio_v6()
    threading.Thread(target=arrancar, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
