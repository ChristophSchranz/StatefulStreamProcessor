import json
import pytz
from datetime import datetime
from confluent_kafka import Consumer
from influxdb import InfluxDBClient

# of the form 'mybroker1,mybroker2'
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPICS = ["machine.data", "machine.out"]
VERBOSE = True


def extract_time(timestamp):
    # recursively divide by 1000 until the time is in seconds and not in ms, µs or ns
    if timestamp >= 1e11:
        timestamp /= 1000
        return extract_time(timestamp)
    return datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.UTC).isoformat()


if __name__ == "__main__":
    # Create the kafka consumer instance and subscribe to the topics
    kafka_consumer = Consumer({
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': 'db-connector',
        'auto.offset.reset': 'earliest'
    })
    kafka_consumer.subscribe(KAFKA_TOPICS)

    # create InfluxDB Connector and create database if not already done
    client = InfluxDBClient('localhost', 8086, 'root', 'root', 'machinedata')
    client.create_database('machinedata')

    try:
        while True:
            msg = kafka_consumer.poll(1.0)

            # no msg within a second, continue
            if msg is None:
                continue
            if msg.error():
                print("Consumer error: {}".format(msg.error()))
                continue

            record = json.loads(msg.value().decode('utf-8'))
            print('Received message: {}'.format(json.dumps(record)))

            # all tags and the time create together the key and must be unique
            row = [{
                "measurement": "machinedata",
                "tags": {
                    "thing": record["thing"],
                    "quantity": record["quantity"]
                },
                "time": extract_time(record["phenomenonTime"]),
                "fields": {
                    "result": record["result"]
                }
            }]
            client.write_points(row)
    except KeyboardInterrupt:
        kafka_consumer.close()
        print("Graceful stopping.")

    result = client.query("select count(*) from machinedata;")
    print(json.dumps({"data": list(result.get_points())}, indent=2))

    # uncomment the line below to clear all data from machine data
    # client.drop_database("machinedata")
