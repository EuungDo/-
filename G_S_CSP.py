import socket
import serial
import threading
import struct
from queue import Queue

# 송신용 아두이노 시리얼 포트 설정
ser_tx = serial.Serial(
    port='/dev/ttyACM0',  # 적절한 포트로 변경
    baudrate=230400,
)

ser_rx = serial.Serial(
    port='/dev/ttyACM3',  # 적절한 포트로 변경
    baudrate=230400,
)

# UDP/IP 큐(Queue) 설정
send_queue = Queue()
receive_queue = Queue()

# UDP/IP 수신
def udp_receiver():
    udp_ip = "127.0.0.1"
    udp_port = 1234

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((udp_ip, udp_port))

    print(f"Listening on {udp_ip}:{udp_port}")
    while True:
        data, addr = sock.recvfrom(1024)
        print(f"Received UDP message from {addr}: {data.hex()}")
        send_queue.put(data)
        
#UDP/IP 송신
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
            data = send_queue.get()
            packets = parse_and_split_data(data)
            for packet in packets:
                if ser_tx.is_open:
                    ser_tx.write(packet)
                    print(f"Sent packet to Arduino: {packet.hex()}")

#시리얼 수신
def receive_to_arduino():
    expected_length = None
    buffer = b''

    while True:
        if ser_rx.is_open and ser_rx.in_waiting > 0:
            received_data = ser_rx.read(ser_rx.in_waiting)  # 실제 데이터 읽기
            buffer += received_data
            print(f"Raw received data: {buffer.hex()}")

            while len(buffer) >= 6:  # 최소한 헤더 크기만큼 데이터가 있어야 함
                if expected_length is None:
                    # 헤더를 읽고 전체 패킷 길이 계산
                    header = buffer[:6]
                    header_info = parse_primary_header(header)
                    total_length = header_info["Packet Length"] + 7  # 패킷 길이 + 6바이트 헤더 + 1바이트 추가
                    expected_length = total_length
                    print(f"Expected length: {expected_length}")

                # 수신된 데이터의 총 길이가 예상된 길이와 같거나 클 때
                if len(buffer) >= expected_length:
                    packet = buffer[:expected_length]  # 패킷을 분리
                    print(f"Reassembled Data: {packet.hex()}")
                    receive_queue.put(packet)  # UDP 송신 큐에 추가
                    buffer = buffer[expected_length:]  # 처리한 패킷을 제거
                    expected_length = None
                else:
                    break
          
# 패킷을 파싱
def parse_and_split_data(data):
    packets = []
    data_index = 0

    while data_index < len(data):
        if data_index + 6 <= len(data):
            header = data[data_index:data_index + 6]
            header_info = parse_primary_header(header)
            packet_length = header_info["Packet Length"] + 7  # 6바이트 헤더 + 1바이트 추가 (추가 필요 시 조정)

            if data_index + packet_length <= len(data):
                packet = data[data_index:data_index + packet_length]
                packets.append(packet)
                data_index += packet_length
            else:
                break
        else:
            break

    return packets

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
    # 스레드 시작
    udp_send_thread = threading.Thread(target=udp_sender)
    udp_recv_thread = threading.Thread(target=udp_receiver)
    serial_send_thread = threading.Thread(target=send_to_arduino)
    serial_receive_thread = threading.Thread(target=receive_to_arduino)
    
    udp_send_thread.start()
    udp_recv_thread.start()
    serial_send_thread.start()
    serial_receive_thread.start()

    udp_send_thread.join()
    udp_recv_thread.join()
    serial_send_thread.join()
    serial_receive_thread.join()

if __name__ == "__main__":
    main()