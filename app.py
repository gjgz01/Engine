import os
import re
import glob
import urllib.parse
import time
import random
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
from PIL import Image

# 1. SETUP DE CARPETAS Y CONFIGURACIÓN BÁSICA
os.makedirs("saves", exist_ok=True)
os.makedirs("universes", exist_ok=True)

st.set_page_config(page_title="Universal RPG Engine", layout="wide")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except FileNotFoundError:
    api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.warning("⚠️ Ingresa tu GEMINI_API_KEY en secrets.toml o variables de entorno para empezar.")
    st.stop()

@st.cache_resource
def get_gemini_client(key):
    return genai.Client(api_key=key)

client = get_gemini_client(api_key)

# Inicialización de estados clave (100% Genérico)
if "lore_text" not in st.session_state:
    st.session_state.lore_text = """Mundo: Universal RPG
[UNIVERSO Y TÉTRADA VISUAL]
Mundo: Universal RPG. Tono: Ficción Interactiva Adaptable.
Tema Visual Sugerido: #0d1117 | #c9d1d9 | #9370DB | monospace

[PROTAGONISTA]
Nombre: Protagonista. Clase: Aventurero.

[SITUACIÓN INICIAL]
Comienza la aventura en un punto de origen neutral a la espera de definiciones del jugador."""

if "active_save_file" not in st.session_state:
    st.session_state.active_save_file = None

if "cg_gallery" not in st.session_state:
    st.session_state.cg_gallery = []

if "last_img_error" not in st.session_state:
    st.session_state.last_img_error = None

# --- DICCIONARIO DE AUDIO ADAPTATIVO ---
AUDIO_TRACKS = {
    "Combate": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3",
    "Tensión": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-16.mp3",
    "Exploración": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3",
    "Misterio": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3",
    "Romance": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
    "Cyberpunk": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
    "Melancolía": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3",
    "Suspenso": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-12.mp3",
    "Acción Épica": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-14.mp3",
    "Silencio": ""
}

# --- FUNCIÓN CIRUJANO DE GUARDADO ---
def update_save_file(original_data, new_turn_text):
    if not original_data:
        return f"1. PERFIL DEL PERSONAJE Y ESTADÍSTICAS\n(Agrega datos)\n\n2. HISTORIAL RECIENTE Y NARRATIVA ACTIVA\n{new_turn_text}"
    
    pattern = r'<TEMA>.*?</OPCIONES>'
    if re.search(pattern, original_data, re.DOTALL):
        return re.sub(pattern, new_turn_text, original_data, flags=re.DOTALL)
    elif "<NARRATIVA>" in original_data:
        pattern_fallback = r'<NARRATIVA>.*?</OPCIONES>'
        return re.sub(pattern_fallback, new_turn_text, original_data, flags=re.DOTALL)
    else:
        return original_data + "\n\n2. HISTORIAL RECIENTE Y NARRATIVA ACTIVA\n" + new_turn_text

# --- DETECTORES AUTOMÁTICOS DINÁMICOS ---
def get_universe_title():
    lore = st.session_state.get("lore_text", "")
    for line in lore.split('\n'):
        if any(k in line.lower() for k in ["mundo:", "universo:", "título:"]):
            parts = line.split(':', 1)
            if len(parts) > 1:
                titulo = re.sub(r'[\*\#\[\]]', '', parts[1]).strip()
                if titulo:
                    return titulo

    match = re.search(r'(?:Mundo|Universo|Título)\s*[:=]\s*([^\n|#]+)', lore, re.IGNORECASE)
    if match:
        return match.group(1).strip()
        
    return "Universal RPG Engine"

def render_themed_header():
    lore = st.session_state.get("lore_text", "").lower()
    title = get_universe_title()
    
    if any(k in lore for k in ["cyberpunk", "hacker", "neon", "sci-fi", "futurista", "mecha", "corporativo", "domo"]):
        bg_gradient = "linear-gradient(90deg, rgba(0,255,157,0.12) 0%, rgba(13,17,23,0.9) 100%)"
        border_color = "#00ff9d"
        text_glow = "0 0 10px rgba(0,255,157,0.6), 0 0 20px rgba(0,255,157,0.2)"
        icon = "⚡"
    elif any(k in lore for k in ["academia", "combate", "escuadrón", "héroe", "poder", "rango", "entrenamiento"]):
        bg_gradient = "linear-gradient(90deg, rgba(138,43,226,0.15) 0%, rgba(13,17,23,0.9) 100%)"
        border_color = "#9370DB"
        text_glow = "0 0 12px rgba(147,112,219,0.7), 0 0 25px rgba(0,255,157,0.3)"
        icon = "⚔️"
    elif any(k in lore for k in ["fantasía", "magia", "espada", "reino", "dragón", "castillo", "medieval"]):
        bg_gradient = "linear-gradient(90deg, rgba(212,175,55,0.15) 0%, rgba(20,15,10,0.9) 100%)"
        border_color = "#d4af37"
        text_glow = "0 0 10px rgba(212,175,55,0.6), 0 0 20px rgba(212,175,55,0.2)"
        icon = "🛡️"
    elif any(k in lore for k in ["terror", "horror", "oscuro", "sangre", "misterio", "psicológico"]):
        bg_gradient = "linear-gradient(90deg, rgba(255,50,50,0.15) 0%, rgba(15,10,10,0.9) 100%)"
        border_color = "#ff3333"
        text_glow = "0 0 10px rgba(255,51,51,0.6), 0 0 20px rgba(255,51,51,0.2)"
        icon = "🩸"
    else:
        bg_gradient = "linear-gradient(90deg, rgba(138,43,226,0.15) 0%, rgba(13,17,23,0.9) 100%)"
        border_color = "#9370DB"
        text_glow = "0 0 12px rgba(147,112,219,0.7), 0 0 25px rgba(0,255,157,0.3)"
        icon = "✨"

    st.markdown(f"""
    <div style="background: {bg_gradient}; border-left: 6px solid {border_color}; border-top: 1px solid {border_color}; border-right: 1px solid {border_color}; border-bottom: 1px solid {border_color}; padding: 18px 24px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
        <h1 style="margin: 0; color: #FFFFFF; font-family: 'Courier New', monospace; font-size: 2.2em; text-shadow: {text_glow}; letter-spacing: 1.5px;">
            {icon} {title}
        </h1>
    </div>
    """, unsafe_allow_html=True)

