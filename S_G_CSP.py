import time
import socket
import threading
import struct
from queue import Queue
from pyrf24 import RF24, RF24_PA_LOW, RF24_DRIVER

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

receive_queue = Queue()
send_queue = Queue()

# radio_rx Hardware Setting
radio_rx.setPALevel(RF24_PA_LOW)
radio_rx.openReadingPipe(1, address[0])
radio_rx.setChannel(0)
radio_rx.payloadSize = 32  # Set the payload size to the maximum for simplicity
radio_rx.startListening()

# radio_tx Hardware Setting
radio_tx.setPALevel(RF24_PA_LOW)
radio_tx.openWritingPipe(address[1])
radio_tx.setChannel(100)
radio_tx.payloadSize = 32

#########################################################################################
#
# 사용할 함수 정의
#
#########################################################################################

# UDP/IP 수신
def udp_receiver():
    udp_ip = "127.0.0.1"
    udp_port = 1235

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((udp_ip, udp_port))

    print(f"Listening on {udp_ip}:{udp_port}")
    while True:
        data, addr = sock.recvfrom(1024)
        print(f"Received UDP message from {addr}: {data}")
        chunks = split_data(data)
        for chunk in chunks:
            send_queue.put(chunk)

# UDP/IP 송신
def udp_sender():
    udp_ip = "127.0.0.1"
    udp_port = 1234

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
    while True:
        if not receive_queue.empty():
            message = receive_queue.get()
            sock.sendto(message, (udp_ip, udp_port))
            print(f"Sent UDP message to {udp_ip}:{udp_port}\n {message}")

# NRF24L01 송신
def nrf24_sender():
    while True:
        if not send_queue.empty():
            chunk = send_queue.get()
            if radio_tx.write(chunk):
                print(f"Sent chunk: {chunk.hex()}")
            else:
                print("Sending failed")

# NRF24L01 수신 및 데이터 처리
def nrf24_receiver():
    received_data = b''
    expected_length = None

    while True:
        if radio_rx.available():
            length = radio_rx.getDynamicPayloadSize()
            incoming_message = radio_rx.read(length)
            received_data += incoming_message
            print(f"Received chunk: {incoming_message.hex()}")

            while len(received_data) >= 6:  # 최소한 헤더 크기만큼 데이터가 있어야 함
                if expected_length is None:
                    # 헤더를 읽고 전체 패킷 길이 계산
                    header = received_data[:6]
                    header_info = parse_primary_header(header)
                    total_length = header_info["Packet Length"] + 1 + 6  # 패킷 길이 + 1 + 헤더 크기 (6바이트)
                    expected_length = total_length

                # 수신된 데이터의 총 길이가 예상된 길이와 같거나 클 때
                if len(received_data) >= expected_length:
                    packet = received_data[:expected_length]  # 패킷을 분리
                    print(f"Reassembled Data: {packet.hex()}")
                    receive_queue.put(packet)  # UDP 송신 큐에 추가
                    received_data = received_data[expected_length:]  # 처리한 패킷을 제거
                    expected_length = None
                else:
                    break

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

#########################################################################################
#
# 메인 함수 작성
#
#########################################################################################

def main():
    # 스레드 시작
    nrf24_recv_thread = threading.Thread(target=nrf24_receiver)
    udp_recv_thread = threading.Thread(target=udp_receiver)
    udp_send_thread = threading.Thread(target=udp_sender)
    nrf24_send_thread = threading.Thread(target=nrf24_sender)
    
    nrf24_recv_thread.start()
    udp_recv_thread.start()
    udp_send_thread.start()
    nrf24_send_thread.start()

    nrf24_recv_thread.join()
    udp_recv_thread.join()
    udp_send_thread.join()
    nrf24_send_thread.join()

if __name__ == "__main__":
    main()