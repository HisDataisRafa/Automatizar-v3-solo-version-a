import streamlit as st
import requests
import io
from datetime import datetime
import json
import time
import os
import zipfile

# Inicialización del estado de la sesión para mantener los archivos
if 'current_generation' not in st.session_state:
    st.session_state.current_generation = {
        'zip_contents': None,
        'timestamp': None,
        'files_generated': False
    }

def split_text_for_tts(text, max_chars=250):
    """
    Divide el texto en fragmentos más pequeños respetando:
    1. Puntos finales
    2. Máximo de caracteres
    3. Estructura de párrafos
    4. División por comas en oraciones largas
    """
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    fragments = []
    current_fragment = ""
    
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            fragments.append(paragraph)
            continue
            
        sentences = [s.strip() + '.' for s in paragraph.replace('. ', '.').split('.') if s.strip()]
        
        for sentence in sentences:
            if len(sentence) > max_chars:
                parts = sentence.split(',')
                current_part = ""
                
                for part in parts:
                    part = part.strip()
                    if len(current_part) + len(part) + 2 <= max_chars:
                        current_part = (current_part + ", " + part).strip(", ")
                    else:
                        if current_part:
                            fragments.append(current_part + ".")
                        current_part = part
                
                if current_part:
                    fragments.append(current_part + ".")
                    
            elif len(current_fragment + sentence) > max_chars:
                if current_fragment:
                    fragments.append(current_fragment.strip())
                current_fragment = sentence
            else:
                current_fragment = (current_fragment + " " + sentence).strip()
        
        if current_fragment:
            fragments.append(current_fragment)
            current_fragment = ""
    
    if current_fragment:
        fragments.append(current_fragment)
    
    return fragments

def generate_audio_with_retries(text, api_key, voice_id, stability, similarity, use_speaker_boost, 
                              fragment_number, model_id="eleven_multilingual_v2"):
    """
    Genera audio usando la API de Eleven Labs optimizado para una sola versión.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity,
            "style": 0,
            "use_speaker_boost": use_speaker_boost
        }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            filename = f"{fragment_number}.mp3"
            return [{'content': response.content, 'filename': filename, 'text': text}]
        else:
            st.warning(f"Error en la generación: {response.status_code}")
            st.warning(f"Detalles: {response.text}")
    except Exception as e:
        st.error(f"Error en la solicitud: {str(e)}")
    
    time.sleep(5.5)
    return []

def get_available_voices(api_key):
    """
    Obtiene la lista de voces disponibles de Eleven Labs
    """
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {
        "Accept": "application/json",
        "xi-api-key": api_key
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            voices = response.json()["voices"]
            return {voice["name"]: voice["voice_id"] for voice in voices}
        return {}
    except:
        return {}

def create_zip_file(audio_files):
    """
    Crea un único archivo ZIP con los audios generados
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for audio in audio_files:
            zip_file.writestr(audio['filename'], audio['content'])
    return zip_buffer.getvalue()

def main():
    st.title("🎙️ Generador de Audio con Eleven Labs")
    st.write("Convierte texto a audio de alta calidad")
    
    # Configuración en la barra lateral
    st.sidebar.header("Configuración")
    
    api_key = st.sidebar.text_input("API Key de Eleven Labs", type="password")
    
    max_chars = st.sidebar.number_input("Máximo de caracteres por fragmento", 
                                      min_value=100, 
                                      max_value=500, 
                                      value=220)
    
    model_id = "eleven_multilingual_v2"
    st.sidebar.markdown("""
    **Modelo:** Eleven Multilingual v2
    - Soporta múltiples idiomas
    - Optimizado para calidad
    """)
    
    stability = st.sidebar.slider("Stability", 
                                min_value=0.0, 
                                max_value=1.0, 
                                value=0.52,
                                step=0.01)
    
    similarity = st.sidebar.slider("Similarity", 
                                 min_value=0.0, 
                                 max_value=1.0, 
                                 value=0.82,
                                 step=0.01)
                                 
    use_speaker_boost = st.sidebar.checkbox("Speaker Boost", value=True)
    
    if api_key:
        voices = get_available_voices(api_key)
        if voices:
            selected_voice_name = st.sidebar.selectbox("Seleccionar voz", 
                                                     list(voices.keys()))
            voice_id = voices[selected_voice_name]
        else:
            st.sidebar.error("No se pudieron cargar las voces. Verifica tu API key.")
            return
    
    text_input = st.text_area("Ingresa tu texto", height=200)
    
    if st.button("Procesar texto y generar audio"):
        if not text_input or not api_key:
            st.warning("Por favor ingresa el texto y la API key.")
            return
        
        fragments = split_text_for_tts(text_input, max_chars)
        st.info(f"Se generarán {len(fragments)} fragmentos")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        all_audio_files = []
        total_fragments = len(fragments)
        
        for i, fragment in enumerate(fragments, 1):
            status_text.text(f"Procesando fragmento {i}/{total_fragments}...")
            
            audio_results = generate_audio_with_retries(
                fragment,
                api_key,
                voice_id,
                stability,
                similarity,
                use_speaker_boost,
                i
            )
            
            all_audio_files.extend(audio_results)
            progress_bar.progress(i / total_fragments)
            
            with st.expander(f"Fragmento {i}"):
                st.write(fragment)
                for result in audio_results:
                    st.audio(result['content'], format="audio/mp3")
        
        status_text.text("¡Proceso completado! Preparando archivo ZIP...")
        
        if all_audio_files:
            st.session_state.current_generation = {
                'zip_contents': create_zip_file(all_audio_files),
                'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
                'files_generated': True
            }
    
    if st.session_state.current_generation['files_generated']:
        st.subheader("📥 Descargar archivos generados")
        
        timestamp = st.session_state.current_generation['timestamp']
        
        st.download_button(
            label="⬇️ Descargar todos los audios",
            data=st.session_state.current_generation['zip_contents'],
            file_name=f"audios_generados_{timestamp}.zip",
            mime="application/zip"
        )
        
        st.success("Los archivos están listos para descargar.")

if __name__ == "__main__":
    main()
    main()
