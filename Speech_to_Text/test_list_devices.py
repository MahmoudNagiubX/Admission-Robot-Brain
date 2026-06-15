import pyaudio

p = pyaudio.PyAudio()
info = p.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')

print("\n=== AVAILABLE AUDIO INPUT DEVICES ===")
for i in range(0, numdevices):
    device_info = p.get_device_info_by_host_api_device_index(0, i)
    if device_info.get('maxInputChannels') > 0:
        print(f"Index {i}: {device_info.get('name')}")
print("=====================================\n")

p.terminate()