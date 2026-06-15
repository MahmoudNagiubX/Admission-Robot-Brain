import os
import sys
import json
import asyncio
import pyaudio
import requests
import websockets
from dotenv import load_dotenv

# Arabic text formatting libraries
import arabic_reshaper
from bidi.algorithm import get_display

load_dotenv()
API_KEY = os.getenv("GLADIA_API_KEY")

# Audio Settings (Matching your working Realtek Microphone Array)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
DEVICE_INDEX = 1 

async def main():
    print("\nInitializing Gladia V2 session...")
    
    # 1. Ask Gladia to open a live session and give us a secure WebSocket URL
    try:
        response = requests.post(
            "https://api.gladia.io/v2/live",
            headers={
                "x-gladia-key": API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "sample_rate": RATE,
                "encoding": "wav/pcm",
                "bit_depth": 16,
                "channels": CHANNELS,
                # --- NEW CODE: Restrict to Arabic & English ---
                "language_config": {
                    "languages": ["ar", "en"], # Force the AI to only listen for these two
                    "code_switching": True     # Allow seamless switching mid-sentence
                },
                # Enable real-time text updates while you are speaking
                "messages_config": {
                    "receive_partial_transcripts": True
                }
            }
        )
        response.raise_for_status()
        ws_url = response.json().get("url")
        
    except Exception as e:
        print(f"\nFailed to connect to Gladia: {e}")
        return

    # 2. Connect to the secure WebSocket URL and start streaming
    try:
        async with websockets.connect(ws_url) as websocket:
            print("Connected! --- Microphone active. Start speaking! ---")
            sys.stdout.write("Listening... ")
            sys.stdout.flush()

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

            # Background Task: Read mic and send audio
            async def send_audio():
                loop = asyncio.get_event_loop()
                while True:
                    data = await loop.run_in_executor(None, stream.read, CHUNK, False)
                    await websocket.send(data)
                    await asyncio.sleep(0.001)

            # Background Task: Listen for text coming back
            async def receive_text():
                async for message in websocket:
                    msg = json.loads(message)
                    msg_type = msg.get("type")
                    
                    if msg_type == "transcript":
                        data = msg.get("data", {})
                        utterance = data.get("utterance", {})
                        
                        # Extract the text and check if it is the final committed sentence
                        text = utterance.get("text", "")
                        is_final = data.get("is_final", False)
                        
                        if text:
                            # Fix Arabic rendering
                            reshaped = arabic_reshaper.reshape(text)
                            display_text = get_display(reshaped)
                            
                            if is_final:
                                print(f"\rYou (Final): {display_text:<60}")
                                sys.stdout.write("Listening... ")
                            else:
                                sys.stdout.write(f"\rYou: {display_text:<60}")
                            sys.stdout.flush()
                            
                    elif msg_type == "error":
                        print(f"\nGladia API Error: {msg}")

            # Run both tasks at the same time
            await asyncio.gather(send_audio(), receive_text())

    except Exception as e:
        print(f"\nSession Error: {e}")
    finally:
        if 'stream' in locals():
            stream.stop_stream()
            stream.close()
            p.terminate()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nFinished recording.")