def get_protagonist_name():
    save_data = st.session_state.get("original_save_data", "")
    match = re.search(r'Nombre:\s*([^\n|]+)', save_data, re.IGNORECASE)
    if match:
        return match.group(1).strip().upper()
    
    lore = st.session_state.get("lore_text", "")
    match_lore = re.search(r'Nombre:\s*([^\n|]+)', lore, re.IGNORECASE)
    if match_lore:
        return match_lore.group(1).strip().upper()
        
    return "PROTAGONISTA"

render_themed_header()

# --- RENDERIZADORES UI / UX AVANZADOS ---
def format_vn_text(text, acento):
    if not acento:
        acento = "#00ff9d"
    
    def replace_dialogue(match):
        name = match.group(1).strip()
        dialogue = match.group(2).strip()
        return f'''<div style="background: rgba(0,0,0,0.5); padding: 12px 18px; margin: 12px 0; border-radius: 0px 8px 8px 0px; box-shadow: 0 4px 6px rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.05); border-left: 4px solid {acento};">
        <span style="color: {acento}; font-weight: 800; font-size: 1.15em; letter-spacing: 1px; text-transform: uppercase; text-shadow: 1px 1px 2px rgba(0,0,0,0.8);">{name}</span><br>
        <span style="font-size: 1.05em; color: #E8E8E8; line-height: 1.5;">{dialogue}</span>
        </div>'''
    
    text_processed = re.sub(r'\*\*([^\*]+)\*\*\s*[:\-]\s*([^\n]+)', replace_dialogue, text)

    def replace_goal(match):
        goal_text = match.group(1).strip()
        return f'''<div style="background: linear-gradient(135deg, rgba(20,20,35,0.7) 0%, rgba(10,10,18,0.85) 100%); padding: 14px 20px; margin: 18px 0 10px 0; border-radius: 8px; border: 1px dashed {acento}; box-shadow: inset 0 0 10px rgba(0,0,0,0.5); backdrop-filter: blur(5px);">
        <span style="color: {acento}; font-size: 0.85em; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase;">📌 OBJETIVO DE ESCENA</span><br>
        <span style="font-size: 1.05em; color: #DCDCDC; font-style: italic; line-height: 1.4;">{goal_text}</span>
        </div>'''

    text_processed = re.sub(r'(¿[^?\n]+\?)', replace_goal, text_processed)
    return text_processed

def render_player_action_box(text, acento):
    if not acento:
        acento = "#00ff9d"
    p_name = get_protagonist_name()
    return f'''<div style="background: linear-gradient(135deg, rgba(0,0,0,0.7) 0%, rgba(20,20,30,0.8) 100%); padding: 14px 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.6); border: 1px solid {acento}; border-left: 6px solid {acento};">
    <span style="color: {acento}; font-weight: 900; font-size: 0.95em; letter-spacing: 1.5px; text-transform: uppercase;">▶ {p_name} (ACCIÓN)</span><br>
    <span style="font-size: 1.08em; color: #FFFFFF; font-weight: 500; line-height: 1.5;">{text}</span>
    </div>'''

def render_ui_panel(raw_text, acento):
    if not raw_text:
        return
    lines = raw_text.strip().split('\n')
    if re.match(r'^\d\.\s', lines[0]):
        lines = lines[1:]
    
    html = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ":" in line and not line.startswith("<"):
            k, v = line.split(":", 1)
            html += f"""
            <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); border-left: 3px solid {acento}; padding: 10px; margin-bottom: 8px; border-radius: 4px;">
                <strong style="color: {acento};">{k.strip()}:</strong> <span style="color: #ddd; font-size: 0.95em;">{v.strip()}</span>
            </div>
            """
        else:
            html += f"""
            <div style="background: rgba(255,255,255,0.02); padding: 8px; margin-bottom: 6px; border-radius: 4px; color: #bbb; font-size: 0.9em; font-style: italic;">
                {line}
            </div>
            """
    st.markdown(html, unsafe_allow_html=True)

