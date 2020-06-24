#!/usr/bin/env python3

# script to test the algorithm for the local stream buffering approach.
import json
import math
import time
from confluent_kafka import Producer, Consumer

try:
    from .local_stream_buffer import Record, StreamBuffer, record_from_dict
except ModuleNotFoundError:
    # noinspection PyUnresolvedReferences
    from local_stream_buffer import Record, StreamBuffer, record_from_dict

# of the form 'mybroker1,mybroker2'
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC_FROM = "machine.data"
KAFKA_TOPIC_TO = "machine.out"
VERBOSE = False


class Counter:
    def __init__(self):
        self.cnt = 0

    def increment(self):
        self.cnt += 1

    def get(self):
        return self.cnt


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


# define customized function for join
def join_fct(record_r, record_s):
    # record = Record(thing=record_r.get("thing"), quantity="t",
    #                 result=record_r.get_result() * record_s.get_result(),
    #                 timestamp=(record_r.get_time() + record_s.get_time()) / 2)
    record = dict({"thing": record_r.get("thing"), "quantity": "t",
                   "result": (2 * math.pi / 60) * record_r.get_result() * record_s.get_result(),
                   "timestamp": (record_r.get_time() + record_s.get_time()) / 2})
    # produce a Kafka message, the delivery report callback, the key must be thing + quantity
    kafka_producer.produce(KAFKA_TOPIC_TO, json.dumps(record).encode('utf-8'),
                           key=f"{record.get('thing')}.{record.get('quantity')}".encode('utf-8'),
                           callback=delivery_report)
    cnt_t.increment()
    return record_from_dict(record)


if __name__ == "__main__":
    # Create a kafka producer and consumer instance and subscribe to the topics
    kafka_consumer = Consumer({
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': 'db-connector',
        'auto.offset.reset': 'latest'
    })
    kafka_consumer.subscribe([KAFKA_TOPIC_FROM])

    # create a Kafka Producer
    kafka_producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})

    # create an instance of the StreamBuffer class
    stream_buffer = StreamBuffer(instant_emit=True, left_quantity="r", buffer_results=False,
                                 join_function=join_fct, verbose=False)

    cnt_r = 0
    cnt_s = 0
    cnt_t = Counter()
    st0 = None
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
                record_json = json.loads(msg.value().decode('utf-8'))
                if VERBOSE:
                    print(f"Received new record: {record_json}")
                if st0 is None:
                    print("Start count clock")
                    st0 = time.time()

                # create a Record from the json
                record = Record(
                    thing=record_json.get("thing"),
                    quantity=record_json.get("quantity"),
                    timestamp=record_json.get("phenomenonTime"),
                    result=record_json.get("result"))

                # ingest the record into the StreamBuffer instance, instant emit
                if "Torque" in record_json.get("quantity"):
                    stream_buffer.ingest_r(record)  # instant emit
                    cnt_r += 1
                elif "Load" in record_json.get("quantity"):
                    stream_buffer.ingest_s(record)
                    cnt_s += 1
            except json.decoder.JSONDecodeError as e:
                print("skipping record as there is a json.decoder.JSONDecodeError.")
        pass
    except KeyboardInterrupt:
        kafka_consumer.close()
        print("\nGraceful stopping.")

    print(
        f"\nReceived {cnt_r + cnt_s} records within {time.time() - st0:.3f} s, that are {(cnt_r + cnt_s) / (time.time() - st0):.8g} records/s.")
    print(f"Joined time-series {time.time() - st0:.2f} s long, "
          f"that are {cnt_t.get() / (time.time() - st0):.8g} records/s.")
    print(f"length of |event_t| = {cnt_t.get()}, |r| = {cnt_s}, |s| = {cnt_s}.")
