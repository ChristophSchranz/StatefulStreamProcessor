#!/usr/bin/env python3

"""A script to test the algorithm for the local stream buffering approach with Apache Kafka as Stream Delivery Platform

It consumes from KAFKA_TOPIC_FROM the quantities 'vaTorque_C11' and 'vaSpeed_C11', joins the time-series via the
 LocalStreamBuffer method and produces the resulting 'vaPower_C11' to KAFKA_TOPIC_TO.

The performance was tested to be around 15000 time-series joins per second with usage of Apache Kafka.
"""

import json
import math
import sys
import time

from confluent_kafka import Producer, Consumer, TopicPartition
import confluent_kafka.admin as kafka_admin

try:
    from .local_stream_buffer import Record, StreamBuffer, record_from_dict
except (ModuleNotFoundError, ImportError):
    # noinspection PyUnresolvedReferences
    from local_stream_buffer import Record, StreamBuffer, record_from_dict

# of the form 'mybroker1,mybroker2'
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC_IN_0 = "test.machine.in.1"
KAFKA_TOPIC_IN_1 = "test.machine.in.2"
KAFKA_TOPIC_OUT = "test.machine.out"
EVENT_FILE = "../01_Simulator/events.json"  # file of the records, not a json itself, but each row is
QUANTITIES = ["actSpeed_C11", "vaTorque_C11"]
MAX_JOIN_CNT = 2000  # None or a integer
VERBOSE = False

# create a Kafka instances
k_admin_client = kafka_admin.AdminClient({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})
kafka_producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})


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
    kafka_producer.produce(KAFKA_TOPIC_OUT, json.dumps(record_dict).encode('utf-8'),
                           key=f"{record_dict.get('thing')}.{record_dict.get('quantity')}".encode('utf-8'),
                           callback=delivery_report)
    cnt_out.increment()

    # # Send the consumer's position to transaction to commit
    # # them along with the transaction, committing both
    # # input and outputs in the same transaction is what provides EOS.
    # kafka_producer.send_offsets_to_transaction(
    #     kafka_consumer.position(kafka_consumer.assignment()),
    #     kafka_consumer.consumer_group_metadata())
    # # Commit the transaction
    # kafka_producer.commit_transaction()
    # # Begin new transaction
    # kafka_producer.begin_transaction()

    return record_from_dict(record_dict)


def commit_fct(record_to_commit):
    # Test the commit: Uncomment commit() in order to consume and join always the same Records.
    # It is of importance that the
    rec = record_to_commit.data.get("record")
    # Commits message’s offset+1
    kafka_consumer.commit(offsets=[TopicPartition(topic=rec.get("topic"),
                                                  partition=rec.get("partition"),
                                                  offset=rec.get("offset") + 1)])  # commit the next (n+1) offset


def write_sample_data():
    print("Fill the Kafka topics with sample data.")

    # open the file containing the events, skip first 99000 rows to get the rows of interest
    with open(EVENT_FILE) as f:
        events = f.readlines()[99000:]
        events = [event for event in events if QUANTITIES[0] in event or QUANTITIES[1] in event][:1000]

    for event in events:

        # Extract quantities from the line
        payload = json.loads(event.replace("\n", ""))
        quantities = list(set(payload.keys()).difference({'Thing', 'Timestamp', 'id'}))

        # forward each quantity separately to Kafka
        thing_id = payload["Thing"]
        timestamp = payload["Timestamp"]
        kafka_producer.poll(0)
        for quantity in quantities:
            rec = {"phenomenonTime": timestamp,
                   "quantity": quantity,
                   "thing": thing_id,
                   "result": payload[quantity]}
            # produce a Kafka message, the delivery report callback, the key must be thing + quantity
            if quantity.startswith(QUANTITIES[0]):
                kafka_producer.produce(KAFKA_TOPIC_IN_0, json.dumps(rec).encode('utf-8'),
                                       key=f"{thing_id}.{quantity}".encode('utf-8'), callback=delivery_report)
            elif quantity.startswith(QUANTITIES[1]):
                kafka_producer.produce(KAFKA_TOPIC_IN_1, json.dumps(rec).encode('utf-8'),
                                       key=f"{thing_id}.{quantity}".encode('utf-8'), callback=delivery_report)
        time.sleep(0)
    kafka_producer.flush()
    print(f"Wrote {len(events)} records into {KAFKA_TOPIC_IN_0} and {KAFKA_TOPIC_IN_1}.")


