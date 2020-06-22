import json
import time

import pytz
from datetime import datetime
from confluent_kafka import Consumer

# of the form 'mybroker1,mybroker2'
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC = "machine.out"
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
        'auto.offset.reset': 'latest'
    })
    kafka_consumer.subscribe([KAFKA_TOPIC])

    cnt = 0
    st0 = st_t = time.time()
    try:
        while True:
            msg = kafka_consumer.poll(0.1)

            # if there is no msg within a second, continue
            if msg is None:
                continue
            if msg.error():
                print("Consumer error: {}".format(msg.error()))
                continue
            try:
                record = json.loads(msg.value().decode('utf-8'))
                cnt += 1
                if VERBOSE:
                    print('Received message: {}'.format(json.dumps(record)))

            except json.decoder.JSONDecodeError as e:
                print("skipping record as there is a json.decoder.JSONDecodeError.")


    except KeyboardInterrupt:
        kafka_consumer.close()
        print("Graceful stopping.")

    print(f"Received {cnt} records within {time.time()-st0} s, that are {cnt/(time.time()-st0)} records/s.")
    # print(json.dumps({"data": list(result.get_points())}, indent=2))

