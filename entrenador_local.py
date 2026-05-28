import os
import time
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
import telebot
from flask import Flask, send_file, redirect
import threading
import requests

# ==============================================================================
# 🎯 CONTROL DE VERSIONES Y CONFIGURACIÓN CLOUD
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
    "estado": "Inicializando Ares Bosque V6.3 Perpetuo...",
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
    "ops_consecutivas_direccion": 0,
    "ultima_direccion": 0,
    "alerta_ecosistema": "Estable. Memoria unificada activa.",
    "errores_indicador": "Ninguno"
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
# 🛰️ SISTEMA CONECTOR REFRESH DE DROPBOX (MEMORIA INFINITA)
# ==============================================================================
def obtener_access_token():
    """Intercambia el Refresh Token Perpetuo por una llave temporal de acceso"""
    if not DBX_APP_KEY or not DBX_APP_SECRET or not DBX_REFRESH_TOKEN:
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
    if not token: 
        print("⚠️ Saltando descarga: Faltan credenciales Cloud.")
        return False
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
            print("🌲 Memoria evolutiva descargada con éxito desde Dropbox.")
            return True
    except Exception as e:
        print(f"⚠️ No hay respaldo previo en la nube: {e}")
    return False

def subir_cerebro_cloud():
    token = obtener_access_token()
    if not token or not os.path.exists(CEREBRO_A_ENTRENAR): 
        return
    try:
        url = "https://content.dropboxapi.com/2/files/upload"
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": '{"path": "/' + CEREBRO_A_ENTRENAR + '", "mode": "overwrite"}',
            "Content-Type": "application/octet-stream"
        }
        with open(CEREBRO_A_ENTRENAR, "rb") as f:
            requests.post(url, headers=headers, data=f, timeout=20)
        print("☁️ Respaldo de seguridad sincronizado en Dropbox exitosamente.")
    except Exception as e:
        print(f"❌ Error respaldando en la nube: {e}")

# ==============================================================================
# 🧠 ARQUITECTURA UNIFICADA ARES ACTOR-CRÍTICO (CON GRADIENTES ACTIVOS)
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

