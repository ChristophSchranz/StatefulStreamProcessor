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
VERBOSE = True


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
def join_fct(record_left, record_right):
    # record = Record(thing=record_r.get("thing"), quantity="t",
    #                 result=record_r.get_result() * record_s.get_result(),
    #                 timestamp=(record_r.get_time() + record_s.get_time()) / 2)
    record_dict = dict({"thing": record_left.get("thing"), "quantity": "vaPower_C11",
                        "result": (2 * math.pi / 60) * record_left.get_result() * record_right.get_result(),
                        "timestamp": (record_left.get_time() + record_right.get_time()) / 2})
    # produce a Kafka message, the delivery report callback, the key must be thing + quantity
    kafka_producer.produce(KAFKA_TOPIC_TO, json.dumps(record_dict).encode('utf-8'),
                           key=f"{record_dict.get('thing')}.{record_dict.get('quantity')}".encode('utf-8'),
                           callback=delivery_report)
    result_counter.increment()
    return record_from_dict(record_dict)


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
    stream_buffer = StreamBuffer(instant_emit=True, left="actSpeed_C11", right="vaTorque_C11", buffer_results=False,
                                 join_function=join_fct, verbose=VERBOSE)

    cnt_left = 0
    cnt_right = 0
    result_counter = Counter()
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
                if record_json.get("quantity") == "actSpeed_C11":
                    stream_buffer.ingest_left(record)  # instant emit
                    cnt_left += 1
                elif record_json.get("quantity") == "vaTorque_C11":
                    stream_buffer.ingest_right(record)
                    cnt_right += 1
            except json.decoder.JSONDecodeError as e:
                print("skipping record as there is a json.decoder.JSONDecodeError.")
        pass
    except KeyboardInterrupt:
        kafka_consumer.close()
        print("\nGraceful stopping.")

    print(
        f"\nReceived {cnt_left + cnt_right} records within {time.time() - st0:.3f} s, that are "
        f"{(cnt_left + cnt_right) / (time.time() - st0):.8g} records/s.")
    print(f"Joined time-series {time.time() - st0:.2f} s long, "
          f"that are {result_counter.get() / (time.time() - st0):.8g} records/s.")
    print(f"Length of |resulting_events| = {result_counter.get()}, |lefts| = {cnt_left}, |rights| = {cnt_right}.")
    print(f"Lengths of Buffers: |Br| = {len(stream_buffer.get_left_buffer())},"
          f" |Bs| = {len(stream_buffer.get_right_buffer())}")
