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
    events_t = list()

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
    n_r = 0
    n_s = 0
    for i in range(N):
        # decide based on the ingestion order which stream record is forwarded
        # store as dict of KafkaRecords and a flag whether it was already joined as older sibling
        if ingestionOrder[i] == "r":
            # receive the first record from the event stream
            if len(events_r) == 0:
                continue
            rec = events_r[0]
            stream_buffer.ingest_left(rec)  # instant emit
            n_r += 1
            events_r = events_r[1:]
        elif ingestionOrder[i] == "s":
            # receive the first record from the event stream
            if len(events_s) == 0:
                continue
            rec = events_s[0]
            stream_buffer.ingest_right(rec)
            n_s += 1
            events_s = events_s[1:]

    # print("\nRecords in buffer r:")
    # for rec in stream_buffer.buffer_left:
    #     print(rec)
    # print("Records in buffer s:")
    # for rec in stream_buffer.buffer_right:
    #     print(rec)
    # print("Merged records in buffer t:")
    buffer_t = stream_buffer.fetch_results()
    # for rec in buffer_t:
    #     print(rec)

    print(f"length of |event_t| = {len(events_t)}, |r| = {n_r}, |s| = {n_s}.")
    print(f"joined time-series with {buffer_t.length()} resulting joins in {time.time() - ts} s.")
    assert buffer_t.length() == 99


def test_five_five():
    ts = time.time()

    # create an instance of the StreamBuffer class
    stream_buffer = StreamBuffer(instant_emit=True, delta_time=200, left="r", buffer_results=True,
                                 verbose=True)

    # Test Settings:
    # Create Queues to store the input streams
    events_r = list()
    events_s = list()
    events_t = list()

    # Fill the input_stream with randomized
    N = 100
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
            if len(events_r) == 0:
                continue
            rec = events_r[0]
            stream_buffer.ingest_left(rec)  # instant emit
            n_r += 1
            events_r = events_r[1:]
        elif ingestionOrder[i] == "s":
            # receive the first record from the event stream
            if len(events_s) == 0:
                continue
            rec = events_s[0]
            stream_buffer.ingest_right(rec)
            n_s += 1
            events_s = events_s[1:]

    # print("\nRecords in buffer r:")
    # for rec in stream_buffer.buffer_left:
    #     print(rec)
    # print("Records in buffer s:")
    # for rec in stream_buffer.buffer_right:
    #     print(rec)
    # print("Merged records in buffer t:")
    buffer_t = stream_buffer.fetch_results()
    # for rec in buffer_t:
    #     print(rec)

    print(f"length of |event_t| = {len(events_t)}, |r| = {n_r}, |s| = {n_s}.")
    print(f"joined time-series with {buffer_t.length()} resulting joins in {time.time() - ts} s.")
    assert buffer_t.length() == 167


if __name__ == "__main__":
    # test ordered ingestion
    test_one_one()
    test_five_five()

    # test unordered ingestion


