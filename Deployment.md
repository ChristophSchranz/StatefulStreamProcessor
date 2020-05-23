# Deployment Nodes for the project


## 01 Simulator

Unzip the events in `01_Simulator` with the name `events.json`.
This file has 1402232 rows with different number of values each.

```bash
cd 01_Simulator
python3 simulator.py
```

Set the variables with in `simulator.py`. The defauls are

* BROKER_HOST = "localhost"
* BROKER_PORT = 1883
* EVENT_FILE = "events.json"
* TOPIC_NAME = "machine/states"
* SAMPLE_RATE = 1000

The maximum sample rate is around 1 kS/s.

## 02 MQTT Broker

This step requires a running docker-compose installation. Therefore, run:

1. Install [Docker](https://www.docker.com/community-edition#/download) version **1.10.0+**
2. Install [Docker Compose](https://docs.docker.com/compose/install/) version **1.6.0+**

To set up the MQTT Broker locally with the default
port of `1883`, run:

```bash
cd 02_MQTT_Broker
docker-compose up --build -d
```

To check if the service is available or 
to stop it, run:

```bash
cd 02_MQTT_Broker
docker-compose ps
docker-compose stop
```




## 03 Stream Connector

To install the requirements for the Stream Connector, run these lines:

```bash
# Install Kafka version 2.5 to /kafka
cd 03_Stream_Connector
bash install_kafka_libs-1v4.sh
pip install confluent-kafka==1.4.2
```




## 04 Kafka

To setup Apache Kafka, run these lines:

```bash
# Install Kafka version 2.5 to /kafka
cd 04_Kafka
bash install_kafka-2v5.sh
# Copy the systemd service files
sudo cp zookeeper.service /etc/systemd/system/zookeeper.service 
sudo cp kafka.service /etc/systemd/system/kafka.service 
```

Update services and enable auto-start:
```bash
sudo systemctl enable kafka
sudo systemctl enable zookeeper
```

Then (re-) start the services.
```bash
sudo systemctl stop zookeeper
sudo systemctl stop kafka
sudo systemctl restart zookeeper
sudo systemctl status --no-pager zookeeper
sudo systemctl restart kafka
sudo systemctl status --no-pager kafka
```

For a more detailed investigation `sudo journalctl -b -u zookeeper.service -f`
is useful (or use other parameters as `-e`)!


Now, we can create our topic with the specified configs. Note that the MQTT records are streamed to the topic
`machine.data`. Flink consumes records from this topic, processes them and writes the aggregated records to 
`machine.out`.

```bash
/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic machine.data --replication-factor 1 --partitions 5 --config cleanup.policy=compact --config retention.ms=172800000
/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic machine.out --replication-factor 1 --partitions 3 --config cleanup.policy=compact --config retention.ms=172800000
# check if the topic was created with the correct configs:
/kafka/bin/kafka-topics.sh --bootstrap-server :2181 --describe --topic machine.data
```

Here are some other useful command for
```bash
/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
/kafka/bin/kafka-topics.sh --bootstrap-server :2181 --delete --topic machine.data
```

In order to test the installation, open two terminal windows and start
the consumer and producer instance each:
```bash
/kafka/bin/kafka-console-producer.sh --broker-list 127.0.0.1:9092 --topic machine.data --property parse.key=true --property key.separator=,
/kafka/bin/kafka-console-consumer.sh --bootstrap-server 127.0.0.1:9092 --topic machine.data --from-beginning --property print.key=true --property key.separator=,
```
After that, you can stream messages of the form `[key],[value]` from the producer to the consumer,
e.g. `0,helloKafka`.




