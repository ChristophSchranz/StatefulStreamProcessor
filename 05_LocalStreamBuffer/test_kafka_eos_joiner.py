#!/usr/bin/env python3

"""This is a test-scriptfor exactly-once time-series joins using a local stream buffering algorithm with Apache Kafka.

It consumes from KAFKA_TOPIC_IN_1/2 the quantities 'vaTorque_C11' and 'actSpeed_C11', joins the time-series via the
LocalStreamBuffer method and produces the resulting 'vaPower_C11' to KAFKA_TOPIC_OUT.

A join rate of around 15000 time-series joins per second was reached with a exactly-once semantic for
the consume-join-produce using Apache Kafka.
"""
import sys
import time
import json
import math
import uuid

import pytest

import confluent_kafka.admin as kafka_admin
from confluent_kafka import Producer, Consumer, TopicPartition

try:
    from .local_stream_buffer import Record, StreamBuffer, record_from_dict
except (ModuleNotFoundError, ImportError):
    # noinspection PyUnresolvedReferences
    from local_stream_buffer import Record, StreamBuffer, record_from_dict

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"  # of the form 'mybroker1,mybroker2'
KAFKA_TOPIC_IN_0 = "test.machine.in.1"
KAFKA_TOPIC_IN_1 = "test.machine.in.2"
KAFKA_TOPIC_OUT = "test.machine.out"
EVENT_FILE = "../05_LocalStreamBuffer/test_events.json"  # file of the records, not a json itself, but each row is
QUANTITIES = ["actSpeed_C11", "vaTorque_C11"]
RES_QUANTITY = "vaPower_C11"
MAX_JOIN_CNT = 50  # maximum of 20000 rows
VERBOSE = True

if sys.platform.startswith("win"):
    pytest.skip("skipping unix-only tests", allow_module_level=True)

# Create a kafka producer and consumer instance and subscribe to the topics
print("Create Kafka instances.")

# create a Kafka admin client
k_admin_client = kafka_admin.AdminClient({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})

kafka_consumer = Consumer({
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': f"kafka-eof_{str(uuid.uuid4())}",
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,
    'enable.auto.offset.store': False,
    'enable.partition.eof': False
})

kafka_consumer.subscribe([KAFKA_TOPIC_IN_0, KAFKA_TOPIC_IN_1])
kafka_consumer.assign([TopicPartition(KAFKA_TOPIC_IN_0), TopicPartition(KAFKA_TOPIC_IN_1)])

# create a Kafka producer
kafka_producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
                           "transactional.id": 'eos-transactions1.py'})


class Counter:
    """
    A counter class that is used to count the number of joins
    """
    def __init__(self):
        self.cnt = 0

    def increment(self):
        self.cnt += 1

    def get(self):
        return self.cnt


cnt_out = Counter()