# 2. INTERFAZ LATERAL (CON LOS MODELOS EXACTOS DE GOOGLE AI STUDIO)
with st.sidebar:
    st.subheader("⚙️ Motores de IA")
    
    text_model_options = {
        "Gemini 3.1 Flash Lite (gemini-3.1-flash-lite-preview)": "gemini-3.1-flash-lite-preview",
        "Gemini 2.5 Flash (gemini-2.5-flash)": "gemini-2.5-flash",
        "Gemini 2.5 Flash Lite (gemini-2.5-flash-lite)": "gemini-2.5-flash-lite",
        "Gemini 2.5 Pro (gemini-2.5-pro)": "gemini-2.5-pro"
    }
    selected_model = text_model_options[st.selectbox("Motor Narrativo:", list(text_model_options.keys()))]

    img_model_options = {
        "Nano Banana 2 Lite - Sin candado Paid (gemini-3.1-flash-lite-image)": "gemini-3.1-flash-lite-image",
        "Nano Banana 2.1 - Requiere Paid (gemini-nano-banana-2.1)": "gemini-nano-banana-2.1",
        "Nano Banana 2 - Requiere Paid (gemini-3.1-flash-image)": "gemini-3.1-flash-image",
        "Nano Banana Pro - Requiere Paid (gemini-3-pro-image)": "gemini-3-pro-image",
        "Pollinations 2D Anime (Motor Externo)": "POLLINATIONS"
    }
    selected_img_model = img_model_options[st.selectbox("Motor Gráfico (/scene):", list(img_model_options.keys()))]
    allow_fallback = st.checkbox("Usar respaldo 2D si mi API Key da error 429", value=False)

    st.markdown("---")
    st.subheader("🌌 Estudio de Creación")
    
    with st.expander("📁 Universos Locales", expanded=False):
        tab_u_save, tab_u_load = st.tabs(["Guardar", "Cargar"])
        with tab_u_save:
            existing_unis = [os.path.basename(f).replace('.txt', '') for f in glob.glob("universes/*.txt")]
            u_save_sel = st.selectbox("Selecciona para sobrescribir o crea uno nuevo:", ["-- Crear Nuevo --"] + existing_unis, key="u_save_sel")
            lore_name = st.text_input("Nombre Archivo Universo:", value="UNIVERSE_custom", key="u_save_name") if u_save_sel == "-- Crear Nuevo --" else u_save_sel

            if st.button("💻 Guardar/Sobrescribir Universo", use_container_width=True, key="btn_save_uni"):
                if lore_name:
                    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', lore_name.strip())
                    file_path = f"universes/{clean_name}.txt"
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(st.session_state.get("lore_text", ""))
                    st.success(f"Universo guardado en: {file_path} ✅")
            
            if lore_name:
                st.download_button("⬇️ Descargar Universo (Móvil)", data=st.session_state.get("lore_text", ""), file_name=f"{lore_name}.txt", use_container_width=True)
            
        with tab_u_load:
            u_files = glob.glob("universes/*.txt")
            if u_files:
                sel_u = st.selectbox("Locales:", ["-- Seleccionar --"] + [os.path.basename(f) for f in u_files], key="sel_u")
                if sel_u != "-- Seleccionar --" and st.button("Cargar Local", use_container_width=True, key="btn_load_loc_uni"):
                    with open(f"universes/{sel_u}", "r", encoding="utf-8") as f:
                        st.session_state.lore_text = f.read()
                    st.rerun()
            up_u = st.file_uploader("📱 Subir Universo (Móvil)", type=["txt"], key="up_u")
            if up_u and st.button("Cargar Subido", use_container_width=True, key="btn_load_up_uni"):
                st.session_state.lore_text = up_u.getvalue().decode("utf-8")
                st.rerun()

    world_lore = st.text_area("📖 Biblia del Mundo y Estética:", key="lore_text", height=180)
    uploaded_refs = st.file_uploader("🎨 Imágenes de Referencia (Opcional):", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)

    st.markdown("---")
    st.subheader("💾 Gestor de Partidas")
    
    with st.expander("📁 Archivos de Partida", expanded=False):
        tab_p_save, tab_p_load = st.tabs(["Guardar", "Cargar"])
        with tab_p_save:
            existing_saves = [os.path.basename(f).replace('.txt', '') for f in glob.glob("saves/*.txt")]
            p_save_sel = st.selectbox("Selecciona para sobrescribir o crea una nueva:", ["-- Crear Nueva --"] + existing_saves, key="p_save_sel")
            save_campaign = st.text_input("Nombre Archivo Partida:", value="RPG_save", key="p_save_name") if p_save_sel == "-- Crear Nueva --" else p_save_sel

            if st.button("💻 Guardar/Sobrescribir Partida", use_container_width=True, key="btn_save_game"):
                if st.session_state.get("narrative_history"):
                    last_ia = [m["text"] for m in st.session_state.narrative_history if m["role"] == "ia"][-1]
                    original_save_data = st.session_state.get("original_save_data", "")
                    new_save = update_save_file(original_save_data, last_ia)
                    
                    if save_campaign:
                        clean_save_name = re.sub(r'[^a-zA-Z0-9_-]', '_', save_campaign.strip())
                        save_path = f"saves/{clean_save_name}.txt"
                        st.session_state.active_save_file = save_path
                        with open(save_path, "w", encoding="utf-8") as f:
                            f.write(new_save)
                        st.success(f"Partida guardada en: {save_path} ✅")
                        st.session_state.original_save_data = new_save
                else:
                    st.error("No hay partida activa para guardar.")
                    
            if st.session_state.get("narrative_history") and save_campaign:
                last_ia = [m["text"] for m in st.session_state.narrative_history if m["role"] == "ia"][-1]
                dl_structure = update_save_file(st.session_state.get("original_save_data", ""), last_ia)
                st.download_button("⬇️ Descargar Partida (Móvil)", data=dl_structure, file_name=f"{save_campaign}.txt", use_container_width=True)

        with tab_p_load:
            p_files = glob.glob("saves/*.txt")
            if p_files:
                sel_p = st.selectbox("Locales:", ["-- Seleccionar --"] + [os.path.basename(f) for f in p_files], key="sel_p")
                if sel_p != "-- Seleccionar --" and st.button("Cargar Local", use_container_width=True, key="btn_load_loc_game"):
                    file_path = f"saves/{sel_p}"
                    with open(file_path, "r", encoding="utf-8") as f:
                        raw_content = f.read()
                        st.session_state.original_save_data = raw_content
                        match_narrative = re.search(r'(<TEMA>.*?<OPCIONES>.*?</OPCIONES>)', raw_content, re.DOTALL)
                        if not match_narrative:
                            match_narrative = re.search(r'(<NARRATIVA>.*?<OPCIONES>.*?</OPCIONES>)', raw_content, re.DOTALL)
                        st.session_state.current_save = match_narrative.group(1) if match_narrative else raw_content
                    
                    st.session_state.active_save_file = file_path
                    st.session_state.game_started = False
                    st.session_state.api_turn_count = 0
                    st.session_state.needs_context_injection = False
                    st.rerun()
            
            up_p = st.file_uploader("📱 Subir Partida", type=["txt"], key="up_p")
            if up_p and st.button("Cargar Subido", use_container_width=True, key="btn_load_up_game"):
                raw_content = up_p.getvalue().decode("utf-8")
                st.session_state.original_save_data = raw_content
                match_narrative = re.search(r'(<TEMA>.*?<OPCIONES>.*?</OPCIONES>)', raw_content, re.DOTALL)
                if not match_narrative:
                    match_narrative = re.search(r'(<NARRATIVA>.*?<OPCIONES>.*?</OPCIONES>)', raw_content, re.DOTALL)
                st.session_state.current_save = match_narrative.group(1) if match_narrative else raw_content
                
                clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', up_p.name.replace('.txt', ''))
                st.session_state.active_save_file = f"saves/{clean_name}.txt"
                with open(st.session_state.active_save_file, "w", encoding="utf-8") as f:
                    f.write(raw_content)

                st.session_state.game_started = False
                st.session_state.api_turn_count = 0
                st.session_state.needs_context_injection = False
                st.rerun()

    st.markdown("---")
    if st.button("▶️ INICIAR / REINICIAR MOTOR", type="primary", use_container_width=True):
        st.session_state.game_started = True
        st.session_state.narrative_history = []
        st.session_state.api_turn_count = 0
        st.session_state.needs_context_injection = False
        st.session_state.last_img_error = None
        st.rerun()

