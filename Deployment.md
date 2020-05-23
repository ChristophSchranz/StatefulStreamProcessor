# Deployment Nodes for the project


## 01 Simulator

Unzip the events in `01_Simulator` with the name `events.json`.
This file has 1402232 rows with batched values.

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

## 02 MQTT Broker

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