@pytest.mark.tryfirst()
def delivery_report(err, msg):
    """ Delivery callback for Kafka Produce. Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        print('Message delivery failed: {}'.format(err))
    else:
        if VERBOSE:
            # get the sent message using msg.value()
            print(f"Message '{msg.key().decode('utf-8')}'  \tdelivered to topic '{msg.topic()}' [{msg.partition()}].")


@pytest.mark.tryfirst()
def join_fct(record_left, record_right):
    record_dict = dict({"thing": record_left.get("thing"), "quantity": RES_QUANTITY,
                        "result": (2 * math.pi / 60) * record_left.get_result() * record_right.get_result(),
                        "timestamp": (record_left.get_time() + record_right.get_time()) / 2})
    # produce a Kafka message, the delivery report callback, the key must be thing + quantity
    kafka_producer.produce(KAFKA_TOPIC_OUT, json.dumps(record_dict).encode('utf-8'),
                           key=f"{record_dict.get('thing')}.{record_dict.get('quantity')}".encode('utf-8'),
                           callback=delivery_report)
    cnt_out.increment()

    # Send the consumer's position to transaction to commit them along with the transaction, committing both
    # input and outputs in the same transaction is what provides EOS.
    kafka_producer.send_offsets_to_transaction(
        kafka_consumer.position(kafka_consumer.assignment()),
        kafka_consumer.consumer_group_metadata())
    # Commit the transaction
    kafka_producer.commit_transaction()
    # Begin new transaction
    kafka_producer.begin_transaction()

    return record_from_dict(record_dict)


@pytest.mark.tryfirst()
def commit_fct(record_to_commit):
    # Test the commit: Uncomment commit() in order to consume and join always the same Records.
    # It is of importance that the
    rec = record_to_commit.data.get("record")
    # Commit message’s offset + 1
    kafka_consumer.commit(offsets=[TopicPartition(topic=rec.get("topic"),
                                                  partition=rec.get("partition"),
                                                  offset=rec.get("offset") + 1)])  # commit the next (n+1) offset


def test_topic_creation():
    """ This method recreates the test topics. """
    print("Recreate test topics.")
    topic_config = dict({"retention.ms": 3600000})  # store for one hour only
    res_dict = k_admin_client.create_topics(
        [kafka_admin.NewTopic(topic, num_partitions=1, replication_factor=1, config=topic_config)
         for topic in [KAFKA_TOPIC_IN_0, KAFKA_TOPIC_IN_1, KAFKA_TOPIC_OUT]])

    # Wait for each operation to finish.
    for topic, f in res_dict.items():
        try:
            f.result()  # The result itself is None
            print(f"Topic '{topic}' created")
        except Exception as e:
            print(f"Topic '{topic}' couldn't be created: {e}")
    k_admin_client.poll(0.1)  # small timeout for synchronizing

    topics = k_admin_client.list_topics(timeout=3.0).topics
    assert KAFKA_TOPIC_IN_0 in topics
    assert KAFKA_TOPIC_IN_1 in topics
    assert KAFKA_TOPIC_OUT in topics


def test_write_sample_data():
    """ Writes sample data containing the quantities of interest from the EVENT_FILE into the created Kafka topics. """
    print("\n####################  Write events into Kafka input topics ################################\n")

    # open the file containing the events, skip first 99000 rows to get the rows of interest
    with open(EVENT_FILE) as f:
        events = f.readlines()
        events = [event for event in events if QUANTITIES[0] in event or QUANTITIES[1] in event][:MAX_JOIN_CNT]

    producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})

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
            if quantity == QUANTITIES[0]:
                producer.produce(KAFKA_TOPIC_IN_0, json.dumps(rec).encode('utf-8'),
                                       key=f"{thing_id}.{quantity}".encode('utf-8'), callback=delivery_report)
            elif quantity == QUANTITIES[1]:
                producer.produce(KAFKA_TOPIC_IN_1, json.dumps(rec).encode('utf-8'),
                                       key=f"{thing_id}.{quantity}".encode('utf-8'), callback=delivery_report)
        time.sleep(0)
    producer.flush()
    print(f"Wrote {len(events)} records into {KAFKA_TOPIC_IN_0} and {KAFKA_TOPIC_IN_1}.")

    assert len(events) == MAX_JOIN_CNT


def test_commit_transaction(round_nr=1):

    print(f"\n################################ commit, transaction {round_nr} ######################################\n")

    if round_nr == 1:
        # Initialize producer transaction.
        kafka_producer.init_transactions()
        # Start producer transaction for round 1 only
        kafka_producer.begin_transaction()

    # commit_fct is empty and join_fct is with transactions
    stream_buffer = StreamBuffer(instant_emit=True, left="actSpeed_C11", right="vaTorque_C11",
                                 buffer_results=True, delta_time=1,
                                 verbose=VERBOSE, join_function=join_fct, commit_function=commit_fct)
    cnt_left = cnt_right = 0
    cnt_out.cnt = 0
    st0 = time.time()
    while True:
        msg = kafka_consumer.poll(0.1)
        # kafka_consumer.consume(num_messages=10, timeout=0.1) is faster, returns a list

        # if there is no msg within a second, continue
        if msg is None:
            if time.time() - st0 > 5 + MAX_JOIN_CNT / 10000:
                print("  Break as there won't come enough messages.")
                break
            continue
        elif msg.error():
            raise Exception("Consumer error: {}".format(msg.error()))
        elif st0 == 0:
            st0 = time.time()
            print("Start the count clock")

        record_json = json.loads(msg.value().decode('utf-8'))
        if VERBOSE:
            if record_json.get("quantity").endswith("_C11"):
                print(f"Received new record: {record_json}")

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
            print("Reached the maximal join count, graceful stopping.")
            break
        time.sleep(0)
    ts_stop = time.time()

    try:
        # commit processed message offsets to the transaction
        kafka_producer.send_offsets_to_transaction(
            kafka_consumer.position(kafka_consumer.assignment()),
            kafka_consumer.consumer_group_metadata())
        # commit transaction
        kafka_producer.commit_transaction()
    except:
        print("couldn't commit transaction.")
        pass

    events_out = stream_buffer.fetch_results()
    print(f"\nLengths: |{RES_QUANTITY}| = {len(events_out)}, "
          f"|{QUANTITIES[0]}| = {cnt_left}, |{QUANTITIES[1]}| = {cnt_right}.")
    print(f"Joined time-series {ts_stop - st0:.5g} s long, "
          f"that are {len(events_out) / (ts_stop - st0):.6g} joins per second.")

    if round_nr == 1:
        assert len(events_out) == 51
        # assert cnt_left == 162  # this values can be different
        # assert cnt_right == 30
        print(f"Result #0: {events_out[0]}")
        assert events_out[0].get_quantity() == "vaPower_C11"
        assert round(events_out[0].get_time() - 1554096460.415, 3) == 0
        assert round(events_out[0].get_result() - 86.71966370389097, 3) == 0
        assert round(events_out[-1].get_time() - 1554096505.38, 3) == 0
        assert round(events_out[-1].get_result() - 2010.8941815187334, 3) == 0
    else:
        assert len(events_out) == 0
        assert cnt_left + cnt_right > 0


def test_commit_transaction_2():
    test_commit_transaction(round_nr=2)


def test_topic_deletion():
    print("\n##################### test topic deletion ##########################")

    # delete test topics
    res_dict = k_admin_client.delete_topics([KAFKA_TOPIC_IN_0, KAFKA_TOPIC_IN_1, KAFKA_TOPIC_OUT])

    # Wait for each operation to finish.
    for topic, f in res_dict.items():
        try:
            f.result()  # The result itself is None
            print(f"Topic '{topic}' was deleted.")
        except Exception as e:
            print(f"Failed to delete topic '{topic}': {e}")
    k_admin_client.poll(3.0)  # small timeout for synchronizing

    topics = k_admin_client.list_topics(timeout=3.0).topics
    assert KAFKA_TOPIC_IN_0 not in topics
    assert KAFKA_TOPIC_IN_1 not in topics
    assert KAFKA_TOPIC_OUT not in topics


# to profile via cProfile, run it normally with a python interpreter
if __name__ == "__main__":
    import cProfile

    pr = cProfile.Profile()
    pr.enable()

    test_topic_creation()
    test_write_sample_data()
    test_commit_transaction()
    test_commit_transaction_2()

    kafka_consumer.close()
    test_topic_deletion()

    pr.disable()
    # after your program ends
    pr.print_stats(sort="tottime")