# 3. REGLAS BASE DEL SISTEMA
engine_rules = """ROL Y MECÁNICAS PRINCIPALES
Eres el Game Director de un motor de ficción interactiva adaptable a cualquier género y universo definido en la Biblia del Mundo. NUNCA narres por el jugador ni decidas sus acciones.
ESTRICTO: Toda la narrativa debe escribirse obligatoriamente en SEGUNDA PERSONA del singular ("Tú haces", "Tú observas").

COMANDOS DE SISTEMA ADMITIDOS:
Si el usuario envía comandos especiales como /AdultContentOn, /MemoryContinuity, /retcon, /Fix, o /save, interprétalos e intégralos orgánicamente.

REGLAS DE FORMATO XML (OBLIGATORIO):
Debes seguir estrictamente este orden y cerrar siempre cada etiqueta. Nunca mezcles los textos fuera de las etiquetas XML.

<TEMA>
[Color Fondo Hex] | [Color Texto Hex] | [Color Acento Hex] | [Fuente: serif / sans-serif / monospace]
</TEMA>
<AMBIENTE>
[Selecciona uno: Exploración / Tensión / Combate / Misterio / Romance / Cyberpunk / Melancolía / Suspenso / Acción Épica / Silencio]
</AMBIENTE>
<NARRATIVA>
Mínimo 4 a 6 párrafos literarios en SEGUNDA PERSONA adaptados estrictamente al universo activo. Usa emojis temáticos sutiles. Enfatiza OBLIGATORIAMENTE los diálogos de los NPCs en líneas nuevas con el formato estricto: **NOMBRE**: "Texto del diálogo". Termina la narrativa obligatoriamente con una pregunta o instrucción clara que comience con un signo de interrogación (¿) de máximo 2 oraciones guiando al jugador sobre qué hacer. Jamás menciones suerte o azar.
</NARRATIVA>
<IMAGEN>
Escribe un prompt en INGLÉS (máximo 85 palabras) para una ilustración 2D Anime que represente EXACTAMENTE la acción y los personajes de los párrafos anteriores.
Estructura obligatoria: "2D anime key visual illustration, cel-shaded 2D anime art, clean anime lineart, vibrant colors, ufotable and Honkai Star Rail 2D style, [Describe físicamente a los personajes presentes según el Lore: cabello, ropa, armas/poderes], [Describe la acción exacta, poses e interacción que están realizando en esta escena], [Describe el fondo]. Flat 2D anime shading, no 3D render, no photorealism."
</IMAGEN>
<HUD>
[Salud/Resistencia]: [Act]/[Max] | [Maná/Energía]: [Act]/[Max] | [NombreNPC - Emoción]: [Valor]% | Estado: [Texto] | Entorno: [Texto]
</HUD>
<OPCIONES>
Presenta 4 opciones tácticas (ej: [NombreCorto] - Descripción).
</OPCIONES>
"""

