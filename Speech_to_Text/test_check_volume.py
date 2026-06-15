import pyaudio
import audioop
import sys
import time

# Settings matching our Deepgram configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
DEVICE_INDEX = 1  # Your Microphone Array

p = pyaudio.PyAudio()

try:
    # Try opening the raw stream from Index 1
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=DEVICE_INDEX,
        frames_per_buffer=CHUNK
    )
    
    print("\n=== TESTING MICROPHONE VOLUME ===")
    print("Speak or blow into the microphone now... Press Ctrl+C to stop.\n")
    
    # Run a loop for about 10 seconds to read sound data
    for _ in range(0, int(RATE / CHUNK * 10)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        # Calculate the Root Mean Square (RMS) which represents volume level
        rms = audioop.rms(data, 2)
        
        # Create a simple visual volume bar in the terminal
        bar = '#' * int(rms / 200)
        sys.stdout.write(f"\rVolume Level: {rms:<5} {bar}")
        sys.stdout.flush()
        time.sleep(0.01)

except Exception as e:
    print(f"\nHardware Error opening microphone: {e}")

finally:
    print("\n\nTesting complete.")
    if 'stream' in locals():
        stream.stop_stream()
        stream.close()
    p.terminate()