class AresActorCritico(nn.Module):
    """El Transformer procesa todo con gradientes activos para evitar desajustes"""
    def __init__(self, num_caracteristicas=9, d_model=64, nhead=4, num_layers=3, dropout=0.40):
        super().__init__()
        self.proyeccion_entrada = nn.Linear(num_caracteristicas, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        
        # ESCUDO ANTI-SOBREAJUSTE: Aumento de Dropout a 0.40
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=128, dropout=dropout, batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Cabezales unificados
        self.actor = nn.Sequential(
            nn.Linear(d_model, 32), nn.ReLU(), nn.Linear(32, 3), nn.Softmax(dim=-1)
        )
        self.critico = nn.Sequential(
            nn.Linear(d_model, 32), nn.ReLU(), nn.Linear(32, 1)
        )

    def forward(self, x):
        x = self.proyeccion_entrada(x) * (64 ** 0.5)
        x = self.pos_encoder(x)
        features = self.transformer_encoder(x)[:, -1, :] # Vector de Contexto Puro (Último token)
        
        probs = self.actor(features)
        valor = self.critico(features)
        return probs, valor

# ==============================================================================
# 🎯 ENTORNO QUANT CON NORMALIZACIÓN EN VIVO (ANTI DATA LEAKAGE)
# ==============================================================================
class MercadoGimnasioAresBosque:
    def __init__(self, datos_raw, precios_close, volumen_raw, ventana=60):
        self.ventana = ventana
        self.precios = precios_close
        self.volumen = volumen_raw
        
        self.matriz_extendida = np.zeros((len(precios_close), 9), dtype=np.float32)
        for i in range(6):
            self.matriz_extendida[:, i] = datos_raw[:, i]
            
        print("🌲 Generando Ratios de Aceleración Macro V6.3...")
        for i in range(30, len(precios_close)):
            retorno_5m = (precios_close[i] - precios_close[i-5]) / (precios_close[i-5] + 1e-8)
            retorno_15m = (precios_close[i] - precios_close[i-15]) / (precios_close[i-15] + 1e-8)
            max_24 = np.max(precios_close[i-24:i])
            min_24 = np.min(precios_close[i-24:i])
            rango_ptj = 1.0 if precios_close[i] >= max_24 else (-1.0 if precios_close[i] <= min_24 else 0.0)
            
            self.matriz_extendida[i, 6] = retorno_5m
            self.matriz_extendida[i, 7] = retorno_15m
            self.matriz_extendida[i, 8] = rango_ptj

        self.reset()

    def obtener_observacion_normalizada(self):
        """ONLINE SCALING: Extrae escala solo del pasado inmediato para evitar fugas"""
        sub_matriz = self.matriz_extendida[self.paso_actual - self.ventana : self.paso_actual]
        medias = np.mean(sub_matriz, axis=0)
        desviaciones = np.std(sub_matriz, axis=0) + 1e-8
        return (sub_matriz - medias) / desviaciones

    def reset(self):
        self.paso_actual = np.random.randint(self.ventana + 200, len(self.precios) - 100)
        self.conteo_esperas_seguidas = 0
        return self.obtener_observacion_normalizada()

    def step(self, accion):
        precio_ahora = self.precios[self.paso_actual]
        precio_siguiente = self.precios[self.paso_actual + 1]
        volumen_ahora = self.volumen[self.paso_actual]
        
        precios_ventana = self.precios[self.paso_actual - 14 : self.paso_actual]
        atr_estimado = np.max(precios_ventana) - np.min(precios_ventana)
        volumen_promedio = np.mean(self.volumen[self.paso_actual - 14 : self.paso_actual]) + 1e-6
        ma_macro = np.mean(self.precios[self.paso_actual - 200 : self.paso_actual])
        bosque_alcista = precio_ahora > ma_macro

        ESTADISTICAS_IA["atr_actual"] = float(atr_estimado)
        ESTADISTICAS_IA["volumen_actual"] = float(volumen_ahora)

        if accion == ESTADISTICAS_IA["ultima_direccion"] and accion != 0:
            ESTADISTICAS_IA["ops_consecutivas_direccion"] += 1
        else:
            ESTADISTICAS_IA["ops_consecutivas_direccion"] = 1
            if accion != 0: ESTADISTICAS_IA["ultima_direccion"] = accion

        if accion == 1: ESTADISTICAS_IA["ops_long"] += 1
        elif accion == 2: ESTADISTICAS_IA["ops_short"] += 1
        else: ESTADISTICAS_IA["ops_espera"] += 1
        
        rendimiento = 0.0
        if accion == 1:
            rendimiento = (precio_siguiente - precio_ahora) / precio_ahora
            self.conteo_esperas_seguidas = 0
        elif accion == 2:
            rendimiento = (precio_ahora - precio_siguiente) / precio_ahora
            self.conteo_esperas_seguidas = 0
        else:
            self.conteo_esperas_seguidas += 1

        recompensa = rendimiento
        if accion != 0 and volumen_ahora > volumen_promedio * 1.5: recompensa *= 1.3  
        if accion != 0 and atr_estimado < (np.mean(self.precios) * 0.0005): recompensa *= 0.6  
        if accion != 0 and abs(precio_siguiente - precio_ahora) > atr_estimado and volumen_ahora < volumen_promedio: recompensa -= 0.0005
        if accion == 1 and not bosque_alcista: recompensa *= 0.5
        if accion == 2 and bosque_alcista: recompensa *= 0.5
        if ESTADISTICAS_IA["ops_consecutivas_direccion"] > 5: recompensa -= 0.0003
        if accion == 0 and self.conteo_esperas_seguidas > 5 and volumen_ahora > volumen_promedio: recompensa = -0.0002  

        # Suavizado Exponencial de Atención (EMA)
        total_m = atr_estimado + volumen_ahora + abs(precio_ahora - ma_macro) + 1e-6
        peso_instantaneo_atr = (atr_estimado / total_m) * 100
        peso_instantaneo_vol = (volumen_ahora / total_m) * 100
        peso_instantaneo_mac = (abs(precio_ahora - ma_macro) / total_m) * 100

        ESTADISTICAS_IA["peso_atr_acumulado"] = (ESTADISTICAS_IA["peso_atr_acumulado"] * 0.98) + (peso_instantaneo_atr * 0.02)
        ESTADISTICAS_IA["peso_volumen_acumulado"] = (ESTADISTICAS_IA["peso_volumen_acumulado"] * 0.98) + (peso_instantaneo_vol * 0.02)
        ESTADISTICAS_IA["peso_macro_acumulado"] = (ESTADISTICAS_IA["peso_macro_acumulado"] * 0.98) + (peso_instantaneo_mac * 0.02)

        self.paso_actual += 1
        terminado = (self.paso_actual >= len(self.precios) - 5)
        return self.obtener_observacion_normalizada(), recompensa, rendimiento, terminado

# ==============================================================================
# 🏋️ BUCLE DE EVOLUCIÓN COMPACTA PPO (CON BUFFER DE TRAYECTORIAS REAL)
# ==============================================================================
def iniciar_gimnasio_v6():
    global ESTADISTICAS_IA
    RUTA_CSV = "BTCUSDT_1m_Ene_Abr_2026.csv"
    
    if not os.path.exists(RUTA_CSV):
        ESTADISTICAS_IA["estado"] = "❌ Alerta: Falta el archivo histórico CSV."
        return

    try:
        df = pd.read_csv(RUTA_CSV, header=None, skiprows=1, nrows=35000, low_memory=False)
        datos_raw = df[[1, 2, 3, 4, 5, 4]].values.astype(np.float32)
        precios_close = df[4].values.astype(np.float32)
        volumen_raw = df[5].values.astype(np.float32)
        del df
    except Exception as e:
        ESTADISTICAS_IA["estado"] = f"❌ Error CSV: {str(e)}"
        return

    # Descargar la última memoria de la nube si existe antes de inicializar la red
    descargar_cerebro_cloud()

    modelo_ares = AresActorCritico()
    
    # Inyección adaptativa limpia si existe archivo local o descargado
    if os.path.exists(CEREBRO_A_ENTRENAR):
        try:
            checkpoint = torch.load(CEREBRO_A_ENTRENAR, map_location=torch.device('cpu'), weights_only=False)
            model_dict = modelo_ares.state_dict()
            for k, v in checkpoint.items():
                if k in model_dict and v.shape == model_dict[k].shape:
                    model_dict[k] = v
                elif "proyeccion_entrada.weight" in k:
                    with torch.no_grad():
                        [span_1](start_span)[span_2](start_span)model_dict[k][:, :6] = v # Relleno molecular adaptativo[span_1](end_span)[span_2](end_span)
            modelo_ares.load_state_dict(model_dict)
            ESTADISTICAS_IA["estado"] = "🌲 Memoria Unificada de Gradiente Conectada V6.3"
        except Exception as e:
            ESTADISTICAS_IA["estado"] = f"⚠️ Adaptación Incompleta: {str(e)}"
            
    optimizer = optim.Adam(modelo_ares.parameters(), lr=0.0001)
    scheduler = CosineAnnealingLR(optimizer, T_max=COMBATES_PPO, eta_min=1e-6)
    entorno = MercadoGimnasioAresBosque(datos_raw, precios_close, volumen_raw, ventana=VENTANA_TIEMPO)
    
    alertar_telegram("🌲 *Ares Bosque V6.3 Online:* Modo Anti-Sobreajuste y Sincronización Cloud Activa.")

    ops_ganadas_acumuladas = 0
    ops_totales_acumuladas = 0

    for combate in range(1, COMBATES_PPO + 1):
        ESTADISTICAS_IA["combate_actual"] = combate
        obs = entorno.reset()
        
        # BUFFERS DE TRAYECTORIA DE PPO REAL
        b_estados, b_acciones, b_prob_viejas, b_recompensas, b_valores = [], [], [], [], []
        historial_rendimientos = []
        
        modelo_ares.eval() # Modo inferencia rápida durante el combate
        for _ in range(30):
            obs_t = torch.tensor(obs, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                probs, valor = modelo_ares(obs_t)
            
            accion = torch.argmax(probs, dim=-1).item()
            prob_accion = probs[0, accion].item()
            
            sig_obs, recompensa, rendimiento, term = entorno.step(accion)
            
            # Almacenar experiencias
            b_estados.append(obs)
            b_acciones.append(accion)
            b_prob_viejas.append(prob_accion)
            b_recompensas.append(recompensa)
            b_valores.append(valor.item())
            historial_rendimientos.append(rendimiento)
            
            obs = sig_obs
            
            if accion != 0:
                ops_totales_acumuladas += 1
                ESTADISTICAS_IA["balance_usd"] += ESTADISTICAS_IA["balance_usd"] * rendimiento
                ESTADISTICAS_IA["pnl_total_usd"] = ESTADISTICAS_IA["balance_usd"] - 1000.0
                if rendimiento > 0: ops_ganadas_acumuladas += 1
            if term: break
            
        # ==============================================================================
        # 🔥 FASE DE OPTIMIZACIÓN CLIPPED PPO REAL (AL TERMINAR EL COMBATE)
        # ==============================================================================
        [span_3](start_span)modelo_ares.train() # Encendemos gradientes y dropout[span_3](end_span)
        
        t_estados = torch.tensor(np.array(b_estados), dtype=torch.float32)
        t_acciones = torch.tensor(b_acciones, dtype=torch.long)
        t_prob_viejas = torch.tensor(b_prob_viejas, dtype=torch.float32)
        
        # Calcular retornos descontados históricos
        retornos = []
        g_descontado = 0
        for r in reversed(b_recompensas):
            g_descontado = r + (0.97 * g_descontado) # Factor de descuento
            retornos.insert(0, g_descontado)
        t_retornos = torch.tensor(retornos, dtype=torch.float32)
        t_valores = torch.tensor(b_valores, dtype=torch.float32)
        
        # Ventaja Clásica PPO
        ventajas = t_retornos - t_valores.detach()
        
        # 4 Épocas de repaso intensivo por combate (Buffer Optimization)
        for _ in range(4):
            nuevas_probs, nuevos_valores = modelo_ares(t_estados)
            nuevos_valores = nuevos_valores.squeeze()
            
            prob_especificas = nuevas_probs.gather(1, t_acciones.unsqueeze(1)).squeeze()
            ratios = prob_especificas / (t_prob_viejas + 1e-8)
            
            # Pérdida Clipada de PPO
            surr1 = ratios * ventajas
            surr2 = torch.clamp(ratios, 1.0 - 0.2, 1.0 + 0.2) * ventajas
            loss_actor = -torch.min(surr1, surr2).mean()
            
            # Pérdida de función de valor (Crítico)
            loss_critico = nn.MSELoss()(nuevos_valores, t_retornos)
            
            # Factor de entropía dinámico para forzar la curiosidad de la IA
            entropia = -(nuevas_probs * torch.log(nuevas_probs + 1e-8)).mean()
            
            loss_total = loss_actor + 0.5 * loss_critico - 0.01 * entropia
            
            optimizer.zero_grad()
            loss_total.backward()
            # ESCUDO CRÍTICO: Gradient Clipping para proteger el Transformer
            nn.utils.clip_grad_norm_(modelo_ares.parameters(), max_norm=0.5)
            optimizer.step()
            
        scheduler.step()
        
        # Actualización de Métricas de Control
        ESTADISTICAS_IA["loss_actor"] = float(loss_actor.item())
        ESTADISTICAS_IA["loss_critico"] = float(loss_critico.item())
        ESTADISTICAS_IA["retorno_ultimo_combate"] = float(np.sum(historial_rendimientos))
        if len(historial_rendimientos) > 1 and np.std(historial_rendimientos) > 0:
            ESTADISTICAS_IA["ratio_sharpe"] = float(np.mean(historial_rendimientos) / np.std(historial_rendimientos))
        ESTADISTICAS_IA["lr_actual"] = float(optimizer.param_groups[0]['lr'])
        if ops_totales_acumuladas > 0:
            ESTADISTICAS_IA["efectividad_estimada"] = float(ops_ganadas_acumuladas / ops_totales_acumuladas * 100)

        # Reporte y Sincronización Automática con la Nube
        if combate % REPORTAR_CADA == 0:
            torch.save(modelo_ares.state_dict(), CEREBRO_A_ENTRENAR)
            subir_cerebro_cloud() # Sube el cerebro a Dropbox de forma automática
            alertar_telegram(f"🌲 *V6.3 Cloud:* [{combate}/{COMBATES_PPO}] | Wallet: ${ESTADISTICAS_IA['balance_usd']:.2f} | Sharpe: {ESTADISTICAS_IA['ratio_sharpe']:.4f}")

    torch.save(modelo_ares.state_dict(), CEREBRO_A_ENTRENAR)
    subir_cerebro_cloud()
    ESTADISTICAS_IA["estado"] = "🏆 ¡EVOLUCIÓN MÁXIMA V6.3 PERPETUA COMPLETA!"

# ==============================================================================
# 📺 INTERFAZ INTERACTIVA PREMIUM (FLASK HTML)
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def index():
    color_sharpe = "#00ffcc" if ESTADISTICAS_IA["ratio_sharpe"] >= 0 else "#ff3333"
    color_efectividad = "#ffff00" if ESTADISTICAS_IA["efectividad_estimada"] >= 50.0 else "#aaaaaa"
    color_pnl = "#00ff55" if ESTADISTICAS_IA["pnl_total_usd"] >= 0 else "#ff3333"
    signo_pnl = "+" if ESTADISTICAS_IA["pnl_total_usd"] >= 0 else ""
    
    return f"""
    <html>
        <head>
            <title>Gimnasio Ares Bosque V6.3</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background:#07070f; color:#fff; text-align:center; padding:30px; }}
                .container {{ max-width: 750px; margin: 0 auto; background: #0f0f1f; padding: 25px; border-radius: 12px; border: 1px solid #1c1c3a; }}
                .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; text-align: left; margin-top: 20px; }}
                .card {{ background: #14142b; padding: 15px; border-radius: 6px; border: 1px solid #222244; }}
                .btn {{ display: inline-block; background: #ff5500; color: white; font-weight: bold; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 15px; }}
                .billetera {{ background: #0b1a12; border: 2px solid #00ff55; padding: 15px; border-radius: 8px; margin-top: 15px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🌲 Panel Operativo: V6.3 - Ares Bosque Cloud 🌲</h2>
                <p style="color:#aaa; font-size:14px; margin-top:0;">Algoritmo Unificado PPO con Escudo Anti-Sobreajuste</p>
                
                <div style="padding:10px; margin-bottom:10px; text-align:right;">
                    <a href="/telemetria" class="btn" style="margin:0; background:#4a157d; border: 1px solid #00ffcc; padding:8px 16px;">📊 VER TELEMETRÍA DE ATENCIÓN</a>
                </div>

                <div style="padding:15px; background:#181830; border-radius:8px; font-size:16px; font-weight:bold; color:#ffcc00; border-left: 5px solid #ffcc00;">
                    {ESTADISTICAS_IA["estado"]}
                </div>

                <div class="billetera">
                    <span style="color:#aaa; font-size:13px; font-weight:bold;">💰 WALLET ACTUAL DE PRUEBA 💰</span>
                    <h1 style="margin: 5px 0 0 0; color:#00ff55; font-size:36px;">${ESTADISTICAS_IA["balance_usd"]:.2f} USD</h1>
                    <p style="margin:2px 0 0 0; font-size:15px; font-weight:bold; color:{color_pnl};">PnL Total: {signo_pnl}${ESTADISTICAS_IA["pnl_total_usd"]:.2f} USD</p>
                </div>

                <div class="grid">
                    <div class="card">
                        <p>🎯 <b>Combate:</b> {ESTADISTICAS_IA["combate_actual"]} / {ESTADISTICAS_IA["total_combates"]}</p>
                        <p>📉 <b>LR Actual:</b> <span style="color:#00ffcc;">{ESTADISTICAS_IA["lr_actual"]:.7f}</span></p>
                        <p>📉 <b>Pérdida Actor:</b> {ESTADISTICAS_IA["loss_actor"]:.5f}</p>
                        <p>📈 <b>Pérdida Crítico:</b> {ESTADISTICAS_IA["loss_critico"]:.5f}</p>
                    </div>
                    <div class="card">
                        <p>📊 <b>Ratio Sharpe:</b> <span style="color:{color_sharpe}; font-size:18px; font-weight:bold;">{ESTADISTICAS_IA["ratio_sharpe"]:.4f}</span></p>
                        <p>🔥 <b>Efectividad Real:</b> <span style="color:{color_efectividad}; font-size:18px; font-weight:bold;">{ESTADISTICAS_IA["efectividad_estimada"]:.2f}%</span></p>
                    </div>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/telemetria')
def telemetria():
    return f"""
    <html>
        <head>
            <title>Telemetría - Ares Bosque</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; background:#07070f; color:#fff; padding:30px; text-align:center; }}
                .container {{ max-width: 750px; margin: 0 auto; background: #0f0f1f; padding: 25px; border-radius: 12px; }}
                .barra-contenedor {{ background: #222; border-radius: 8px; margin: 10px 0; overflow: hidden; }}
                .barra {{ height: 25px; line-height: 25px; color: black; font-weight: bold; padding-left: 10px; transition: 0.5s; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 style="color:#00ffcc;">📊 Distribución de Atención de la Red (Filtro Movilizado)</h2>
                <br>
                <p style="text-align:left;">⚡ <b>Ecosistema Volatilidad (ATR): {ESTADISTICAS_IA["peso_atr_acumulado"]:.1f}%</b></p>
                <div class="barra-contenedor"><div class="barra" style="width: {ESTADISTICAS_IA["peso_atr_acumulado"]}%; background: #ffff00;"></div></div>
                
                <p style="text-align:left;">📊 <b>Ecosistema Volumen (Simons): {ESTADISTICAS_IA["peso_volumen_acumulado"]:.1f}%</b></p>
                <div class="barra-contenedor"><div class="barra" style="width: {ESTADISTICAS_IA["peso_volumen_acumulado"]}%; background: #00ff55;"></div></div>
                
                <p style="text-align:left;">🌲 <b>Ecosistema Macro (Tudor Jones): {ESTADISTICAS_IA["peso_macro_acumulado"]:.1f}%</b></p>
                <div class="barra-contenedor"><div class="barra" style="width: {ESTADISTICAS_IA["peso_macro_acumulado"]}%; background: #00ffcc;"></div></div>
                <br>
                <a href="/" style="color:#00ffcc; text-decoration:none;">⬅️ Regresar al Panel Principal</a>
            </div>
        </body>
    </html>
    """

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 10000))
    def arrancar():
        time.sleep(2)
        iniciar_gimnasio_v6()
    t = threading.Thread(target=arrancar)
    t.daemon = True
    t.start()
    app.run(host="0.0.0.0", port=puerto)