def recreate_kafka_topics():
    print("Recreate test topics.")
    k_admin_client.delete_topics([KAFKA_TOPIC_IN_0, KAFKA_TOPIC_IN_1, KAFKA_TOPIC_OUT])
    k_admin_client.poll(2.0)
    topic_config = dict({"retention.ms": 3600000})
    k_admin_client.create_topics([
        kafka_admin.NewTopic(KAFKA_TOPIC_IN_0, num_partitions=3, replication_factor=1, config=topic_config),
        kafka_admin.NewTopic(KAFKA_TOPIC_IN_1, num_partitions=3, replication_factor=1, config=topic_config),
        kafka_admin.NewTopic(KAFKA_TOPIC_OUT, num_partitions=3, replication_factor=1, config=topic_config)])
    k_admin_client.poll(1.0)


if __name__ == "__main__":
    # Recreate test topics
    recreate_kafka_topics()

    # Write events into Kafka input topics
    write_sample_data()

    print("Create a StreamBuffer instance.")
    stream_buffer = StreamBuffer(instant_emit=True, left="actSpeed_C11", right="vaTorque_C11", buffer_results=True,
                                 verbose=VERBOSE, join_function=join_fct, commit_function=commit_fct)

    # Create a kafka producer and consumer instance and subscribe to the topics
    print("Assign to Kafka topics.")
    kafka_consumer = Consumer({
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': "kafka-eof",
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,
        'enable.auto.offset.store': False
    })
    kafka_consumer.subscribe([KAFKA_TOPIC_IN_0, KAFKA_TOPIC_IN_1])
    kafka_consumer.assign([TopicPartition(KAFKA_TOPIC_IN_0), TopicPartition(KAFKA_TOPIC_IN_1)])

    # while True:
    #     msg = kafka_consumer.poll(0.1)
    #     # if there is no msg within a second, continue
    #     if msg is None:
    #         continue
    #     if msg.error():
    #         print("Consumer error: {}".format(msg.error()))
    #         continue
    #
    #     record_json = json.loads(msg.value().decode('utf-8'))
    #     print(f"Received new record: {record_json}")
    #     if record_json.get("phenomenonTime") == 1554096487396:
    #         kafka_consumer.commit(msg, asynchronous=True)
    #
    #     time.sleep(0.1)

    # create a Kafka producer
    kafka_producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})
    # print("debug15")
    # # Initialize producer transaction.
    # kafka_producer.init_transactions()
    # # Start producer transaction.
    # kafka_producer.begin_transaction()
    # print("debug20")

    cnt_left = 0
    cnt_right = 0
    cnt_out = Counter()
    st0 = ts_stop = None
    while True:
        msg = kafka_consumer.poll(0.1)

        # if there is no msg within a second, continue
        if msg is None:
            continue
        if msg.error():
            raise Exception("Consumer error: {}".format(msg.error()))

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
            result=record_json.get("result"),
            topic=msg.topic(), partition=msg.partition(), offset=msg.offset())

        # ingest the record into the StreamBuffer instance, instant emit
        if msg.topic() == KAFKA_TOPIC_IN_0:  # "actSpeed_C11":
            stream_buffer.ingest_left(record)  # with instant emit
            cnt_left += 1
        elif msg.topic() == KAFKA_TOPIC_IN_1:  # "vaTorque_C11":
            stream_buffer.ingest_right(record)
            cnt_right += 1

        if MAX_JOIN_CNT is not None and cnt_out.get() >= MAX_JOIN_CNT:
            ts_stop = time.time()
            print("Reached the maximal join count, graceful stopping.")
            break

    # # commit processed message offsets to the transaction
    # kafka_producer.send_offsets_to_transaction(
    #     kafka_consumer.position(kafka_consumer.assignment()),
    #     kafka_consumer.consumer_group_metadata())
    # # commit transaction
    # kafka_producer.commit_transaction()
    # Leave group and commit offsets
    kafka_consumer.close()

    print(f"\nLength of |resulting_events| = {cnt_out.get()}, |lefts| = {cnt_left}, |rights| = {cnt_right}.")
    print(f"Joined time-series {ts_stop - st0:.2f} s long, "
          f"that are {cnt_out.get() / (ts_stop - st0):.6g} joins per second.")

    # delete topics
    k_admin_client.delete_topics([KAFKA_TOPIC_IN_0, KAFKA_TOPIC_IN_1, KAFKA_TOPIC_OUT])
    k_admin_client.poll(3.0)
