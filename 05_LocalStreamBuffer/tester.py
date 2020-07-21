#!/usr/bin/env python3

# script to test the algorithm for the local stream buffering approach.
import sys
import time
import random

try:
    from .local_stream_buffer import Record, StreamBuffer
except ImportError:
    from local_stream_buffer import Record, StreamBuffer


def join_fct(record_left, record_right):
    """
    Blueprint for the join function, takes two records and merges them using the defined routine.
    :param record_left: Record 
        Record that is joined as left join partner
    :param record_right: Record 
        Record that is joined as right join partner
    :return: Record
        the resulting record from the join of both partners
    """
    record = Record(quantity="t",
                    result=record_left.get_result() * record_right.get_result(),
                    timestamp=(record_left.get_time() + record_right.get_time()) / 2)
    # here, the resulting record can be produced to e.g. Apache Kafka or a pipeline
    return record


def test_one_one():
    ts = time.time()

    # create an instance of the StreamBuffer class
    stream_buffer = StreamBuffer(instant_emit=True, delta_time=200, left="r", buffer_results=True,
                                 verbose=True)

    # Test Settings:
    # Create Queues to store the input streams
    events_r = list()
    events_s = list()

    # Fill the input_stream with randomized
    N = 100
    random.seed(0)
    eventOrder = ["r", "s"] * int(N / 2)
    start_time = 1600000000

    for i in range(len(eventOrder)):
        if eventOrder[i] == "r":
            events_r.append(Record(timestamp=i + start_time, quantity=eventOrder[i], result=random.random()))
        elif eventOrder[i] == "s":
            events_s.append(Record(timestamp=i + start_time, quantity=eventOrder[i], result=random.random()))

    ingestionOrder = ["r", "s"] * int(N/2)            # works
    n_r = n_s = 0
    for i in range(N):
        # decide based on the ingestion order which stream record is forwarded
        # store as dict of KafkaRecords and a flag whether it was already joined as older sibling
        if ingestionOrder[i] == "r":
            # receive the first record from the event stream
            stream_buffer.ingest_left(events_r[n_r])  # instant emit
            n_r += 1
        elif ingestionOrder[i] == "s":
            # receive the first record from the event stream
            stream_buffer.ingest_right(events_s[n_s])
            n_s += 1

    # print("\nRecords in buffer r:")
    # for rec in stream_buffer.buffer_left:
    #     print(rec)
    # print("Records in buffer s:")
    # for rec in stream_buffer.buffer_right:
    #     print(rec)
    # print("Merged records in buffer t:")
    events_t = stream_buffer.fetch_results()
    # for rec in events_t:
    #     print(rec)

    print(f"Join time-series with |r| = {n_r}, |s| = {n_s}.")
    print(f"joined {events_t.length()} tuples in {time.time() - ts} s.")
    assert events_t.length() == 99


def test_five_five():
    ts = time.time()

    # create an instance of the StreamBuffer class
    stream_buffer = StreamBuffer(instant_emit=True, delta_time=200, left="r", buffer_results=True,
                                 verbose=True)

    # Test Settings:
    # Create Queues to store the input streams
    events_r = list()
    events_s = list()

    # Fill the input_stream with randomized
    N = 20
    random.seed(0)
    eventOrder = ["r", "s"] * int(N / 2)
    eventOrder = (["r"] * 5 + ["s"] * 5) * int(N / 10)
    start_time = 1600000000

    for i in range(len(eventOrder)):
        if eventOrder[i] == "r":
            events_r.append(Record(timestamp=i + start_time, quantity=eventOrder[i], result=random.random()))
        elif eventOrder[i] == "s":
            events_s.append(Record(timestamp=i + start_time, quantity=eventOrder[i], result=random.random()))

    # ingestionOrder = ["r", "s"] * 5            # works
    ingestionOrder = (["r"] * 5 + ["s"] * 5) * N  # works
    n_r = 0
    n_s = 0
    for i in range(N):
        # decide based on the ingestion order which stream record is forwarded
        # store as dict of KafkaRecords and a flag whether it was already joined as older sibling
        if ingestionOrder[i] == "r":
            # receive the first record from the event stream
            stream_buffer.ingest_left(events_r[n_r])  # instant emit
            n_r += 1
        elif ingestionOrder[i] == "s":
            # receive the first record from the event stream
            stream_buffer.ingest_right(events_s[n_s])
            n_s += 1

    events_t = stream_buffer.fetch_results()

    print(f"Join time-series with |r| = {n_r}, |s| = {n_s}.")
    print(f"joined {events_t.length()} tuples in {time.time() - ts} s.")
    assert events_t.length() == 23