# 4. FUNCIONES DE PROCESAMIENTO Y GENERACIÓN VISUAL NATIVA
def parse_ai_response(text):
    narrativa = re.search(r'<NARRATIVA>(.*?)</NARRATIVA>', text, re.DOTALL)
    hud = re.search(r'<HUD>(.*?)</HUD>', text, re.DOTALL)
    opciones = re.search(r'<OPCIONES>(.*?)</OPCIONES>', text, re.DOTALL)
    imagen = re.search(r'<IMAGEN>(.*?)</IMAGEN>', text, re.DOTALL)
    tema = re.search(r'<TEMA>(.*?)</TEMA>', text, re.DOTALL)
    ambiente = re.search(r'<AMBIENTE>(.*?)</AMBIENTE>', text, re.DOTALL | re.IGNORECASE)
    
    raw_narrativa = ""
    if narrativa:
        raw_narrativa = narrativa.group(1).strip()
    else:
        cleaned = re.sub(r'<TEMA>.*?</TEMA>', '', text, flags=re.DOTALL)
        cleaned = re.sub(r'<AMBIENTE>.*?</AMBIENTE>', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'<IMAGEN>.*?</IMAGEN>', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'<HUD>.*?</HUD>', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'<OPCIONES>.*?</OPCIONES>', '', cleaned, flags=re.DOTALL)
        raw_narrativa = cleaned.strip()

    nombres_botones = ["Opción 1", "Opción 2", "Opción 3", "Opción 4"]
    if opciones:
        encontrados = re.findall(r'\[([^0-9\]]+?)\]', opciones.group(1))
        if not encontrados:
            encontrados = re.findall(r'\[(.*?)\]', opciones.group(1))
        for i in range(min(4, len(encontrados))):
            limpio = encontrados[i].strip()
            if limpio and not limpio.isdigit():
                nombres_botones[i] = limpio
                
    hud_data = {"stats_bar": [], "stat_pct": [], "affinities": [], "estado": "Desconocido", "entorno": "Desconocido", "raw": hud.group(1).strip() if hud else ""}
    
    if hud_data["raw"]:
        barras = re.findall(r'\[?([a-zA-ZáéíóúÁÉÍÓÚ\s]+)\]?:\s*\[?(\d+)\]?/\[?(\d+)\]?', hud_data["raw"])
        for b in barras:
            hud_data["stats_bar"].append({"name": b[0].strip(), "act": int(b[1]), "max": int(b[2])})
        
        pct_matches = re.findall(r'\[?([a-zA-ZáéíóúÁÉÍÓÚ\-\s]+)\]?:\s*\[?(\d+)\]?%', hud_data["raw"])
        for p in pct_matches:
            nombre = p[0].strip()
            valor = int(p[1])
            if "-" in nombre: 
                hud_data["affinities"].append({"name": nombre, "val": valor})
            else: 
                hud_data["stat_pct"].append({"name": nombre, "val": valor})
            
        est_txt = re.search(r'Estado:\s*([^|]+)', hud_data["raw"], re.IGNORECASE)
        ent_txt = re.search(r'Entorno:\s*([^|]+)', hud_data["raw"], re.IGNORECASE)
        if est_txt: hud_data["estado"] = est_txt.group(1).strip()
        if ent_txt: hud_data["entorno"] = ent_txt.group(1).strip()

    estilo_css = None
    if tema:
        partes = [p.strip() for p in tema.group(1).split('|')]
        if len(partes) >= 4:
            estilo_css = {"bg": partes[0], "txt": partes[1], "acento": partes[2], "fuente": partes[3]}
            
    return {
        "narrativa": raw_narrativa,
        "hud": hud_data,
        "opciones_raw": opciones.group(1).strip() if opciones else "",
        "botones": nombres_botones,
        "imagen_prompt": imagen.group(1).strip() if imagen else None,
        "tema": estilo_css,
        "ambiente": ambiente.group(1).strip() if ambiente else "Silencio"
    }

def build_anime_scene_prompt(prompt_text, narrative_text, lore_context, text_model):
    # Si el turno ya incluye un prompt detallado en <IMAGEN>, lo usamos y reforzamos sin gastar otra llamada de API
    if prompt_text and len(prompt_text.strip()) > 35:
        clean_p = prompt_text.strip().replace('\n', ' ')
        if "2d anime" not in clean_p.lower():
            clean_p = f"2D anime key visual illustration, cel-shaded 2D anime art, clean anime lineart, vibrant colors, {clean_p}, flat 2D anime shading, no 3D render, no photorealism"
        return clean_p

    # Solo si <IMAGEN> vino vacío (ej. al cargar un save antiguo), sintetizamos el prompt desde la narrativa
    director_prompt = f"""Write a single English image generation prompt (max 85 words) for a 2D Anime illustration of this exact scene.
Start with: "2D anime key visual illustration, cel-shaded 2D anime art, clean anime lineart, vibrant colors,"
Describe the characters (hair, attire, weapons/powers from Lore) performing the exact action in the scene.
End with: "flat 2D anime shading, no 3D render, no photorealism."

[LORE]: {lore_context[:2500]}
[SCENE]: {narrative_text}"""
    try:
        resp = client.models.generate_content(model=text_model, contents=director_prompt)
        if resp and resp.text:
            return resp.text.strip().replace('\n', ' ')
    except Exception:
        pass
    return f"2D anime key visual illustration, cel-shaded 2D anime art, clean anime lineart, vibrant colors, dynamic anime characters in action, {narrative_text[:220]}, flat 2D anime shading, no 3D render, no photorealism"

def generate_image_for_turn(prompt_text, model_choice, narrative_text="", lore_context="", text_model="gemini-2.5-flash", refs=None, use_fallback=False):
    st.session_state.last_img_error = None
    scene_anime_prompt = build_anime_scene_prompt(prompt_text, narrative_text, lore_context, text_model)

    # 1. EJECUCIÓN DIRECTA DEL MODELO NANO BANANA SELECCIONADO
    if model_choice != "POLLINATIONS":
        last_error = ""
        contents_payload = [
            f"Generate a 16:9 widescreen 2D anime illustration of this exact scene: {scene_anime_prompt}"
        ]
        if refs:
            for r in refs[:2]:
                try:
                    r.seek(0)
                    contents_payload.append(Image.open(r))
                except Exception:
                    pass

        # Intento A: generate_content nativo de la familia Nano Banana / Gemini Image
        for mod_cfg in [["IMAGE", "TEXT"], ["IMAGE"]]:
            try:
                resp = client.models.generate_content(
                    model=model_choice,
                    contents=contents_payload,
                    config=types.GenerateContentConfig(
                        response_modalities=mod_cfg
                    )
                )
                if resp and resp.candidates:
                    for part in resp.candidates[0].content.parts:
                        if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                            return {
                                "type": "bytes",
                                "data": part.inline_data.data,
                                "engine": model_choice,
                                "prompt": scene_anime_prompt
                            }
            except Exception as e:
                last_error = str(e)
                # Si es 429 (cuota 0 o límite alcanzado), no repetir llamadas innecesarias al mismo modelo
                if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
                    break

        # Intento B: Si el error no fue de cuota (429), probar vía endpoint generate_images
        if "429" not in last_error and "RESOURCE_EXHAUSTED" not in last_error:
            try:
                res_img = client.models.generate_images(
                    model=model_choice,
                    prompt=scene_anime_prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type="image/jpeg",
                        aspect_ratio="16:9"
                    )
                )
                if res_img and getattr(res_img, "generated_images", None):
                    for generated_image in res_img.generated_images:
                        return {
                            "type": "bytes",
                            "data": generated_image.image.image_bytes,
                            "engine": model_choice,
                            "prompt": scene_anime_prompt
                        }
            except Exception as e:
                last_error = str(e)

        # Mostrar el diagnóstico exacto del modelo elegido
        st.session_state.last_img_error = (
            f"⚠️ El modelo '{model_choice}' devolvió: {last_error[:220]}"
        )
        if not use_fallback:
            return None

    # 2. MOTOR EXTERNO POLLINATIONS (O RESPALDO SI EL USUARIO ACTIVÓ LA CASILLA)
    encoded = urllib.parse.quote(scene_anime_prompt)
    seed = random.randint(1000, 999999)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&nologo=true&seed={seed}&enhance=false"
    return {
        "type": "url",
        "data": url,
        "engine": "Pollinations 2D Anime",
        "prompt": scene_anime_prompt
    }

