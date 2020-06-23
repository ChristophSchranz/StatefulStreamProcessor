#!/usr/bin/env python3
import json
import time
from confluent_kafka import Producer

# Note that Kafka produce publish around 20_000 S/s.
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092" # of the form 'mybroker1,mybroker2'
KAFKA_TOPIC = "machine.data"   # mqtt topic name to produce to
EVENT_FILE = "events.json"      # file of the records, not a json itself, but each row is
SAMPLE_RATE = 100_000             # sample rate in messages per second
READ_FIRST_N = None             # only read the first n lines of the file
VERBOSE = False


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


if __name__ == "__main__":
    st0 = st_t = time.time()
    interval = 1 / SAMPLE_RATE
    print("Starting the Simulator and publish the measurements via Apache Kafka.")

    # create a Kafka Producer
    kafka_producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})

    # open the file containing the events
    with open(EVENT_FILE) as f:
        events = f.readlines()

    i = 0
    try:
        # infinite loop to get a permanent stream to Kafka, which is faster than via MQTT
        while True:
            for line in events:
                if "actSpeed" not in line and "vaTorque" not in line and "vaLoad" not in line:
                    continue
                # Extract quantities from the line
                payload = json.loads(line.replace("\n", ""))
                quantities = list(set(payload.keys()).difference({'Thing', 'Timestamp', 'id'}))

                # forward each quantity separately to Kafka
                thing_id = payload["Thing"]
                timestamp = payload["Timestamp"]
                kafka_producer.poll(0)
                for quantity in quantities:
                    record = {"phenomenonTime": timestamp,
                              "quantity": quantity,
                              "thing": thing_id,
                              "result": payload[quantity]}

                    # produce a Kafka message, the delivery report callback, the key must be thing + quantity
                    kafka_producer.produce(KAFKA_TOPIC, json.dumps(record).encode('utf-8'),
                                           key=f"{thing_id}.{quantity}".encode('utf-8'), callback=delivery_report)

                # wait until the interval is exceeded
                while time.time() < st_t + interval:
                    time.sleep(0.01 * interval)
                st_t = time.time()
                time.sleep(0)

                i += 1
                # Read only the first n records of the event file
                if READ_FIRST_N:
                    if i >= READ_FIRST_N:
                        break
    except KeyboardInterrupt:
        kafka_producer.flush()
        print("Graceful stopped.")

    kafka_producer.flush()
    print(f"Finished in {(time.time() - st0) / i:.6g} s per publish. Wrote {i} records.")
