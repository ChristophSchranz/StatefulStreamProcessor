#!/usr/bin/env bash
sudo apt-get update && sudo apt-get install make
# Installing librdkafka which is an C client library for Kafka
mkdir /kafka &> /dev/null || true
cd /kafka
git clone https://github.com/edenhill/librdkafka
cd librdkafka
git checkout 1.4.x
./configure && make && sudo make install && sudo ldconfig
