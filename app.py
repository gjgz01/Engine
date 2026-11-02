import os
import re
import glob
import urllib.parse
import time
import streamlit as st
from google import genai
from google.genai import types
from PIL import Image

# 1. SETUP DE CARPETAS Y CONFIGURACIÓN BÁSICA
os.makedirs("saves", exist_ok=True)
os.makedirs("universes", exist_ok=True)

st.set_page_config(page_title="Universal RPG Engine", layout="wide")
st.title("⚡ Universal RPG Engine - Game Director AI")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except FileNotFoundError:
    api_key = os.environ.get("GEMINI_API_KEY")

# Inicialización de estados clave
if "lore_text" not in st.session_state:
    st.session_state.lore_text = """[UNIVERSO Y TÉTRADA VISUAL]
Mundo: Relic Academy (Aster City). Tono: Cyberpunk oscuro.
Tema Visual Sugerido: #0d1117 | #c9d1d9 | #00ff9d | monospace

[PROTAGONISTA]
Nombre: Wraith. Clase: Infiltrador. Arma: Guanteletes TALON.

[SITUACIÓN INICIAL]
Comienza en el Sector Cero, acechado por corporativos."""

if "active_save_file" not in st.session_state:
    st.session_state.active_save_file = None

if "cg_gallery" not in st.session_state:
    st.session_state.cg_gallery = []