# 5. BUCLE PRINCIPAL DEL JUEGO
if not st.session_state.get("game_started", False):
    st.info("Configura tu universo, sube tus referencias visuales y presiona **▶️ INICIAR / REINICIAR MOTOR** en la barra lateral para comenzar.")
    st.stop()

if "narrative_history" not in st.session_state or len(st.session_state.narrative_history) == 0:
    with st.spinner("Inicializando Game Director y cargando entorno multimodal..."):
        try:
            sys_instruct = f"{engine_rules}\n\n[CONTEXTO DEL UNIVERSO]\n{world_lore}"
            st.session_state.chat_session = client.chats.create(
                model=selected_model,
                config=types.GenerateContentConfig(system_instruction=sys_instruct)
            )
            
            st.session_state.api_turn_count = 0
            st.session_state.needs_context_injection = False
            
            initial_content = []
            if st.session_state.get("current_save", "").strip():
                original_save_data = st.session_state.get("original_save_data", st.session_state.current_save)
                initial_text = f"[SISTEMA - CARGA DE ESTADO]:\n{original_save_data}\n\nRetoma la historia estrictamente desde la Situación Actual preservando todo el inventario, relaciones con NPCs y estadísticas."
                initial_content.append(initial_text)
                if uploaded_refs:
                    for ref in uploaded_refs:
                        ref.seek(0)
                        img = Image.open(ref)
                        initial_content.append(f"[Referencia Visual del Archivo: {ref.name}]")
                        initial_content.append(img)
                
                st.session_state.chat_session.send_message(initial_content)
                st.session_state.narrative_history = [{"role": "ia", "text": st.session_state.current_save, "img_data": None, "img_type": None}]
            else:
                initial_text = "Genera la escena inicial inmersiva evaluando el Lore y las referencias visuales cargadas."
                initial_content.append(initial_text)
                if uploaded_refs:
                    for ref in uploaded_refs:
                        ref.seek(0)
                        img = Image.open(ref)
                        initial_content.append(f"[Referencia Visual del Archivo: {ref.name}]")
                        initial_content.append(img)
                    
                initial_response = st.session_state.chat_session.send_message(initial_content)
                st.session_state.narrative_history = [{"role": "ia", "text": initial_response.text, "img_data": None, "img_type": None}]
        except Exception as e:
            st.error(f"Error crítico al iniciar la partida: {e}")
            st.stop()

# EXTRACCIÓN DE DATOS ACTUALES
ultimo_mensaje_ia = [m["text"] for m in st.session_state.narrative_history if m["role"] == "ia"][-1]
datos_actuales = parse_ai_response(ultimo_mensaje_ia)

tema_acento_global = datos_actuales.get("tema", {}).get("acento", "#00ff9d") if datos_actuales.get("tema") else "#00ff9d"

if datos_actuales.get("tema"):
    t = datos_actuales["tema"]
    st.markdown(f"""
    <style>
        .stApp {{
            background-color: {t['bg']} !important;
            color: {t['txt']} !important;
            font-family: {t['fuente']}, sans-serif !important;
        }}
        [data-testid="stContainer"] {{
            border-color: {t['acento']} !important;
            background-color: rgba(0,0,0,0.3) !important;
            border-radius: 10px;
        }}
        .stButton>button {{
            border-color: {t['acento']} !important;
            color: {t['acento']} !important;
            background-color: transparent !important;
            transition: all 0.3s ease;
        }}
        .stButton>button:hover {{
            background-color: {t['acento']} !important;
            color: {t['bg']} !important;
        }}
        .stProgress > div > div > div > div {{
            background-color: {t['acento']} !important;
        }}
    </style>
    """, unsafe_allow_html=True)

col_historia, col_hud = st.columns([3, 1], gap="medium")

