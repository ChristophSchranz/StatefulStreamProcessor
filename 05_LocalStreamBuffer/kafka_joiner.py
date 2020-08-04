#!/usr/bin/env python3

"""A script to test the algorithm for the local stream buffering approach with Apache Kafka as Stream Delivery Platform

It consumes from KAFKA_TOPIC_FROM the quantities 'vaTorque_C11' and 'vaSpeed_C11', joins the time-series via the
 LocalStreamBuffer method and produces the resulting 'vaPower_C11' to KAFKA_TOPIC_TO.

The performance was tested to be around 15000 time-series joins per second with usage of Apache Kafka.
"""
import json
import math
import time
import uuid

from confluent_kafka import Producer, Consumer

try:
    from .local_stream_buffer import Record, StreamBuffer, record_from_dict
except (ModuleNotFoundError, ImportError):
    # noinspection PyUnresolvedReferences
    from local_stream_buffer import Record, StreamBuffer, record_from_dict

# of the form 'mybroker1,mybroker2'
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC_FROM = "machine.data"
KAFKA_TOPIC_TO = "machine.out"
MAX_JOIN_CNT = 1000  # None or a integer
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
    record_dict = dict({"thing": record_left.get("thing"), "quantity": "vaPower_C11",
                        "result": (2 * math.pi / 60) * record_left.get_result() * record_right.get_result(),
                        "timestamp": (record_left.get_time() + record_right.get_time()) / 2})
    # produce a Kafka message, the delivery report callback, the key must be thing + quantity
    kafka_producer.produce(KAFKA_TOPIC_TO, json.dumps(record_dict).encode('utf-8'),
                           key=f"{record_dict.get('thing')}.{record_dict.get('quantity')}".encode('utf-8'),
                           callback=delivery_report)
    cnt_out.increment()
    return record_from_dict(record_dict)


if __name__ == "__main__":
    # Create a kafka producer and consumer instance and subscribe to the topics
    kafka_consumer = Consumer({
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': str(uuid.uuid1()),  # should be unique in order to retrieve multiple messages
        'auto.offset.reset': 'earliest'  # should be earliest in order retrieve the Records from beginning
    })
    kafka_consumer.subscribe([KAFKA_TOPIC_FROM])

    # create a Kafka Producer
    kafka_producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})

    # create an instance of the StreamBuffer class
    stream_buffer = StreamBuffer(instant_emit=True, left="actSpeed_C11", right="vaTorque_C11", buffer_results=True,
                                 verbose=VERBOSE, join_function=join_fct)
    print("Created a StreamBuffer instance. starting the time-series join now.")

    cnt_left = 0
    cnt_right = 0
    cnt_out = Counter()
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

            record_json = json.loads(msg.value().decode('utf-8'))
            if VERBOSE:
                if record_json.get("quantity").endswith("_C11"):
                    print(f"Received new record: {record_json}")
            if st0 is None:
                print("Start the count clock")
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

            if MAX_JOIN_CNT is not None and cnt_out.get() >= MAX_JOIN_CNT:
                ts_stop = time.time()
                print("reached the maximal join count, graceful stopping.")
                break
    except KeyboardInterrupt:
        print("\nGraceful stopping.")
    finally:
        # Leave group and commit offsets
        kafka_consumer.close()

    print(f"\nLength of |resulting_events| = {cnt_out.get()}, |lefts| = {cnt_left}, |rights| = {cnt_right}.")
    print(f"Joined time-series {ts_stop - st0:.2f} s long, "
          f"that are {cnt_out.get() / (ts_stop - st0):.6g} joins per second.")
