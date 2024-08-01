################################################################
# Satellite to Ground Communication Support Program
# 위성 통신 보조 프로그램
# CCSDS 패킷에 따라서 패킷 조립 및 분해
# UDP/IP 통신과 nrf 통신을 하나의 프로그램으로 통제해야 함.
################################################################

# 헤더 작성

# nrf24 통신 설정

# UDP/IP 통신 설정

# UDP/IP 수신

# UDP/IP 송신

# nrf24l01 송신

# nrf24l01 수신
# CRC or ACK 등의 데이터 무결성 확인 필요(?)

# CCSDS 패킷 분해
# 헤더 : 처음 6바이트까지
# 32 바이트씩 쪼개서 데이터 순서 지정

# CCSDS 패킷 재조립
# 32바이트씩 쪼개서 들어오는 데이터의 재조립
# 재조립 이후 헤더에서의 데이터 길이와 실제 데이터 길이를 비교하여
# 데이터 무결성 확인(?)

# 시리얼 통신시 0x00 바이트인 경우 통신 중단됨.
# 이를 방지하기 위한 데이터 변조 실시