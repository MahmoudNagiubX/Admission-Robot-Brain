import os
import sys
import json
import base64
import asyncio
import pyaudio
import websockets
from dotenv import load_dotenv

# Arabic text formatting libraries
import arabic_reshaper
from bidi.algorithm import get_display

# Load API key
load_dotenv()
API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Audio Settings (Matching your working Realtek Microphone Array)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
DEVICE_INDEX = 1 

# The ElevenLabs Realtime Scribe v2 URL
# You can add "&language_code=ar" to the end of this URL to force Arabic mode
URI = "wss://api.elevenlabs.io/v1/speech-to-text/realtime?model_id=scribe_v2_realtime"

async def main():
    print("\nConnecting to ElevenLabs...")
    
    # Pass the API key securely in the headers
    headers = {"xi-api-key": API_KEY}

    try:
        # Open the websocket connection
        async with websockets.connect(URI, additional_headers=headers) as websocket:
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

            # 1. Background Task: Read mic and send audio to ElevenLabs
            async def send_audio():
                loop = asyncio.get_event_loop()
                while True:
                    # Read microphone chunk without blocking the system
                    data = await loop.run_in_executor(None, stream.read, CHUNK, False)
                    
                    # Encode data to base64 format for ElevenLabs
                    base64_audio = base64.b64encode(data).decode('utf-8')
                    
                    # Build and send the JSON packet
                    payload = {
                        "message_type": "input_audio_chunk",
                        "audio_base_64": base64_audio,
                        "sample_rate": RATE
                    }
                    await websocket.send(json.dumps(payload))
                    # Tiny sleep to ensure smooth event loop cycling
                    await asyncio.sleep(0)

            # 2. Background Task: Listen for text coming back from ElevenLabs
            async def receive_text():
                async for message in websocket:
                    response = json.loads(message)
                    msg_type = response.get("message_type")
                    
                    # ElevenLabs sends "partial" text as you speak, and "committed" when you stop
                    if msg_type == "partial_transcript":
                        text = response.get("text", "")
                        if text:
                            # Fix Arabic rendering
                            reshaped = arabic_reshaper.reshape(text)
                            display_text = get_display(reshaped)
                            # Print over the current line so it updates live
                            sys.stdout.write(f"\rYou: {display_text:<50}")
                            sys.stdout.flush()
                            
                    elif msg_type == "committed_transcript":
                        text = response.get("text", "")
                        if text:
                            reshaped = arabic_reshaper.reshape(text)
                            display_text = get_display(reshaped)
                            # Final print of the sentence
                            print(f"\rYou (Final): {display_text:<50}")
                            sys.stdout.write("Listening... ")
                            sys.stdout.flush()
                            
                    elif msg_type == "error":
                        print(f"\nElevenLabs API Error: {response}")

            # Run both the sending and receiving tasks at the exact same time
            await asyncio.gather(send_audio(), receive_text())

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"\nConnection failed. Did you enable 'Speech to Text' permissions on your API key? Error: {e}")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if 'stream' in locals():
            stream.stop_stream()
            stream.close()
            p.terminate()

if __name__ == "__main__":
    try:
        # Start the async loop
        asyncio.run(main())
    except KeyboardInterrupt:
        # Cleanly exit if you press Ctrl+C
        print("\nFinished recording.")