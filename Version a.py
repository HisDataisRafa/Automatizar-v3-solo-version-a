
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

def split_text_for_tts(text, max_chars=220):
    """
    Divide el texto en fragmentos más pequeños respetando la estructura natural del lenguaje.
    Esta función utiliza un enfoque inteligente que mantiene la coherencia del texto mientras
    respeta el límite de caracteres.
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

def generate_audio(text, api_key, voice_id, stability, similarity, use_speaker_boost, 
                  fragment_number, model_id="eleven_multilingual_v2"):
    """
    Genera audio usando la API de Eleven Labs optimizada para una sola versión.
    Esta función se centra en la calidad y eficiencia, usando los parámetros optimizados.
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
            return {'content': response.content, 'filename': filename, 'text': text}
        else:
            st.error(f"Error en la generación: {response.status_code}")
            st.error(f"Detalle: {response.text}")
        time.sleep(1)  # Pausa breve para evitar límites de rate
    except Exception as e:
        st.error(f"Error en la solicitud: {str(e)}")
    
    return None

def get_available_voices(api_key):
    """
    Obtiene la lista de voces disponibles de Eleven Labs.
    Incluye manejo de errores y verificación de respuesta.
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
    Crea un archivo ZIP con los archivos de audio generados.
    Organiza los archivos de manera clara y consistente.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for audio in audio_files:
            zip_file.writestr(audio['filename'], audio['content'])
    
    return zip_buffer.getvalue()

def main():
    st.title("🎙️ Generador de Audio Optimizado")
    st.write("Convierte texto a voz de alta calidad con parámetros optimizados")
    
    # Configuración en la barra lateral
    st.sidebar.header("Configuración")
    
    api_key = st.sidebar.text_input("API Key de Eleven Labs", type="password")
    
    max_chars = st.sidebar.number_input("Máximo de caracteres por fragmento", 
                                      min_value=100, 
                                      max_value=500, 
                                      value=220)
    
    st.sidebar.markdown("""
    **Modelo:** Eleven Multilingual v2
    - Soporta múltiples idiomas
    - Optimizado para calidad de voz
    """)
    
    # Parámetros optimizados predefinidos
    stability = 0.52
    similarity = 0.82
    use_speaker_boost = True
    
    st.sidebar.markdown("""
    **Parámetros Optimizados:**
    - Stability: 0.52
    - Similarity: 0.82
    - Speaker Boost: Activado
    """)
    
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
    
    if st.button("Generar audio"):
        if not text_input or not api_key:
            st.warning("Por favor ingresa el texto y la API key.")
            return
        
        fragments = split_text_for_tts(text_input, max_chars)
        st.info(f"Se generarán {len(fragments)} fragmentos de audio")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        all_audio_files = []
        total_generations = len(fragments)
        
        for i, fragment in enumerate(fragments, 1):
            status_text.text(f"Generando fragmento {i}/{len(fragments)}...")
            
            result = generate_audio(
                fragment,
                api_key,
                voice_id,
                stability,
                similarity,
                use_speaker_boost,
                i
            )
            
            if result:
                all_audio_files.append(result)
                with st.expander(f"Fragmento {i}"):
                    st.write(fragment)
                    st.audio(result['content'], format="audio/mp3")
            
            progress_bar.progress((i) / total_generations)
        
        status_text.text("¡Proceso completado! Preparando archivo ZIP...")
        
        if all_audio_files:
            # Guardar los resultados en el estado de la sesión
            st.session_state.current_generation = {
                'zip_contents': create_zip_file(all_audio_files),
                'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
                'files_generated': True
            }
    
    # Mostrar el botón de descarga si hay archivos generados
    if st.session_state.current_generation['files_generated']:
        st.subheader("📥 Descargar archivos generados")
        
        timestamp = st.session_state.current_generation['timestamp']
        
        st.download_button(
            label="⬇️ Descargar archivos de audio",
            data=st.session_state.current_generation['zip_contents'],
            file_name=f"audios_generados_{timestamp}.zip",
            mime="application/zip"
        )
        
        st.success("Los archivos están listos para descargar.")

if __name__ == "__main__":
    main()
