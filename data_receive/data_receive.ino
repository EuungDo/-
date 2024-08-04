#include <Arduino.h>
#include <SPI.h>
#include "RF24.h"

#define HEADER_SIZE 6
#define BAUD_RATE 230400
#define PAYLOAD_SIZE 32

#define CE_PIN 7
#define CSN_PIN 8

RF24 radio(CE_PIN, CSN_PIN);

uint8_t address[][6] = { "1Node", "2Node" };

struct ParsedHeader {
  uint8_t versionNumber;
  uint8_t packetType;
  uint8_t secondaryHeaderFlag;
  uint16_t apid;
  uint8_t sequenceFlags;
  uint16_t packetSequenceCount;
  uint16_t packetLength;
};

ParsedHeader parsePrimaryHeader(byte* header) {
  uint16_t versionTypeSecflagApid = (header[0] << 8) | header[1];
  uint16_t seqFlagsSeqCount = (header[2] << 8) | header[3];
  uint16_t packetLength = (header[4] << 8) | header[5];

  ParsedHeader parsedHeader;
  parsedHeader.versionNumber = (versionTypeSecflagApid >> 13) & 0x07;
  parsedHeader.packetType = (versionTypeSecflagApid >> 12) & 0x01;
  parsedHeader.secondaryHeaderFlag = (versionTypeSecflagApid >> 11) & 0x01;
  parsedHeader.apid = versionTypeSecflagApid & 0x07FF;
  parsedHeader.sequenceFlags = (seqFlagsSeqCount >> 14) & 0x03;
  parsedHeader.packetSequenceCount = seqFlagsSeqCount & 0x3FFF;
  parsedHeader.packetLength = packetLength;

  return parsedHeader;
}

void setup() {
  Serial.begin(BAUD_RATE);
  //Serial.println("패킷 수신 준비 완료...");

  if (!radio.begin()) {
    Serial.println(F("라디오가 응답하지 않습니다"));
    while (1) {}
  }
  radio.setPALevel(RF24_PA_LOW);
  radio.setPayloadSize(PAYLOAD_SIZE);
  radio.openReadingPipe(1, address[0]);
  radio.setChannel(100);
  radio.startListening();
  radio.setDataRate(RF24_1MBPS);
}

byte data[1024];  // 최대 데이터 길이 설정, 필요에 따라 조정 가능
int dataIndex = 0;
int totalLength = 0;
bool headerParsed = false;

void loop() {
  if (radio.available()) {
    byte payload[PAYLOAD_SIZE];
    radio.read(payload, PAYLOAD_SIZE); // 32바이트씩 데이터 읽기

    // 수신한 데이터를 전체 데이터 버퍼에 복사
    for (int i = 0; i < PAYLOAD_SIZE; i++) {
      if (dataIndex < sizeof(data)) {
        data[dataIndex++] = payload[i];
      }
    }

    // 헤더가 파싱되지 않았으면 헤더를 파싱
    if (!headerParsed && dataIndex >= HEADER_SIZE) {
      ParsedHeader header = parsePrimaryHeader(data);
      /*
      Serial.print("Version Number: "); Serial.println(header.versionNumber);
      Serial.print("Packet Type: "); Serial.println(header.packetType);
      Serial.print("Secondary Header Flag: "); Serial.println(header.secondaryHeaderFlag);
      Serial.print("APID: "); Serial.println(header.apid);
      Serial.print("Sequence Flags: "); Serial.println(header.sequenceFlags);
      Serial.print("Packet Sequence Count: "); Serial.println(header.packetSequenceCount);
      Serial.print("Packet Length: "); Serial.println(header.packetLength);
      */
      totalLength = HEADER_SIZE + header.packetLength + 1; // 전체 패킷 길이 계산
      headerParsed = true;
    }

    // 전체 데이터가 수신되었으면 시리얼로 출력
    if (headerParsed && dataIndex >= totalLength) {
      if (totalLength <= 32) {
        // 패킷이 32바이트 이하인 경우 그대로 전송
        Serial.write(data, totalLength);

        // dataIndex를 초기화
        dataIndex = 0;
        headerParsed = false;
      } else {
        // 패킷이 32바이트보다 큰 경우 전체 패킷이 수신될 때까지 대기한 후 전송
        Serial.write(data, totalLength);

        // 남은 데이터를 별도의 버퍼로 이동
        int remainingDataLength = dataIndex - totalLength;
        for (int i = 0; i < remainingDataLength; i++) {
          data[i] = data[totalLength + i];
        }

        // dataIndex를 초기화
        dataIndex = 0;
        headerParsed = false;
      }
    }
  }
}
