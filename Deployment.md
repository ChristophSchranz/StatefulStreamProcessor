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
docker-compose logs
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


## 05 Flink Setup

To install Apache Flink, simply run:

```bash
pip install apache-flink
```


## 06 Flink

This section explains how to start the stream processing 
within Flink.

## 07 DB Connector

The Database Connector consumes Messages from Kafka, both from 
the topic `machine.data` and `machine.out`, and forwards them
to InfluxDB via RestAPI.

This step requires a reachable InfluxDB endpoint on [localhost:8086](localhost:8086).
To start the application, run:

```bash
cd 07_DB_Connector
python db_connector.py
``` 

In the connector, the package [influxdb-python](https://influxdb-python.readthedocs.io/en/latest/include-readme.html)
was used.

## 08 InfluxDB and Grafana

### Setup

Update the configurations in the environment file `08_InfluxDB/.env`.
**Change the password immediately and never commit this file if the service is available from other 
nodes!** 

To start InfluxDB and also Grafana, run`
```bash
cd 08_InfluxDB
docker-compose up -d
``` 

To validate, if InfluxDB is running correctly, curl the service 
using:

```bash
curl -sl -I http://localhost:8086/ping
# Expected result, note the status code 204
HTTP/1.1 204 No Content
Content-Type: application/json
Request-Id: 2f7091fb-9daa-11ea-8002-0242ac110002
X-Influxdb-Build: OSS
X-Influxdb-Version: 1.8.0
X-Request-Id: 2f7091fb-9daa-11ea-8002-0242ac110002
Date: Sun, 24 May 2020 10:34:45 GMT
```

Grafana is started with InfluxDB and is reachable on
[localhost:3000](http://localhost:3000).


To investigate the services or 
to stop them, run:

```bash
docker-compose ps
docker-compose logs [influxDB|Grafana]
docker-compose stop
```

### First steps in InfluxDB

InfluxDB provides a RestAPI that can be executed via `curl`

```bash
curl -XPOST 'http://localhost:8086/query' --data-urlencode 'q=CREATE DATABASE "mydb"'
curl -XPOST 'http://localhost:8086/query?db=mydb' --data-urlencode 'q=SELECT * INTO "newmeas" FROM "mymeas"'
curl -G 'http://localhost:8086/query?db=mydb&pretty=true' --data-urlencode 'q=SELECT * FROM "mymeas"'
```
More API interface examples can be found [here](https://docs.influxdata.com/influxdb/v1.8/tools/api/).

It is important, that the attributes `time` and all `tags` are
the primary key and must be unique.

### First steps in Grafana

Grafana is started with InfluxDB and is reachable on
[localhost:3000](http://localhost:3000).

To retrieve data from the InfluxDB, add a new data source by 
clicking on `Configuration -> Data Sources -> Add data source`.
Then fill the fields as shown in this screenshot:

![source](docs/grafana_source.png)   

The password is set in the environment file `08_InfluxDB/.env`.
As you can see in the green box, the test was successful!

Afterwards, a dashboard can be created that retrieves data from
InfluxDB. Therefore, click on `+ -> Dashboard` and then build a
dashboard from scratch. However, it is also possible to import
a dashboard that was previously exported.
