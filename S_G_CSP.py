import time
import socket
import threading
import struct
from queue import Queue
from pyrf24 import RF24, RF24_PA_HIGH, RF24_PA_LOW, RF24_DRIVER, RF24_1MBPS, RF24_2MBPS

###############################################################
# Satellite to Ground Communication Support Program
# 위성 통신 보조 프로그램
# CCSDS 패킷에 따라서 패킷 조립 및 분해
# UDP/IP 통신과 nrf 통신을 하나의 프로그램으로 통제해야 함.
###############################################################

#########################################################################################
#
# NRF 통신 및 큐(Queue) 설정
#
#########################################################################################

# 수신용 라디오 핀 설정 
CSN_PIN_1 = 0  # SPI0 CE0 -> spidev 0.0
if RF24_DRIVER == 'MRAA':
    CE_PIN_1 = 15
elif RF24_DRIVER == 'wiringPi':
    CE_PIN_1 = 3
else:
    CE_PIN_1 = 22

radio_rx = RF24(CE_PIN_1, CSN_PIN_1)

# 송신용 라디오 핀 설정
CSN_PIN_2 = 12  # SPI1 CE2 -> spidev1.2
if RF24_DRIVER == 'MRAA':
    CE_PIN_2 = 32
elif RF24_DRIVER == 'wiringPi':
    CE_PIN_2 = 26
else:
    CE_PIN_2 = 12

radio_tx = RF24(CE_PIN_2, CSN_PIN_2)

if not radio_rx.begin():
    raise RuntimeError("radio_rx hardware is not responding")

if not radio_tx.begin():
    raise RuntimeError("radio_tx hardware is not responding")

address = [b"1Node", b"2Node"]

# radio_rx Hardware Settinggpej 
radio_rx.setPALevel(RF24_PA_LOW)
radio_rx.openReadingPipe(1, address[1])
radio_rx.setChannel(0)
radio_rx.payloadSize = 32  # Set the payload size to the maximum for simplicity
radio_rx.setDataRate(RF24_1MBPS)
radio_rx.startListening()

# radio_tx Hardware Setting
radio_tx.setPALevel(RF24_PA_LOW)
radio_tx.openWritingPipe(address[0])
radio_tx.setChannel(100)
radio_tx.setDataRate(RF24_1MBPS)
radio_tx.payloadSize = 32

#########################################################################################
## 사용할 함수 정의
#
#########################################################################################

# UDP/IP 수신 및 NRF24L01 송신
def udp_to_nrf24():
    udp_ip = "127.0.0.1"
    udp_port = 1235

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((udp_ip, udp_port))

    print(f"Listening on {udp_ip}:{udp_port}")
    buffer = b''
    
    while True:
        data, addr = sock.recvfrom(1024)
        buffer += data
        print(f"Received UDP message from {addr}, buffer size: {len(buffer)}")
        
        while len(buffer) >= 6:
            header = buffer[:6]
            header_info = parse_primary_header(header)
            packet_length = header_info["Packet Length"] + 1 + 6
            
            if len(buffer) >= packet_length:
                packet = buffer[:packet_length]
                buffer = buffer[packet_length:]
                
                print(f"Processing CCSDS packet: {packet.hex()}")
                chunks = split_data(packet)
                for chunk in chunks:
                    if radio_tx.write(chunk):
                        print(f"Sent chunk: {chunk.hex()}")
                    else:
                        print(f"Sending Failed")
            else:
                break
            
# NRF24L01 수신 및 UDP/IP 송신
def nrf24_to_udp():
    udp_ip = "127.0.0.1"
    udp_port = 1234

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    received_data = b''
    expected_length = None

    while True:
        if radio_rx.available():
            length = radio_rx.getDynamicPayloadSize()
            incoming_message = radio_rx.read(length)
            print(f"Received chunk: {incoming_message.hex()}")
            received_data += incoming_message

            while len(received_data) >= 6:
                if expected_length is None:
                    header = received_data[:6]
                    header_info = parse_primary_header(header)
                    expected_length = header_info["Packet Length"] + 1 + 6
                    print(f"Expected length: {expected_length}")

                if expected_length is not None and len(received_data) >= expected_length:
                    packet = received_data[:expected_length]
                    if packet[0] == 0x00:
                        if len(received_data) < expected_length:
                            continue
                        received_data = b''
                        expected_length = None
                        break
                    print(f"Reassembled Data: {packet.hex()}")
                    sock.sendto(packet, (udp_ip, udp_port))
                    print(f"Sent UDP message to {udp_ip}:{udp_port}\n {packet}")
                    received_data = received_data[expected_length:]
                    expected_length = None
                else:
                    break

            if expected_length is None and len(received_data) < 6:
                received_data = b''
                expected_length = None

# CCSDS 패킷 분해
def split_data(data, chunk_size=32):
    chunks = []
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        chunks.append(chunk)
    return chunks

# CCSDS 패킷 헤더 분석
def parse_primary_header(header):
    version_type_secflag_apid = struct.unpack(">H", header[:2])[0]
    seq_flags_seq_count = struct.unpack(">H", header[2:4])[0]
    packet_length = struct.unpack(">H", header[4:6])[0]

    version_number = (version_type_secflag_apid >> 13) & 0x07
    packet_type = (version_type_secflag_apid >> 12) & 0x01
    secondary_header_flag = (version_type_secflag_apid >> 11) & 0x01
    apid = version_type_secflag_apid & 0x07FF

    sequence_flags = (seq_flags_seq_count >> 14) & 0x03
    packet_sequence_count = seq_flags_seq_count & 0x3FFF

    return {
        "Version Number": version_number,
        "Packet Type": packet_type,
        "Secondary Header Flag": secondary_header_flag,
        "APID": apid,
        "Sequence Flags": sequence_flags,
        "Packet Sequence Count": packet_sequence_count,
        "Packet Length": packet_length
    }

def main():
    # Threads for UDP to NRF24 and NRF24 to UDP
    udp_to_nrf24_thread = threading.Thread(target=udp_to_nrf24)
    nrf24_to_udp_thread = threading.Thread(target=nrf24_to_udp)

    udp_to_nrf24_thread.start()
    nrf24_to_udp_thread.start()
    
    udp_to_nrf24_thread.join()
    nrf24_to_udp_thread.join()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Exiting program")
    finally:
        radio_rx.powerDown()
        radio_tx.powerDown()