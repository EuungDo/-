import time
import socket
import serial
import threading
import struct
from queue import Queue

###############################################################
# Ground to Satellite Communication Support Program
# 지상국 통신 보조 프로그램
# 송신과 수신을 각각 담당하는 두개의 아두이노를 이용해 데이터 송/수신
###############################################################

#########################################################################################
#
# 시리얼 통신 및 큐(Queue) 설정
#
#########################################################################################

# 송신용 아두이노 시리얼 포트 설정
ser_tx = serial.Serial(
    port='/dev/ttyACM1',  # 적절한 포트로 변경
    baudrate=115200,
    timeout=1
)

# 수신용 아두이노 시리얼 포트 설정
ser_rx = serial.Serial(
    port='/dev/ttyACM0',  # 적절한 포트로 변경
    baudrate=115200,
    timeout=1
)

# UDP/IP 큐(Queue) 설정
send_queue = Queue()
receive_queue = Queue()

#########################################################################################
#
# 사용할 함수 정의
#
#########################################################################################

# UDP/IP 수신
def udp_receiver():
    udp_ip = "127.0.0.1"
    udp_port = 1234

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
    udp_port = 1235

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
    while True:
        if not receive_queue.empty():
            message = receive_queue.get()
            sock.sendto(message, (udp_ip, udp_port))
            print(f"Sent UDP message to {udp_ip}:{udp_port}\n {message}")

# 시리얼 송신
def send_to_arduino():
    while True:
        if not send_queue.empty():
            message = send_queue.get()
            escaped_message = escape_data(message)
            if ser_tx.is_open:
                ser_tx.write(escaped_message)
                print(f"Message sent to Arduino on port {ser_tx.port}\n")

# 시리얼 수신 및 데이터 처리
def read_from_arduino():
    received_data = b''
    expected_length = None

    while True:
        if ser_rx.is_open and ser_rx.in_waiting > 0:
            incoming_message = ser_rx.read(32)
            received_data += incoming_message

            while len(received_data) >= 6:  # 최소한 헤더 크기만큼 데이터가 있어야 함
                unescaped_data = unescape_data(received_data)

                if expected_length is None:
                    # 헤더를 읽고 전체 패킷 길이 계산
                    header = unescaped_data[:6]
                    header_info = parse_primary_header(header)
                    total_length = header_info["Packet Length"] + 1 + 6  # 패킷 길이 + 1 + 헤더 크기 (6바이트)
                    expected_length = total_length

                # 수신된 데이터의 총 길이가 예상된 길이와 같거나 클 때
                if len(unescaped_data) >= expected_length:
                    packet = unescaped_data[:expected_length]  # 패킷을 분리
                    print(f"Reassembled Data: {packet.hex()}")
                    receive_queue.put(packet)  # UDP 송신 큐에 추가
                    received_data = received_data[expected_length:]  # 처리한 패킷을 제거
                    expected_length = None
                else:
                    break

# CCSDS 페킷 헤더 분석
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

# 시리얼 통신시 0x00 바이트인 경우 통신 중단됨.
# 이를 방지하기 위한 데이터 변조 실시
def escape_data(data):
    escaped = data.replace(b'\xFF', b'\xFF\xFF').replace(b'\x00', b'\xFF\x00')
    return escaped

def unescape_data(data):
    unescaped = data.replace(b'\xFF\x00', b'\x00').replace(b'\xFF\xFF', b'\xFF')
    return unescaped

# CCSDS 패킷 분해
# 헤더는 처음 6바이트까지
# 32 바이트씩 쪼개서 데이터 저장
def split_data(data, chunk_size=32):
    chunks = []
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        chunks.append(chunk)
    return chunks

#########################################################################################
#
# 메인 함수 작성
#
#########################################################################################

def main():
    # 스레드 시작
    udp_recv_thread = threading.Thread(target=udp_receiver)
    udp_send_thread = threading.Thread(target=udp_sender)
    serial_send_thread = threading.Thread(target=send_to_arduino)
    serial_recv_thread = threading.Thread(target=read_from_arduino)
    
    udp_recv_thread.start()
    udp_send_thread.start()
    serial_send_thread.start()
    serial_recv_thread.start()

    udp_recv_thread.join()
    udp_send_thread.join()
    serial_send_thread.join()
    serial_recv_thread.join()

if __name__ == "__main__":
    main()