with col_historia:
    st.subheader("📖 Narrativa y Escena")

    if st.session_state.get("last_img_error"):
        st.error(st.session_state.last_img_error)

    for msg in st.session_state.narrative_history:
        if msg["role"] == "ia":
            parsed_msg = parse_ai_response(msg["text"])
            msg_acento = parsed_msg.get("tema", {}).get("acento", "#00ff9d") if parsed_msg.get("tema") else "#00ff9d"
            
            narrativa_final = format_vn_text(parsed_msg["narrativa"], msg_acento)
            st.markdown(narrativa_final, unsafe_allow_html=True)
            
            if msg.get("img_data") is not None:
                engine_label = msg.get("img_engine", "2D Anime Engine")
                st.image(msg.get("img_data"), use_container_width=True, caption=f"📸 Scene Render ({engine_label})")
                if msg.get("img_prompt"):
                    with st.expander("🔍 Ver Prompt Visual 2D de la Escena", expanded=False):
                        st.caption(msg.get("img_prompt"))
            st.markdown("---")
        else:
            player_box = render_player_action_box(msg['text'], tema_acento_global)
            st.markdown(player_box, unsafe_allow_html=True)
            st.markdown("---")
    
    st.subheader("🎯 Elige tu Acción")
    c1, c2, c3, c4 = st.columns(4)
    accion_seleccionada = None
    
    if c1.button(f"1️⃣ {datos_actuales['botones'][0]}", use_container_width=True): accion_seleccionada = datos_actuales['botones'][0]
    if c2.button(f"2️⃣ {datos_actuales['botones'][1]}", use_container_width=True): accion_seleccionada = datos_actuales['botones'][1]
    if c3.button(f"3️⃣ {datos_actuales['botones'][2]}", use_container_width=True): accion_seleccionada = datos_actuales['botones'][2]
    if c4.button(f"4️⃣ {datos_actuales['botones'][3]}", use_container_width=True): accion_seleccionada = datos_actuales['botones'][3]

    st.markdown("**O escribe tu acción libre:**")
    col_input, col_btn = st.columns([4, 1])
    with col_input:
        accion_personalizada = st.text_input("Acción personalizada:", label_visibility="collapsed")
    with col_btn:
        if st.button("Ejecutar", use_container_width=True) and accion_personalizada:
            accion_seleccionada = accion_personalizada

    st.markdown("**🛠️ Comandos de Sistema:**")
    r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
    r2_c1, r2_c2, r2_c3 = st.columns(3)

    if r1_c1.button("🩸 /Adult", use_container_width=True, help="Alternar contenido adulto/explícito"): accion_seleccionada = "/AdultContentOn"
    if r1_c2.button("🧠 /Memory", use_container_width=True, help="Refrescar continuidad de memoria"): accion_seleccionada = "/MemoryContinuity"
    if r1_c3.button("⏪ /retcon", use_container_width=True, help="Modificar o reescribir un evento pasado"): accion_seleccionada = "/retcon"
    if r1_c4.button("🔧 /Fix", use_container_width=True, help="Corregir errores de formato o consistencia"): accion_seleccionada = "/Fix"
    
    if r2_c1.button("💾 /save", use_container_width=True, help="Generar estado de guardado"): accion_seleccionada = "/save"
    if r2_c2.button("🖼️ /scene", use_container_width=True, help="Ilustrar en 2D Anime la escena actual sin avanzar el turno"): accion_seleccionada = "/scene"
    if r2_c3.button("↩️ /undo", use_container_width=True, help="Deshacer última acción y volver atrás"): accion_seleccionada = "/undo"

    if accion_seleccionada:
        # 1. INTERCEPTAR /undo
        if accion_seleccionada.strip().lower() == "/undo":
            if len(st.session_state.narrative_history) >= 2:
                st.session_state.narrative_history.pop()
                st.session_state.narrative_history.pop()
                if st.session_state.api_turn_count > 0:
                    st.session_state.api_turn_count -= 1
                st.success("¡Acción deshecha con éxito! Regresaste al estado anterior.")
                st.rerun()
            else:
                st.warning("No hay suficientes turnos previos para deshacer.")
                st.stop()

        # 2. INTERCEPTAR /scene PARA ILUSTRAR LA ESCENA ACTUAL SIN AVANZAR LA HISTORIA
        if accion_seleccionada.strip().lower() == "/scene":
            with st.spinner(f"🎨 Generando ilustración 2D Anime con {selected_img_model}..."):
                lore_and_save = f"{world_lore}\n{st.session_state.get('original_save_data', '')}"
                res = generate_image_for_turn(
                    prompt_text=datos_actuales.get("imagen_prompt", ""),
                    model_choice=selected_img_model,
                    narrative_text=datos_actuales.get("narrativa", ""),
                    lore_context=lore_and_save,
                    text_model=selected_model,
                    refs=uploaded_refs,
                    use_fallback=allow_fallback
                )
                if res:
                    for idx in range(len(st.session_state.narrative_history) - 1, -1, -1):
                        if st.session_state.narrative_history[idx]["role"] == "ia":
                            st.session_state.narrative_history[idx]["img_data"] = res["data"]
                            st.session_state.narrative_history[idx]["img_type"] = res["type"]
                            st.session_state.narrative_history[idx]["img_engine"] = res.get("engine", selected_img_model)
                            st.session_state.narrative_history[idx]["img_prompt"] = res.get("prompt", "")
                            break
                    st.session_state.cg_gallery.append({
                        "data": res["data"],
                        "engine": res.get("engine", selected_img_model)
                    })
                st.rerun()

        # 3. FLUJO NORMAL DE TURNO NARRATIVO
        with st.spinner("Procesando turno..."):
            try:
                st.session_state.last_img_error = None
                mensaje_api = accion_seleccionada
                if st.session_state.get("needs_context_injection", False):
                    contexto_guardado = st.session_state.get("original_save_data", "")
                    mensaje_api = f"[SISTEMA: MEMORIA COMPRIMIDA. ESTADO ACTUAL DE LA PARTIDA]:\n{contexto_guardado}\n\nRetoma estrictamente desde este contexto manteniendo el formato XML. Siguiente acción del jugador/comando: {accion_seleccionada}"
                    st.session_state.needs_context_injection = False

                response = st.session_state.chat_session.send_message(mensaje_api)

                st.session_state.narrative_history.append({"role": "user", "text": accion_seleccionada})
                st.session_state.narrative_history.append({
                    "role": "ia", 
                    "text": response.text,
                    "img_data": None,
                    "img_type": None
                })
                
                st.session_state.api_turn_count = st.session_state.get("api_turn_count", 0) + 1
                
                if st.session_state.api_turn_count >= 3:
                    last_ia = response.text
                    original_save = st.session_state.get("original_save_data", "")
                    new_save = update_save_file(original_save, last_ia)
                    st.session_state.original_save_data = new_save
                    
                    save_target = st.session_state.get("active_save_file")
                    if save_target:
                        with open(save_target, "w", encoding="utf-8") as f:
                            f.write(new_save)
                    else:
                        os.makedirs("saves", exist_ok=True)
                        st.session_state.active_save_file = "saves/AutoSave_Backup.txt"
                        with open(st.session_state.active_save_file, "w", encoding="utf-8") as f:
                            f.write(new_save)

                    sys_instruct = f"{engine_rules}\n\n[CONTEXTO DEL UNIVERSO]\n{world_lore}"
                    st.session_state.chat_session = client.chats.create(
                        model=selected_model,
                        config=types.GenerateContentConfig(system_instruction=sys_instruct)
                    )
                    st.session_state.needs_context_injection = True
                    st.session_state.api_turn_count = 0

                st.rerun()
            except Exception as e:
                st.error(f"Error de comunicación con la IA: {e}. Intenta enviar la acción nuevamente.")

