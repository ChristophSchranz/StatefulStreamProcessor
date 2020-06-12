#!/usr/bin/env python3
# script to test the algorithm for the local stream buffering approach.

import numpy as np
from queue import Queue
# import importlib
# LinkedList = importlib.import_module('05_LocalStreamBuffer.doublylinkedlist')


# Record is a record as streamed via Kafka, each record contains a set of fixed attributes
class Record:
    def __init__(self, time, result=None, quantity=None):
        self.phenomenonTime = float(time)
        self.quantity = quantity
        self.result = np.random.random() if result is None else result

    def set_quantity(self, quantity):
        self.quantity = quantity

    def get_quantity(self):
        return self.quantity

    def get_time(self):
        return self.phenomenonTime

    def get_result(self):
        return self.result

    def __str__(self):
        return f"KafkaRecord: {{phenomenonTime={self.phenomenonTime}, quantity={self.quantity}, result={self.result}"


# Check for join pairs and commits. W.l.o.G., there is a new record in r.
def emit(buffer_r, buffer_s, leading=None):
    # Return if one of the Buffers is empty
    print(f"\n -> emit <{len(buffer_r)}, {len(buffer_s)}>")
    if len(buffer_s) == 0 or len(buffer_r) == 0:
        return buffer_r, buffer_s

    # load the entries as tuples (record, was_sibling) from the buffer
    r_1 = buffer_r[-1]  # latest record in buffer r, this one is new.
    r_2 = None if len(buffer_r) < 2 else buffer_r[-2]  # second to the latest record

    s_idx = 0
    s_1 = buffer_s[s_idx]  # first (= oldest) record of s
    s_0 = buffer_s[s_idx+1] if s_idx+1 < len(buffer_s) else None  # subsequent record or s_1
    # Case 3: join s_1 with r_1, this is the case if r_1 was ingested, but the event order is s_1 < r_2 < r_1 < s_0
    if r_2 is not None:
        while s_0 is not None and s_1.get("record").get_time() < r_2.get("record").get_time():
            if r_1.get("record").get_time() < s_0.get("record").get_time():
                print("in part 1: ", end="")
                join(r_1, s_1, leading)
                if not s_1.get("was_older"):
                    s_1["was_older"] = True
            s_idx += 1              # load next entry in s
            s_1 = buffer_s[s_idx] if s_idx < len(buffer_s) else None
            s_0 = buffer_s[s_idx+1] if s_idx+1 < len(buffer_s) else None  # subsequent record or s_1

    s_idx = 0
    s_1 = buffer_s[s_idx]  # first (= oldest) record of s
    s_0 = buffer_s[s_idx+1] if s_idx+1 < len(buffer_s) else None  # subsequent record or s_1
    # Case 1: join r_2 with records from s with event times between r_2 and r_1
    # if r_2 is not None:
    while s_1 is not None and s_1.get("record").get_time() < r_1.get("record").get_time():
        if r_2 is not None and r_2.get("record").get_time() < s_1.get("record").get_time():
            join(r_2, s_1, leading)
            if not r_2.get("was_older"):
                r_2["was_older"] = True
        s_idx += 1              # load next entry in s
        s_1 = buffer_s[s_idx] if s_idx < len(buffer_s) else None
        # s_2 = buffer_s[s_idx+1] if s_idx + 1 < len(buffer_s) else None

    s_idx = 0
    s_1 = buffer_s[s_idx]  # first (= oldest) record of s
    # Case 2: join r_1 with with records from s with event times between r_2 and r_1
    while s_1 is not None and s_1.get("record").get_time() <= r_1.get("record").get_time():
        if r_2 is None or r_2.get("record").get_time() < s_1.get("record").get_time():
            join(r_1, s_1, leading)
            if not s_1.get("was_older"):
                s_1["was_older"] = True
        s_idx += 1              # load next entry in s
        s_1 = buffer_s[s_idx] if s_idx < len(buffer_s) else None

    # try to commit & remove deprecated records based on a record criteria (cases, B and E)
    buffer_r = strip_buffers(buffer_r, buffer_s)
    buffer_s = strip_buffers(buffer_s, buffer_r)

    return buffer_r, buffer_s