def test_five_five_many():

    # create an instance of the StreamBuffer class
    stream_buffer = StreamBuffer(instant_emit=True, delta_time=200, left="r", buffer_results=True,
                                 verbose=False)

    # Test Settings:
    # Create Queues to store the input streams
    events_r = list()
    events_s = list()

    # Fill the input_stream with randomized
    N = 100_000
    random.seed(0)
    eventOrder = (["r"] * 5 + ["s"] * 5) * int(N / 10)
    start_time = 1600000000

    for i in range(len(eventOrder)):
        if eventOrder[i] == "r":
            events_r.append(Record(timestamp=i + start_time, quantity=eventOrder[i], result=random.random()))
        elif eventOrder[i] == "s":
            events_s.append(Record(timestamp=i + start_time, quantity=eventOrder[i], result=random.random()))

    ingestionOrder = (["r"] * 5 + ["s"] * 5) * int(N/10)  # works
    n_r = 0
    n_s = 0
    ts = time.time()
    for i in range(N):
        # decide based on the ingestion order which stream record is forwarded
        # store as dict of KafkaRecords and a flag whether it was already joined as older sibling
        if ingestionOrder[i] == "r":
            # receive the first record from the event stream
            stream_buffer.ingest_left(events_r[n_r])  # instant emit
            n_r += 1
        elif ingestionOrder[i] == "s":
            # receive the first record from the event stream
            stream_buffer.ingest_right(events_s[n_s])
            n_s += 1

    events_t = stream_buffer.fetch_results()

    print(f"Join time-series with |r| = {n_r}, |s| = {n_s}.")
    print(f"joined {events_t.length()} tuples in {time.time() - ts} s.")
    print(f"that are {int(events_t.length()/(time.time() - ts))} joins per second.")
    assert events_t.length() == 179987
    assert time.time() - ts < 4


def test_unordered():
    # create an instance of the StreamBuffer class
    stream_buffer = StreamBuffer(instant_emit=True, delta_time=200, left="r", buffer_results=True,
                                 verbose=True)

    # Fill the input_stream with randomized
    random.seed(0)
    start_time = 1600000000

    # Test Settings:
    # Create Queues to store the input records
    events_r = list()
    for i in range(10):
        events_r.append(Record(timestamp=i + start_time, quantity="r", result=random.random()))

    ts = time.time()
    # first ingest all Records into R, then all into s
    for event in events_r:
        stream_buffer.ingest_left(event)  # instant emit

    print("Ingest Records into s.")
    stream_buffer.ingest_right(Record(timestamp=start_time - 0.5, quantity="s", result=random.random()))
    stream_buffer.ingest_right(Record(timestamp=start_time + 0.5, quantity="s", result=random.random()))
    stream_buffer.ingest_right(Record(timestamp=start_time + 5.5, quantity="s", result=random.random()))
    stream_buffer.ingest_right(Record(timestamp=start_time + 9.5, quantity="s", result=random.random()))

    events_t = stream_buffer.fetch_results()

    print(f"Join time-series with |r| = {len(events_r)}, |s| = {4}.")
    print(f"joined {events_t.length()} tuples in {time.time() - ts} s.")
    if time.time() - ts > 1e-3:
        print(f"that are {int(events_t.length()/(time.time() - ts))} joins per second.")
    assert events_t.length() == 20
    d = {'r.quantity': 'r', 'r.phenomenonTime': 1600000006, 'r.result': 0.7837985890347726,
         's.quantity': 's', 's.phenomenonTime': 1600000005.5, 's.result': 0.28183784439970383}
    assert d in events_t.items()


def rest_randomized():
    pass


if __name__ == "__main__":
    # test ordered ingestion
    test_one_one()
    test_five_five()

    # test unordered ingestion
    print("\n #############################")
    print("Testing a lot of cases")
    test_five_five_many()

    print("\n Testing unordered ingestion:")
    test_unordered()
    rest_randomized()
