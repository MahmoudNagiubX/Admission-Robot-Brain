import os
import sys
import threading
import pyaudio
from dotenv import load_dotenv

# NEW IMPORTS FOR ARABIC RTL FIX
import arabic_reshaper
from bidi.algorithm import get_display

from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions,
)

# Load the API key
load_dotenv()
API_KEY = os.getenv("DEEPGRAM_API_KEY")

# Audio Settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
DEVICE_INDEX = 1  # Your working Realtek Microphone Array

is_recording = True

def main():
    global is_recording
    try:
        deepgram = DeepgramClient(API_KEY)
        dg_connection = deepgram.listen.websocket.v("1")

        # Handle incoming text
        def on_message(self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) > 0:
                # FIX ARABIC TEXT REVERSAL
                # 1. Reshaper connects the letters (e.g., م ـ ر ـ ح ـ ب ـ ا becomes مرحبا)
                reshaped_text = arabic_reshaper.reshape(sentence)
                # 2. bidi flips the text direction so it reads right-to-left correctly
                corrected_text = get_display(reshaped_text)
                
                print(f"\rYou: {corrected_text}")
                sys.stdout.write("Listening... ")
                sys.stdout.flush()

        def on_error(self, error, **kwargs):
            print(f"\nDeepgram Error: {error}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        # Configure the live stream (Make sure language="ar" if testing Arabic)
        options = LiveOptions(
            model="nova-3",
            language="ar", # Set to "ar" for Arabic, or "en" for English
            smart_format=True,
            encoding="linear16", 
            channels=1,          
            sample_rate=16000,   
        )

        if dg_connection.start(options) is False:
            print("Failed to connect to Deepgram")
            return

        p = pyaudio.PyAudio()
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=DEVICE_INDEX,
            frames_per_buffer=CHUNK
        )

        print("\n--- Microphone active. Start speaking! ---")
        sys.stdout.write("Listening... ")
        sys.stdout.flush()

        def send_audio():
            while is_recording:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    dg_connection.send(data)
                except Exception as e:
                    print(f"Stream error: {e}")
                    break

        sender_thread = threading.Thread(target=send_audio)
        sender_thread.start()

        input()
        
        is_recording = False
        sender_thread.join()

        print("\nStopping...")
        stream.stop_stream()
        stream.close()
        p.terminate()
        dg_connection.finish()
        print("Finished.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()