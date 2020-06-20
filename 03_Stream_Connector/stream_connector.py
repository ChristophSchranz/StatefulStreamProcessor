#!/usr/bin/env python3
import json

import paho.mqtt.client as mqtt
from confluent_kafka import Producer

MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_TOPIC_NAME = "machine/states"
# of the form 'mybroker1,mybroker2'
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC = "machine.data"
VERBOSE = True


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected to the MQTT broker with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(MQTT_TOPIC_NAME)


# Delivery callback for Kafka Produce
def delivery_report(err, msg):
    """ Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        print('Message delivery failed: {}'.format(err))
    else:
        if VERBOSE:
            # get the sent message using msg.value()
            print(f"Message '{msg.key().decode('utf-8')}'  \tdelivered to topic '{msg.topic()}' [{msg.partition()}].")


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    # extract the payload from the mqtt message
    payload = json.loads(msg.payload)
    quantities = list(set(payload.keys()).difference({'Thing', 'Timestamp', 'id'}))

    # forward each quantity separately
    thing_id = payload["Thing"]
    timestamp = payload["Timestamp"]
    id = payload["id"]
    kafka_producer.poll(0)
    for quantity in quantities:
        record = {"thing": thing_id,
                  "quantity": quantity,
                  "phenomenonTime": timestamp,
                  "result": payload[quantity]}

        # Asynchronously produce a Kafka message, the delivery report callback, the key must be thing + quantity
        kafka_producer.produce(KAFKA_TOPIC, json.dumps(record).encode('utf-8'),
                               key=f"{thing_id}.{quantity}".encode('utf-8'), callback=delivery_report)
    kafka_producer.flush()


# create the MQTT client and set the on_connect and on_message methods
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)

# create a Kafka Producer
kafka_producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})

# start the consumption of MQTT messages in an infinite loop
client.loop_forever()