# --- DICCIONARIO DE AUDIO ADAPTATIVO ---
AUDIO_TRACKS = {
    "Combate": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3",
    "Tensión": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-16.mp3",
    "Exploración": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3",
    "Misterio": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3",
    "Romance": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
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

# --- RENDERIZADORES UI / UX AVANZADOS ---
def format_vn_text(text, acento):
    if not acento: acento = "#00ff9d"
    def replace_dialogue(match):
        name = match.group(1).strip()
        dialogue = match.group(2).strip()
        return f'''<div style="background: rgba(0,0,0,0.5); padding: 12px 18px; margin: 12px 0; border-radius: 0px 8px 8px 0px; box-shadow: 0 4px 6px rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.05); border-left: 4px solid {acento};">
        <span style="color: {acento}; font-weight: 800; font-size: 1.15em; letter-spacing: 1px; text-transform: uppercase; text-shadow: 1px 1px 2px rgba(0,0,0,0.8);">{name}</span><br>
        <span style="font-size: 1.05em; color: #E8E8E8; line-height: 1.5;">{dialogue}</span>
        </div>'''
    return re.sub(r'\*\*([^\*]+)\*\*\s*[:\-]\s*([^\n]+)', replace_dialogue, text)

def render_ui_panel(raw_text, acento):
    if not raw_text: return
    lines = raw_text.strip().split('\n')
    if re.match(r'^\d\.\s', lines[0]):
        lines = lines[1:]
    
    html = ""
    for line in lines:
        line = line.strip()
        if not line: continue
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

# 2. INTERFAZ LATERAL (CONFIGURACIÓN)
with st.sidebar:
    st.subheader("🔑 Configuración")
    if not api_key:
        api_key_input = st.text_input("Ingresa tu API Key:", type="password")
        if api_key_input:
            api_key = api_key_input
    else:
        st.success("API Key cargada en automático ✅")

    st.markdown("---")
    st.subheader("⚙️ Motores de IA")
    
    text_model_options = {
        "Gemini 3.8 Flash (gemini-3.8-flash)": "gemini-3.8-flash",
        "Gemini 3.5 Flash Lite (gemini-3.5-flash-lite)": "gemini-3.5-flash-lite",
        "Gemini 4 Argon (gemini-4-argon)": "gemini-4-argon",
        "Gemini 3.1 Pro Preview (gemini-3.1-pro-preview)": "gemini-3.1-pro-preview"
    }
    selected_model = text_model_options[st.selectbox("Motor Narrativo:", list(text_model_options.keys()))]

    img_model_options = {
        "Pollinations AI (Cinemático / Rápido / Universal)": "pollinations",
        "Gemini Flash Image (Modo Adaptativo)": "pollinations_gemini",
        "Gemini Pro Image (Modo HD)": "pollinations_hd"
    }
    selected_img_model = img_model_options[st.selectbox("Motor Gráfico (/scene):", list(img_model_options.keys()))]

    st.markdown("---")
    st.subheader("🌌 Estudio de Creación")
    
    with st.expander("📁 Universos Locales", expanded=False):
        tab_u_save, tab_u_load = st.tabs(["Guardar", "Cargar"])
        with tab_u_save:
            existing_unis = [os.path.basename(f).replace('.txt', '') for f in glob.glob("universes/*.txt")]
            u_save_sel = st.selectbox("Selecciona para sobrescribir o crea uno nuevo:", ["-- Crear Nuevo --"] + existing_unis, key="u_save_sel")
            lore_name = st.text_input("Nombre Archivo Universo:", value="RELIC_universo", key="u_save_name") if u_save_sel == "-- Crear Nuevo --" else u_save_sel

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
            save_campaign = st.text_input("Nombre Archivo Partida:", value="WRAITH_save", key="p_save_name") if p_save_sel == "-- Crear Nueva --" else p_save_sel

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
        st.rerun()

# 3. REGLAS BASE DEL SISTEMA
engine_rules = """ROL Y MECÁNICAS PRINCIPALES
Eres el Game Director de una Novela Visual Anime Interactiva. NUNCA narres por el jugador ni decidas sus acciones. 
ESTRICTO: Toda la narrativa debe escribirse obligatoriamente en SEGUNDA PERSONA del singular ("Tú haces", "Tú observas").

REGLAS DE AFINIDAD (VÍNCULOS):
Debes evaluar constantemente la relación del protagonista con los NPCs basándote en sus decisiones. En la etiqueta <HUD>, DEBES incluir al menos una métrica de afinidad para los NPCs relevantes en la escena usando el formato exacto: [NombreNPC - Emoción]: [Valor]%. (Ejemplo: [Airi - Confianza]: 65% o [Vance - Sospecha]: 80%).

ESTRUCTURA OBLIGATORIA DE RESPUESTA:
<TEMA>
[Color Fondo Hex] | [Color Texto Hex] | [Color Acento Hex] | [Fuente: serif / sans-serif / monospace]
</TEMA>
<AMBIENTE>
[Selecciona uno: Exploración / Tensión / Combate / Misterio / Romance / Silencio]
</AMBIENTE>
<NARRATIVA>
Mínimo 4 a 6 párrafos literarios. Usa emojis temáticos sutiles. Enfatiza OBLIGATORIAMENTE los diálogos en líneas nuevas con el formato estricto: **NOMBRE**: "Texto del diálogo". Haz que las consecuencias del mundo parezcan orgánicas, jamás menciones suerte o azar.
</NARRATIVA>
<IMAGEN>
Prompt visual en inglés, detallado, estilo anime cinemático describiendo la escena actual.
</IMAGEN>
<HUD>
[Salud/Resistencia]: [Act]/[Max] | [Maná/Energía]: [Act]/[Max] | [NombreNPC - Emoción]: [Valor]% | Estado: [Texto] | Entorno: [Texto]
</HUD>
<OPCIONES>
Presenta 4 opciones tácticas (ej: [NombreCorto] - Descripción).
</OPCIONES>
"""

if not api_key:
    st.warning("⚠️ Ingresa tu API Key para empezar.")
    st.stop()

@st.cache_resource
def get_gemini_client(key):
    return genai.Client(api_key=key)

client = get_gemini_client(api_key)

# 4. FUNCIONES DE PROCESAMIENTO OPTIMIZADAS
def parse_ai_response(text):
    narrativa = re.search(r'<NARRATIVA>(.*?)</NARRATIVA>', text, re.DOTALL)
    hud = re.search(r'<HUD>(.*?)</HUD>', text, re.DOTALL)
    opciones = re.search(r'<OPCIONES>(.*?)</OPCIONES>', text, re.DOTALL)
    imagen = re.search(r'<IMAGEN>(.*?)</IMAGEN>', text, re.DOTALL)
    tema = re.search(r'<TEMA>(.*?)</TEMA>', text, re.DOTALL)
    ambiente = re.search(r'<AMBIENTE>(.*?)</AMBIENTE>', text, re.DOTALL | re.IGNORECASE)
    
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
        "narrativa": narrativa.group(1).strip() if narrativa else text,
        "hud": hud_data,
        "opciones_raw": opciones.group(1).strip() if opciones else "",
        "botones": nombres_botones,
        "imagen_prompt": imagen.group(1).strip() if imagen else None,
        "tema": estilo_css,
        "ambiente": ambiente.group(1).strip() if ambiente else "Silencio"
    }

