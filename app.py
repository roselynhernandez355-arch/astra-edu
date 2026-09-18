import streamlit as st
import requests
import json
import io
import re
import urllib.parse
from PIL import Image, ImageDraw, ImageFont

# Configuración de API en la nube (Groq)
GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Soporte opcional para lectura de PDF
try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

st.set_page_config(page_title="Astra Edu", page_icon="🪐", layout="wide")

# --- ESTILOS CSS ---
custom_css = """
<style>
    .stApp {
        background-color: #030408 !important;
        background-image: 
            radial-gradient(circle at 15% 15%, rgba(255, 30, 39, 0.08) 0%, transparent 35%),
            radial-gradient(circle at 85% 85%, rgba(56, 189, 248, 0.08) 0%, transparent 35%),
            radial-gradient(#fff, rgba(255,255,255,.08) 1px, transparent 15px) !important;
        background-size: 100% 100%, 100% 100%, 250px 250px !important;
        color: #f1f5f9 !important;
        font-family: 'Inter', system-ui, sans-serif;
    }
    
    section[data-testid="stSidebar"] {
        background: #060812 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
    }

    .sidebar-title { font-size: 1.4rem; font-weight: 700; color: #ffffff; }
    .sidebar-sub { color: #ff3b44; font-size: 0.75rem; font-weight: 600; margin-bottom: 10px; }

    .stTabs [data-baseweb="tab-list"] { gap: 10px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
    .stTabs [data-baseweb="tab"] { background-color: #0c0e1e !important; color: #94a3b8 !important; border-radius: 8px !important; }
    .stTabs [aria-selected="true"] { background: #0f172a !important; color: #38bdf8 !important; border: 1px solid #38bdf8 !important; }

    .stChatMessage { background-color: transparent !important; }
    .stChatInputContainer { border: 1px solid rgba(255, 59, 68, 0.3) !important; background-color: #060812 !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- ESTADO DE LA SESIÓN ---
if "last_generated_image" not in st.session_state: st.session_state.last_generated_image = None
if "flashcards" not in st.session_state: st.session_state.flashcards = []
if "file_context" not in st.session_state: st.session_state.file_context = ""
if "messages" not in st.session_state: st.session_state.messages = []

# --- FUNCIONES ---
def clean_prompt_fast(prompt):
    clean = re.sub(r'^(quiero|necesito|dibuja|genera|crea|haz|muestra)?\s*(una|un|la|el)?\s*(imagen|dibujo|foto)?\s*(de|sobre)?\s*', '', prompt, flags=re.IGNORECASE).strip()
    dict_terms = {"agujero negro supermasivo": "supermassive black hole", "agujero negro": "black hole", "galaxia": "galaxy", "planeta": "planet", "estrella": "star"}
    clean_lower = clean.lower()
    for es, en in dict_terms.items():
        if es in clean_lower: clean_lower = clean_lower.replace(es, en)
    return clean_lower

def add_watermark(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        txt_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)
        text = "Astra Edu"
        font_size = max(18, int(img.width * 0.035))
        try: font = ImageFont.truetype("arial.ttf", font_size)
        except IOError: font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        px, py = 20, 12
        x, y = img.width - text_w - 20, img.height - text_h - 22
        draw.rectangle([x-px, y-py, img.width, img.height], fill=(5, 6, 15, 255))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
        out_b = io.BytesIO()
        Image.alpha_composite(img, txt_layer).convert("RGB").save(out_b, format="JPEG", quality=90)
        return out_b.getvalue()
    except Exception: return image_bytes

def generate_image_with_watermark(prompt):
    english_prompt = clean_prompt_fast(prompt)
    encoded_p = urllib.parse.quote(f"{english_prompt}, cinematic space photo, realistic astrophysics, highly detailed, 8k resolution, cosmic background")
    url = f"https://image.pollinations.ai/prompt/{encoded_p}?width=768&height=768&model=flux"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200: return add_watermark(response.content)
    except Exception: pass 
    return None

def extract_text_from_file(uploaded_file):
    text = ""
    try:
        file_type = uploaded_file.name.split(".")[-1].lower()
        if file_type == "txt": text = uploaded_file.read().decode("utf-8", errors="ignore")
        elif file_type == "pdf" and PDF_SUPPORT:
            for page in PdfReader(uploaded_file).pages:
                content = page.extract_text()
                if content: text += content + "\n"
    except Exception: return "Error al leer el archivo."
    return text

def safe_eval_math_advanced(prompt_text):
    cleaned = prompt_text.lower().replace("x", "*").replace("entre", "/").replace("dividido", "/")
    matches = re.findall(r'(\d+(?:\.\d+)?)\s*([\+\-\*\/])\s*(\d+(?:\.\d+)?)', cleaned)
    if matches:
        n1, op, n2 = matches[-1]
        try:
            a, b = float(n1), float(n2)
            if op == "/": res = "Cero." if b == 0 else a / b
            elif op == "*": res = a * b
            elif op == "+": res = a + b
            elif op == "-": res = a - b
            return f"📐 **{n1} {op} {n2}** = **{int(res) if res.is_integer() else round(res, 4)}**"
        except Exception: pass
    return None

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown("<div class='sidebar-title'>🪐 Astra Edu</div>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-sub'>SISTEMA EDUCATIVO ESPACIAL Cloud</div>", unsafe_allow_html=True)
    memory_limit = st.slider("🧠 Límite de Memoria", 2, 8, 4, 1)

    uploaded_file = st.file_uploader("📄 Leer Documento (PDF / TXT)", type=["txt", "pdf"])
    if uploaded_file:
        st.session_state.file_context = extract_text_from_file(uploaded_file)[:1000]
        if st.session_state.file_context: st.success("Documento cargado.")

    st.markdown("---")
    if st.button("🗑️ Limpiar Conversación", use_container_width=True):
        st.session_state.messages, st.session_state.flashcards, st.session_state.last_generated_image = [], [], None
        st.rerun()

# --- PESTAÑAS PRINCIPALES ---
tab_chat, tab_cards, tab_img, tab_math = st.tabs(["💬 Chat", "🎴 Flashcards", "🎨 Imágenes", "🧮 Calculadora"])

# TAB CHAT
with tab_chat:
    for msg in st.session_state.messages:
        avatar_icon = "🪐" if msg["role"] == "user" else "👽"
        with st.chat_message(msg["role"], avatar=avatar_icon):
            st.markdown(msg["content"])

prompt = st.chat_input("Consulta con Astra Edu...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with tab_chat:
        with st.chat_message("user", avatar="🪐"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="👽"):
            response_placeholder, full_response, prompt_lower = st.empty(), "", prompt.lower()
            
            if any(p in prompt_lower for p in ["genera una imagen", "dibuja", "crea una imagen"]):
                with st.spinner("Generando render en la nube..."):
                    clean_p = prompt_lower.replace("genera una imagen", "").replace("dibuja", "").replace("de", "").strip()
                    img_b = generate_image_with_watermark(clean_p if clean_p else prompt)
                    if img_b:
                        st.image(img_b, width=450)
                        full_response = f"🎨 Imagen generada: '{clean_p if clean_p else prompt}'"
                    else: full_response = "Error al generar la imagen."
                response_placeholder.markdown(full_response)
            
            else:
                math_result = safe_eval_math_advanced(prompt)
                if math_result:
                    full_response = math_result
                    response_placeholder.markdown(full_response)
                else:
                    system_prompt_text = (
                        "Eres Astra Edu, un tutor educativo espacial preciso. Responde de forma clara en español. "
                        "Si el usuario hace una pregunta general (como cuántos elementos hay en la tabla periódica), "
                        "responde formalmente sobre el tema general sin encasillarte en el tema previo."
                    )
                    if st.session_state.file_context:
                        system_prompt_text += f"\n[DOCUMENTO ADJUNTO]: {st.session_state.file_context}"

                    system_msg = {"role": "system", "content": system_prompt_text}
                    history_payload = [system_msg] + st.session_state.messages[-memory_limit:]
                    
                    headers = {
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    
                    payload = {
                        "model": "llama-3.3-70b-versatile",
                        "messages": history_payload,
                        "temperature": 0.3,
                        "max_tokens": 400
                    }

                    try:
                        res = requests.post(GROQ_URL, json=payload, headers=headers, timeout=20)
                        if res.status_code == 200:
                            full_response = res.json()["choices"][0]["message"]["content"]
                            response_placeholder.markdown(full_response)
                        else:
                            full_response = "Error de conexión con la API de Groq."
                            st.error(full_response)
                    except Exception:
                        full_response = "Error de red al conectar con la nube."
                        st.error(full_response)
            
        st.session_state.messages.append({"role": "assistant", "content": full_response})

# TAB FLASHCARDS
with tab_cards:
    st.subheader("🎴 Tarjetas de Estudio")
    c1, c2 = st.columns(2)
    with c1: card_q = st.text_input("Concepto:")
    with c2: card_a = st.text_input("Explicación:")
    if st.button("➕ Guardar Flashcard"):
        if card_q and card_a: st.session_state.flashcards.append({"q": card_q, "a": card_a}); st.rerun()
    st.divider()
    for card in st.session_state.flashcards:
        with st.expander(f"📖 {card['q']}"): st.write(card['a'])

# TAB IMÁGENES
with tab_img:
    st.subheader("🎨 Generador Visual Espacial")
    img_prompt_in = st.text_input("Describe la imagen:")
    if img_prompt_in and st.button("Generar Visual"):
        with st.spinner("Generando..."):
            img_b = generate_image_with_watermark(img_prompt_in)
            if img_b: st.session_state.last_generated_image = img_b
    if st.session_state.last_generated_image: st.image(st.session_state.last_generated_image, width=500)

# TAB CALCULADORA
with tab_math:
    st.subheader("🧮 Calculadora Rápida")
    math_input = st.text_input("Operación (Ej: 1400 / 3.14):")
    if math_input:
        res = safe_eval_math_advanced(math_input)
        if res: st.markdown(res)