def strip_buffers(buffer_r, buffer_s):
    # if len(buffer_s) == 0:
    #     return buffer_r
    s_1 = None if len(buffer_s) < 1 else buffer_s[-1]  # load the latest (newest) entry of s
    s_idx = 0
    s_0 = buffer_s[s_idx]
    r_1 = buffer_r[0]
    r_2 = None if len(buffer_r) < 2 else buffer_r[1]
    while r_2 is not None and r_1.get("record").get_time() < r_2.get("record").get_time() <= s_1.get("record").get_time():
        # commit r_2 in the data streaming framework
        # remove r_2 from the buffer r
        # some records r_1 are not joined so far as older sibling
        if not r_1.get("was_older"):
            # forward to the first s, with event time r_1 < s_0
            while s_0 is not None and s_0.get("record").get_time() <= r_1.get("record").get_time():
                s_idx += 1
                s_0 = buffer_s[s_idx]
            join(r_1, s_0, leading)
        # remove r_1 from buffer
        buffer_r = buffer_r[1:]
        r_1 = buffer_r[0]
        r_2 = None if len(buffer_r) < 2 else buffer_r[1]

    return buffer_r


# Joins two tuples if not already done and produces the pair.
def join(r, s, leading=None):
    # print the leading quantity at first
    if r.get('record').get_quantity() == leading:
        print(f"New join: ({r.get('record')}, {s.get('record')})")
    else:
        print(f"New join: ({s.get('record')}, {r.get('record')})")

    # prod.produce((r, s))
    record = Record(quantity="t", result=r.get('record').get_result() * s.get('record').get_result(),
                    time=(r.get('record').get_time() + s.get('record').get_time()) / 2)
    events_t.append(record)


if __name__ == "__main__":
    # Create Queues to store the input streams
    events_r = list()
    events_s = list()
    events_t = list()

    # Fill the input_stream with randomized
    np.random.seed(0)
    eventOrder = ["r", "s"] * 10
    eventOrder = (["r"] * 3 + ["s"] * 3) * 5
    start_time = 1600000000
    for i in range(len(eventOrder)):
        if eventOrder[i] == "r":
            events_r.append(Record(time=i + start_time, quantity=eventOrder[i]))
        elif eventOrder[i] == "s":
            events_s.append(Record(time=i + start_time, quantity=eventOrder[i]))

    # unload the input and stream the messages based on the order into the buffer queues
    buffer_r = list()
    buffer_s = list()
    leading = None # "r"
    # ingestionOrder = ["r", "s"] * 5            # works
    ingestionOrder = ["r"] * 10 + ["s"] * 10      # works not fully
    for i in range(len(ingestionOrder)):
        # decide based on the ingestion order which stream record is forwarded
        # store as dict of KafkaRecords and a flag whether it was already joined as older sibling
        if ingestionOrder[i] == "r":
            # receive the first record from the event stream
            if len(events_r) == 0:
                continue
            record = events_r[0]
            buffer_r.append({"ts": record.get_time(), "record": record, "was_older": False})
            events_r = events_r[1:]
            buffer_r, buffer_s = emit(buffer_r, buffer_s, leading=leading)
        elif ingestionOrder[i] == "s":
            # receive the first record from the event stream
            if len(events_s) == 0:
                continue
            record = events_s[0]
            buffer_s.append({"ts": record.get_time(), "record": record, "was_older": False})
            events_s = events_s[1:]
            buffer_s, buffer_r = emit(buffer_s, buffer_r, leading=leading)

        # if delay_timeout is not Null:
        #    time_commit()
        # test methods to time join the buffer's records

    print("\nRecords in buffer r:")
    for rec in buffer_r:
        print(rec)
    print("Records in buffer s:")
    for rec in buffer_s:
        print(rec)
    print("Merged records in buffer t:")
    for rec in events_t:
        print(rec)