with col_hud:
    ambiente_actual = datos_actuales.get("ambiente", "Silencio")
    track_url = AUDIO_TRACKS.get(ambiente_actual, "")
    color_acento = datos_actuales.get('tema', {}).get('acento', '#00ff9d') if datos_actuales.get('tema') else '#00ff9d'
    
    if track_url:
        unique_id = f"audio_{int(time.time())}"
        audio_html = f"""
        <div style="padding: 10px; border-radius: 5px; background: rgba(0,0,0,0.4); border: 1px solid {color_acento}; margin-bottom: 15px;">
            <strong style="color: {color_acento};">🎧 Ambiente Activo: {ambiente_actual}</strong><br>
            <audio id="{unique_id}" controls autoplay loop style="width: 100%; height: 35px; margin-top: 5px; border-radius: 5px;">
                <source src="{track_url}?v={int(time.time())}" type="audio/mpeg">
                Tu navegador no soporta el elemento de audio.
            </audio>
        </div>
        """
        components.html(audio_html, height=85)

    with st.container(border=True):
        tab_hud, tab_inv, tab_npc, tab_gal = st.tabs(["⚙️ HUD", "🎒 Perfil/Inv", "👥 NPCs", "🖼️ Galería"])
        
        with tab_hud:
            st.subheader("Estado Inmediato")
            h_data = datos_actuales["hud"]
            
            if isinstance(h_data, dict):
                if h_data.get("stats_bar"):
                    for stat in h_data["stats_bar"]:
                        pct = min(stat["act"] / max(stat["max"], 1), 1.0)
                        st.caption(f"🔹 **{stat['name']}:** {stat['act']} / {stat['max']}")
                        st.progress(pct)
                
                if h_data.get("stat_pct"):
                    cols_pct = st.columns(len(h_data["stat_pct"]))
                    for idx, spct in enumerate(h_data["stat_pct"]):
                        with cols_pct[idx]:
                            st.metric(f"💠 {spct['name']}", f"{spct['val']}%")
                
                if h_data.get("affinities"):
                    st.divider()
                    st.markdown("**💖 Vínculos y Afinidades**")
                    for aff in h_data["affinities"]:
                        val = min(max(aff["val"], 0), 100)
                        st.caption(f"**{aff['name']}**")
                        st.progress(val / 100.0)
                        
                st.divider()
                st.markdown(f"**🛡️ Estado:** {h_data['estado']}")
                st.markdown(f"**📍 Entorno:** {h_data['entorno']}")
            else:
                st.markdown(datos_actuales["hud"]["raw"] if isinstance(h_data, dict) else h_data)
                
            st.markdown("---")
            with st.expander("Opciones Detalladas", expanded=False):
                opciones_limpias = re.sub(r'\[([^\]]+)\]', r'\n* **[\1]**', datos_actuales["opciones_raw"]).strip()
                st.markdown(opciones_limpias)
                
        with tab_inv:
            save_data = st.session_state.get("original_save_data", "")
            m_perfil = re.search(r'(1\. PERFIL.*?)(?=2\. INVENTARIO|3\. RESUMEN|4\. ESTADO|<TEMA>|$)', save_data, re.DOTALL | re.IGNORECASE)
            m_inv = re.search(r'(2\. INVENTARIO.*?)(?=3\. RESUMEN|4\. ESTADO|<TEMA>|$)', save_data, re.DOTALL | re.IGNORECASE)
            
            if m_perfil:
                render_ui_panel(m_perfil.group(1), color_acento)
            else:
                st.caption("No se encontró un perfil en el archivo de guardado.")
                
            st.divider()
            
            if m_inv:
                render_ui_panel(m_inv.group(1), color_acento)
            else:
                st.caption("No se encontró inventario en el archivo de guardado.")
                
        with tab_npc:
            save_data = st.session_state.get("original_save_data", "")
            m_npc = re.search(r'(4\. ESTADO DE LOS NPCs.*?)(?=5\. SITUACIÓN|<TEMA>|$)', save_data, re.DOTALL | re.IGNORECASE)
            
            if m_npc:
                render_ui_panel(m_npc.group(1), color_acento)
            else:
                st.caption("No se encontraron registros de NPCs en el archivo de guardado.")
                
        with tab_gal:
            st.subheader("Arte CG Desbloqueado")
            if st.session_state.cg_gallery:
                cols = st.columns(2)
                for i, item in enumerate(reversed(st.session_state.cg_gallery)):
                    with cols[i % 2]:
                        img_content = item["data"] if isinstance(item, dict) else item
                        eng_name = item.get("engine", "CG") if isinstance(item, dict) else "CG"
                        st.image(img_content, use_container_width=True, caption=f"Escena #{len(st.session_state.cg_gallery) - i} ({eng_name})")
            else:
                st.caption("Aún no has desbloqueado ninguna CG. ¡Presiona 🖼️ /scene durante un momento clave de la historia para generar arte!")