import time
import threading
from queue import Queue
from pyrf24 import RF24, RF24_PA_LOW, RF24_DRIVER, RF24_2MBPS

# Set radio_1 CE, CSN PIN
CSN_PIN_1 = 0 #SPI0 CE0 -> spidev 0.0
if RF24_DRIVER == 'MRAA':
    CE_PIN_1 = 15
elif RF24_DRIVER == 'wiringPi':
    CE_PIN_1 = 3
else:
    CE_PIN_1 = 22

radio_1 = RF24(CE_PIN_1, CSN_PIN_1)

# Set radio_2 CE, CSN PIN
CSN_PIN_2 = 12 #SPI1 CE0 -> spidev1.0
if RF24_DRIVER == 'MRAA':
    CE_PIN_2 = 32
elif RF24_DRIVER == 'wiringPi':
    CE_PIN_2 = 26
else:
    CE_PIN_2 = 12

radio_2 = RF24(CE_PIN_2, CSN_PIN_2)

if not radio_1.begin():
    raise RuntimeError("radio_1 hardware is not responding")

if not radio_2.begin():
    raise RuntimeError("radio_2 hardware is not responding")

address = [b"1Node", b"2Node"]

receive_queue = Queue()
send_queue = Queue()

# radio_1 Hardware Setting
radio_1.setPALevel(RF24_PA_LOW)
radio_1.openReadingPipe(1, address[0])
radio_1.setChannel(0)  
radio_1.payloadSize = 32  # Set the payload size to the maximum for simplicity
radio_1.startListening()

# radio_2 Hardware Setting
radio_2.setPALevel(RF24_PA_LOW)
radio_2.openWritingPipe(address[1])
radio_2.setChannel(100)  
radio_2.payloadSize = 32
#radio_2.setDataRate(RF24_2MBPS)
#radio_2.setAutoAck(True)

def forward_data():
    while True:
        
        if radio_1.available():
            received_payload = radio_1.read(32)
            print("Forwarding:",format(received_payload.decode('utf-8').strip()))
            radio_2.write(received_payload)
        
if __name__ == "__main__":
    forward_thread = threading.Thread(target=forward_data)
    forward_thread.start()
    forward_thread.join()