def generate_image_for_turn(prompt_text, model_choice):
    encoded = urllib.parse.quote(prompt_text)
    return {"type": "url", "data": f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=512&nologo=true"}

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
                        img = Image.open(ref)
                        initial_content.append(f"[Referencia Visual del Archivo: {ref.name}]")
                        initial_content.append(img)
                
                st.session_state.chat_session.send_message(initial_content)
                st.session_state.narrative_history = [{"role": "ia", "text": st.session_state.current_save, "img_data": None, "img_type": None}]
            else:
                initial_text = "Genera la escena inicial inmersiva evaluando el Lore y las referencias visuales."
                initial_content.append(initial_text)
                if uploaded_refs:
                    for ref in uploaded_refs:
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
    for msg in st.session_state.narrative_history:
        if msg["role"] == "ia":
            parsed_msg = parse_ai_response(msg["text"])
            tema_acento = parsed_msg.get("tema", {}).get("acento", "#00ff9d") if parsed_msg.get("tema") else "#00ff9d"
            
            narrativa_final = format_vn_text(parsed_msg["narrativa"], tema_acento)
            st.markdown(narrativa_final, unsafe_allow_html=True)
            
            if msg.get("img_type") == "url":
                st.image(msg.get("img_data"), use_container_width=True, caption="📸 Scene Render")
            elif msg.get("img_type") == "bytes":
                st.image(msg.get("img_data"), use_container_width=True, caption="📸 Scene Render")
            st.markdown("---")
        else:
            st.markdown(f"**Tú:** {msg['text']}")
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
    cmd1, cmd2, cmd3, cmd4, cmd5, cmd6 = st.columns(6)
    if cmd1.button("🩸 /Adult", use_container_width=True): accion_seleccionada = "/AdultContentOn"
    if cmd2.button("🧠 /Memory", use_container_width=True): accion_seleccionada = "/MemoryContinuity"
    if cmd3.button("⏪ /retcon", use_container_width=True): accion_seleccionada = "/retcon"
    if cmd4.button("🔧 /Fix", use_container_width=True): accion_seleccionada = "/Fix"
    if cmd5.button("💾 /save", use_container_width=True): accion_seleccionada = "/save"
    if cmd6.button("🖼️ /scene", use_container_width=True): accion_seleccionada = "/scene"

    if accion_seleccionada:
        with st.spinner("Procesando turno..."):
            try:
                mensaje_api = accion_seleccionada
                if st.session_state.get("needs_context_injection", False):
                    contexto_guardado = st.session_state.get("original_save_data", "")
                    mensaje_api = f"[SISTEMA: MEMORIA COMPRIMIDA. ESTADO ACTUAL DE LA PARTIDA]:\n{contexto_guardado}\n\nRetoma estrictamente desde este contexto manteniendo el formato XML. Siguiente acción del jugador/comando: {accion_seleccionada}"
                    st.session_state.needs_context_injection = False

                response = st.session_state.chat_session.send_message(mensaje_api)
                parsed_resp = parse_ai_response(response.text)
                
                img_data, img_type = None, None
                if accion_seleccionada == "/scene" and parsed_resp["imagen_prompt"]:
                    with st.spinner("🎨 Renderizando escenografía..."):
                        res = generate_image_for_turn(parsed_resp["imagen_prompt"], selected_img_model)
                        if res:
                            img_data, img_type = res["data"], res["type"]
                            st.session_state.cg_gallery.append(res["data"])

                st.session_state.narrative_history.append({"role": "user", "text": accion_seleccionada})
                st.session_state.narrative_history.append({
                    "role": "ia", 
                    "text": response.text,
                    "img_data": img_data,
                    "img_type": img_type
                })
                
                # Lógica de Compresión y Autoguardado Invisible (Hiper optimizado)
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

                    # Purgar y resetear API session
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
    # --- REPRODUCTOR DE AUDIO DINÁMICO (FORZANDO RECARGA EN NAVEGADOR) ---
    ambiente_actual = datos_actuales.get("ambiente", "Silencio")
    track_url = AUDIO_TRACKS.get(ambiente_actual, "")
    color_acento = datos_actuales.get('tema', {}).get('acento', '#00ff9d') if datos_actuales.get('tema') else '#00ff9d'
    
    if track_url:
        # Añadir un timestamp oculta engaña al navegador para que descarte el caché y cargue el nuevo audio
        cache_buster_url = f"{track_url}?t={int(time.time())}"
        st.markdown(f"""
        <div style="padding: 10px; border-radius: 5px; background: rgba(0,0,0,0.4); border: 1px solid {color_acento}; margin-bottom: 15px;">
            <strong style="color: {color_acento};">🎧 Ambiente Activo: {ambiente_actual}</strong><br>
            <audio id="audio_{ambiente_actual}" controls autoplay loop style="width: 100%; height: 35px; margin-top: 5px; border-radius: 5px;">
                <source src="{cache_buster_url}" type="audio/mpeg">
            </audio>
        </div>
        """, unsafe_allow_html=True)
    # -------------------------------------

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
                for i, img_url in enumerate(reversed(st.session_state.cg_gallery)):
                    with cols[i % 2]:
                        st.image(img_url, use_container_width=True, caption=f"Escena #{len(st.session_state.cg_gallery) - i}")
            else:
                st.caption("Aún no has desbloqueado ninguna CG. ¡Presiona 🖼️ /scene durante un momento clave de la historia para generar arte!")