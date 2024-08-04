#include <Arduino.h>
#include <SPI.h>
#include "RF24.h"

#define BAUD_RATE 230400
#define PAYLOAD_SIZE 32

#define CE_PIN 7
#define CSN_PIN 8

RF24 radio(CE_PIN, CSN_PIN);

uint8_t address[][6] = { "1Node", "2Node" };

struct ParsedHeader {
  uint16_t packetLength;
};

ParsedHeader parsePrimaryHeader(byte* header) {
  uint16_t packetLength = (header[4] << 8) | header[5];
  ParsedHeader parsedHeader;
  parsedHeader.packetLength = packetLength;
  return parsedHeader;
}

void setup() {
  Serial.begin(BAUD_RATE);
  Serial.println("시리얼 데이터 수신 준비 완료...");

  if (!radio.begin()) {
    Serial.println(F("라디오가 응답하지 않습니다"));
    while (1) {}
  }
  radio.setPALevel(RF24_PA_LOW);
  radio.setPayloadSize(PAYLOAD_SIZE);
  radio.openWritingPipe(address[1]);
  radio.setChannel(0);
  radio.stopListening();
  radio.setDataRate(RF24_1MBPS);
}

byte buffer[1024];  // 최대 데이터 길이 설정, 필요에 따라 조정 가능
int bufferIndex = 0;

void loop() {
  // 시리얼 데이터 수신
  while (Serial.available() > 0) {
    if (bufferIndex < sizeof(buffer)) {
      buffer[bufferIndex++] = Serial.read();
    }
  }

  // 패킷 처리
  while (bufferIndex >= 6) { // 최소 헤더 크기만큼 데이터가 있는지 확인
    ParsedHeader header = parsePrimaryHeader(buffer);
    int packetLength = header.packetLength + 7; // 6바이트 헤더 + 1바이트 추가 (필요에 따라 조정)

    if (bufferIndex >= packetLength) {
      byte packet[packetLength];
      for (int i = 0; i < packetLength; i++) {
        packet[i] = buffer[i];
      }

      // 패킷 전송
      int remainingLength = packetLength;
      int offset = 0;
      while (remainingLength > 0) {
        byte payload[PAYLOAD_SIZE];
        int chunkSize = min(PAYLOAD_SIZE, remainingLength);
        for (int i = 0; i < chunkSize; i++) {
          payload[i] = packet[offset + i];
        }

        radio.write(payload, chunkSize);
        Serial.println("라디오로 데이터 전송 완료");

        remainingLength -= chunkSize;
        offset += chunkSize;
      }

      // 남은 데이터를 버퍼 앞으로 이동
      int remainingDataLength = bufferIndex - packetLength;
      for (int i = 0; i < remainingDataLength; i++) {
        buffer[i] = buffer[packetLength + i];
      }

      bufferIndex = remainingDataLength;
    } else {
      break; // 패킷이 완전히 수신될 때까지 대기
    }
  }
}
