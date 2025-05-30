import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import io
import streamlit as st
import asyncio
import pygame
from pydub import AudioSegment
from gtts import gTTS
import speech_recognition as sr
import threading
import base64
import tempfile
import edge_tts

from streamlit_mic_recorder import mic_recorder
from orchestrator.query_router import handle_market_brief_query


# ---------------------------
# Transcribe Audio
# ---------------------------
def transcribe_audio(audio_bytes):
    recognizer = sr.Recognizer()
    
    # Convert audio bytes (likely WebM or MP3) to WAV using pydub
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    except Exception as e:
        st.error(f"❗ Could not load audio: {e}")
        return "Invalid audio format."

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
        audio.export(tmp_wav.name, format="wav")
        tmp_wav_path = tmp_wav.name

    with sr.AudioFile(tmp_wav_path) as source:
        audio_data = recognizer.record(source)
        try:
            return recognizer.recognize_google(audio_data)
        except sr.UnknownValueError:
            return "Sorry, I couldn't understand the audio."
        except sr.RequestError:
            return "API unavailable."

# TTS with Edge
# ---------------------------
async def speak(text: str):
    try:
        communicate = edge_tts.Communicate(text=text, voice="en-US-GuyNeural")
        temp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        await communicate.save(temp_mp3.name)
        return temp_mp3.name
    except Exception as e:
        st.error(f"❗ TTS error: {e}")
        return None

# ---------------------------
# Render Audio Autoplay
# ---------------------------
def render_audio_player_autoplay(file_path):
    with open(file_path, "rb") as f:
        base64_audio = base64.b64encode(f.read()).decode()

    audio_html = f"""
    <audio id="tts-audio" autoplay>
        <source src="data:audio/mp3;base64,{base64_audio}" type="audio/mp3">
        Your browser does not support the audio element.
    </audio>
    <br>
    <button onclick="document.getElementById('tts-audio').pause()"> Pause</button>
    <button onclick="document.getElementById('tts-audio').play()"> Resume</button>
    """

    st.components.v1.html(audio_html, height=100)

# ---------------------------
# Streamlit App
# ---------------------------
st.set_page_config(page_title="Finance Assistant", layout="centered")
st.title("Voice-Powered Finance Assistant")

st.markdown("🎙️ Click below to record from your mic.")

audio = mic_recorder(start_prompt="Start Recording", stop_prompt="Stop Recording", just_once=True, key="recorder")

if audio and audio['bytes']:
    st.success("✅ Audio recorded!")

    user_query = transcribe_audio(audio['bytes'])
    st.markdown(f"**🗣️ You asked:** {user_query}")

    with st.spinner("💬 Generating response..."):
        response = handle_market_brief_query(user_query)
        cleaned_response = response.replace("### ", "")
        st.markdown(f"** Assistant:** {cleaned_response}")


    with st.spinner("🔈 Generating voice..."):
        tts_path = asyncio.run(speak(cleaned_response))

    if tts_path:
        render_audio_player_autoplay(tts_path)
    else:
        st.warning("⚠️ Failed to generate voice.")
else:
    st.info(" No audio recorded yet.")