import os
import sys
import asyncio
import pyaudio
from dotenv import load_dotenv

# Arabic text formatting libraries
import arabic_reshaper
from bidi.algorithm import get_display

# The NEW Speechmatics real-time client libraries
from speechmatics.rt import (
    AudioEncoding, 
    AudioFormat, 
    ServerMessageType, 
    TranscriptResult,
    TranscriptionConfig, 
    AsyncClient,
)

# Load API Key
load_dotenv()
API_KEY = os.getenv("SPEECHMATICS_API_KEY")

# Audio Settings (Matching your working Realtek Microphone Array)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
DEVICE_INDEX = 1 

# Configure the audio format for Speechmatics
audio_format = AudioFormat(
    encoding=AudioEncoding.PCM_S16LE,
    sample_rate=RATE,
    chunk_size=CHUNK,
)

# Configure the bilingual Arabic/English transcription engine
config = TranscriptionConfig(
    language="ar_en",          
    # "ar" can be added as an additional language. If you ever get a kwargs error here, 
    # you can delete this line and it will fall back to English! 
    max_delay=0.7,
    enable_partials=True          
)

def print_text(text, is_final=False):
    """Reshapes and reverses Arabic text so it displays correctly in the console."""
    if not text:
        return
        
    reshaped = arabic_reshaper.reshape(text)
    display_text = get_display(reshaped)
    
    if is_final:
        print(f"\rYou (Final): {display_text:<60}")
        sys.stdout.write("Listening... ")
    else:
        sys.stdout.write(f"\rYou: {display_text:<60}")
        
    sys.stdout.flush()

async def main():
    # Initialize your hardware microphone
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=DEVICE_INDEX,
        frames_per_buffer=CHUNK
    )

    print("\nConnecting to Speechmatics...")
    sys.stdout.write("Listening... ")
    sys.stdout.flush()

    try:
        # Open the async client connection
        async with AsyncClient(api_key=API_KEY) as client:
            
            # Event handler for partial text (while you are speaking)
            @client.on(ServerMessageType.ADD_PARTIAL_TRANSCRIPT)
            def handle_partials(msg):
                text = TranscriptResult.from_message(msg).metadata.transcript
                if text:
                    print_text(text, is_final=False)

            # Event handler for final text (when you stop speaking)
            @client.on(ServerMessageType.ADD_TRANSCRIPT)
            def handle_finals(msg):
                text = TranscriptResult.from_message(msg).metadata.transcript
                if text:
                    print_text(text, is_final=True)

            # Start the session using our settings
            await client.start_session(
                transcription_config=config,
                audio_format=audio_format
            )

            # Continuously read from the microphone and send to the API
            while True:
                data = stream.read(CHUNK, exception_on_overflow=False)
                await client.send_audio(data)
                
                # Tiny sleep to keep the async event loop moving
                await asyncio.sleep(0.001) 

    except Exception as e:
        print(f"\nSession Error: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        print("\nFinished.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nRecording stopped cleanly.")