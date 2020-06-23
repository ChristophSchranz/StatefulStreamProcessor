#!/usr/bin/env python3

# script to test the algorithm for the local stream buffering approach.
import sys
import time
import random
# import importlib
# LinkedList = importlib.import_module('05_LocalStreamBuffer.doublylinkedlist')


# Record is a record as streamed via Kafka, each record contains a set of fixed attributes
def record_from_dict(record_dict):
    """Creates a Record from a record dictionary

    :param json_dict: dict
        a dictionary storing all the necessary attributes
    """
    quantity = record_dict.pop("quantity", None)
    timestamp = record_dict.pop("timestamp", None)
    phenomenonTime = record_dict.pop("phenomenonTime", None)
    result = record_dict.pop("result", None)
    record = Record(quantity, timestamp=timestamp, phenomenonTime=phenomenonTime, result=result, kwargs=record_dict)
    return record


class Record:
    """Time-Series Records of Measurements or Events"""
    def __init__(self, quantity, timestamp=0, phenomenonTime=0, result=None, **kwargs):
        """
        :param quantity: string
            specifies the observed property by an unique string identifier
        :param timestamp: float, optional
            point in time in the unix format in seconds, only one of timestamp or phenomenonTime has to be set
        :param phenomenonTime: float, optional
            point in time in the unix format in seconds, only one of timestamp or phenomenonTime has to be set
        :param result: float, int, string, object, optional
            result value of the measurement of event, default = None
        :param kwargs:
            appends more arguments into class.meta
        """
        self.phenomenonTime = max(float(timestamp), float(timestamp))
        self.quantity = str(quantity)
        self.result = result
        self.metadata = kwargs

    def set_quantity(self, quantity):
        self.quantity = quantity

    def get_quantity(self):
        return self.quantity

    def get(self, attribute):
        return self.metadata.get(attribute)

    def get_time(self):
        return self.phenomenonTime

    def get_result(self):
        return self.result

    def get_metadata(self):
        return self.metadata

    def __str__(self):
        """to String method

        :return: str
            A readable representation of the record
        """
        tail = f", meta={self.metadata}}}" if self.metadata != dict() else "}}"
        return f"{{phenomenonTime={self.phenomenonTime}, quantity={self.quantity}, result={self.result}" \
               + tail


class StreamBuffer:
    """Stream Buffer class

    A class for deterministic, low-latency, high-throughput time-series joins of records within the continuous streams
    'r' (left) and 's' (right join partner).
    """
    def __init__(self, instant_emit=True, delta_time=sys.maxsize, left_quantity="r",
                 buffer_results=True, join_function=None, verbose=False):
        """

        :param instant_emit: boolean, default=True
            Emit (join and reduce) on each new record in the buffer
        :param delta_time: float, int, default=sys.maxsize
            Sets the maximum allowed time difference of two join candidates
        :param left_quantity: str, optional
            Sets the stream's quantity name that is joined as left record
        :param buffer_results: boolean, default=True
            Whether or not to buffer resulting join records
        :param join_function: function(record_r, record_s), default=None
            A function for merging the two join tuples, can be seen as projection in terms of relational algebra.
            The default is None, that inherits all attributes of both records, the function can look as follows:

            def join_fct(record_r, record_s):
                record = Record(quantity="t",
                                result=record_r.get_result() * record_s.get_result(),
                                timestamp=(record_r.get_time() + record_s.get_time()) / 2)
                # produce resulting record in Kafka or a pipeline
                return record
        """
        # unload the input and stream the messages based on the order into the buffer queues
        self.buffer_r = list()
        self.buffer_s = list()
        self.instant_emit = instant_emit
        self.buffer_out = list()
        self.delta_time = delta_time
        self.left_quantity = left_quantity
        self.buffer_results = buffer_results
        self.join_function = join_function
        self.verbose = verbose

    def get_buffer_r(self):
        """Get buffer r

        :return: the buffer r
        """
        return self.buffer_r

    def get_buffer_s(self):
        """Get buffer s

        :return: the buffer s
        """
        return self.buffer_s

    def fetch_results(self):
        """Fetch the buffer for the resulting join records. The buffer is emptied when fetched

        :return: a list of resulting join records
        """
        res = self.buffer_out
        self.buffer_out = list()
        return res

    def ingest_r(self, record):
        """
        Ingests a record of stream 'r' into the StreamBuffer instance. Emits instantly join partners if not disabled.
        :param record: object
            A Measurement or Event object.
        """
        self.buffer_r.append({"ts": record.get_time(), "record": record, "was_older": False})
        if self.instant_emit:
            self.buffer_r, self.buffer_s = self.emit(self.buffer_r, self.buffer_s)

    def ingest_s(self, record):
        """
        Ingests a record of stream 's' into the StreamBuffer instance. Emits instantly join partners if not disabled.
        :param record: object
            A Measurement or Event object.
        """
        self.buffer_s.append({"ts": record.get_time(), "record": record, "was_older": False})
        if self.instant_emit:
            self.buffer_s, self.buffer_r = self.emit(self.buffer_s, self.buffer_r)


    # Check for join pairs and commits. W.l.o.G., there is a new record in r.
    def emit(self, buffer_r, buffer_s):
        # Return if one of the Buffers is empty
        # print(f"\n -> emit <{len(buffer_r)}, {len(buffer_s)}>")
        if len(buffer_s) == 0 or len(buffer_r) == 0:
            return buffer_r, buffer_s

        # load the entries as tuples (record, was_sibling) from the buffer
        r_1 = buffer_r[-1]  # latest record in buffer r, this one is new.
        r_2 = None if len(buffer_r) < 2 else buffer_r[-2]  # second to the latest record

        s_idx = 0
        s_1 = buffer_s[s_idx]  # first (= oldest) record of s
        s_0 = buffer_s[s_idx + 1] if s_idx + 1 < len(buffer_s) else None  # subsequent record or s_1
        # Case 3: join s_1 with r_1, this is the case if r_1 was ingested, but the event order is s_1 < r_2 < r_1 < s_0
        if r_2 is not None:
            while s_0 is not None and s_1.get("record").get_time() < r_2.get("record").get_time():
                if r_1.get("record").get_time() < s_0.get("record").get_time():
                    # print("in part 1: ", end="")
                    self.join(r_1, s_1)
                    if not s_1.get("was_older"):
                        s_1["was_older"] = True
                s_idx += 1  # load next entry in s
                s_1 = buffer_s[s_idx] if s_idx < len(buffer_s) else None
                s_0 = buffer_s[s_idx + 1] if s_idx + 1 < len(buffer_s) else None  # subsequent record or s_1

        s_idx = 0
        s_1 = buffer_s[s_idx]  # first (= oldest) record of s
        s_0 = buffer_s[s_idx + 1] if s_idx + 1 < len(buffer_s) else None  # subsequent record or s_1
        # Case 1: join r_2 with records from s with event times between r_2 and r_1
        # if r_2 is not None:
        while s_1 is not None and s_1.get("record").get_time() < r_1.get("record").get_time():
            if r_2 is not None and r_2.get("record").get_time() < s_1.get("record").get_time():
                self.join(r_2, s_1)
                if not r_2.get("was_older"):
                    r_2["was_older"] = True
            s_idx += 1  # load next entry in s
            s_1 = buffer_s[s_idx] if s_idx < len(buffer_s) else None
            # s_2 = buffer_s[s_idx+1] if s_idx + 1 < len(buffer_s) else None

        s_idx = 0
        s_1 = buffer_s[s_idx]  # first (= oldest) record of s
        # Case 2: join r_1 with with records from s with event times between r_2 and r_1
        while s_1 is not None and s_1.get("record").get_time() <= r_1.get("record").get_time():
            if r_2 is None or r_2.get("record").get_time() < s_1.get("record").get_time():
                self.join(r_1, s_1)
                if not s_1.get("was_older"):
                    s_1["was_older"] = True
            s_idx += 1  # load next entry in s
            s_1 = buffer_s[s_idx] if s_idx < len(buffer_s) else None

        # try to commit & remove deprecated records based on a record criteria (cases, B and E)
        buffer_r = self.strip_buffers(buffer_r, buffer_s)
        buffer_s = self.strip_buffers(buffer_s, buffer_r)

        return buffer_r, buffer_s


    def strip_buffers(self, br, bs):
        if len(bs) == 0:
            return br
        s_1 = None if len(bs) < 1 else bs[-1]  # load the latest (newest) entry of s
        s_idx = 0
        s_0 = bs[s_idx]
        r_1 = br[0]
        r_2 = None if len(br) < 2 else br[1]
        while r_2 is not None and r_1.get("record").get_time() < r_2.get("record").get_time() <= s_1.get(
                "record").get_time():
            # commit r_2 in the data streaming framework
            # remove r_2 from the buffer r
            # some records r_1 are not joined so far as older sibling
            if not r_1.get("was_older"):
                # forward to the first s, with event time r_1 < s_0
                while s_0 is not None and s_0.get("record").get_time() <= r_1.get("record").get_time():
                    s_idx += 1
                    s_0 = bs[s_idx]
                self.join(r_1, s_0)
            # remove r_1 from buffer
            br = br[1:]
            r_1 = br[0]
            r_2 = None if len(br) < 2 else br[1]

        # remove old records in buffer_r if the delta time is not default
        if self.delta_time != sys.maxsize:
            s_0 = bs[-1]  # the current record in buffer_s
            r_1 = None if len(br) < 1 else br[0]  # the oldest record in buffer_r, remove candidate
            while r_1 is not None and r_1.get("record").get_time() < s_0.get("record").get_time() - self.delta_time:
                # print(f"  removing outdated record {r_1.get('record')}, leader: {s_0.get('record')}")
                # remove r_1 from buffer
                br = br[1:]
                r_1 = None if len(br) < 1 else br[0]  # the oldest record in buffer_r, remove candidate

        return br

    def join(self, u, v):
        """Joins two objects 'u' and 'v' if the time constraint holds and produces a resulting record.
        The join_function can be set arbitrary, see __init__()

        :param u: object that holds a record of 'r' or 's'
        :param v:object that holds a record of 'r' or 's'
        """
        # check the delta time constraint, don't join if not met
        if abs(u.get('record').get_time() - v.get('record').get_time()) <= self.delta_time:
            # set the leading quantity to r
            if v.get('record').get_quantity() == self.left_quantity:
                record_r = v.get('record')
                record_s = u.get('record')
            else:
                # select them from the normal order, default
                record_r = u.get('record')
                record_s = v.get('record')

            if self.join_function:
                # choose an arbitrary join function if set
                record = self.join_function(record_r=record_r, record_s=record_s)
            else:
                # standard join tuple with stream-prefix
                record = {"r.quantity": record_r.get_quantity(), "r.phenomenonTime": record_r.get_time(),
                          "r.result": record_r.get_result(), "s.quantity": record_s.get_quantity(),
                          "s.phenomenonTime": record_s.get_time(), "s.result": record_s.get_result()}
                if record_r.get_metadata() != dict():
                    record["r.metadata"] = record_r.get_metadata()
                if record_s.get_metadata() != dict():
                    record["s.metadata"] = record_s.get_metadata()

            # print join to stdout, append to resulting buffer
            if self.verbose:
                print(f"New join: {record}.")
            if self.buffer_results:
                self.buffer_out.append(record)


def join_fct(record_r, record_s):
    record = Record(quantity="t",
                    result=record_r.get_result() * record_s.get_result(),
                    timestamp=(record_r.get_time() + record_s.get_time()) / 2)
    # produce resulting record to Kafka or a pipeline
    return record


if __name__ == "__main__":
    ts = time.time()

    # create an instance of the StreamBuffer class
    stream_buffer = StreamBuffer(instant_emit=True, delta_time=2, left_quantity="r", buffer_results=True,
                                 join_function=join_fct)

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
            stream_buffer.ingest_r(rec)  # instant emit
            n_r += 1
            events_r = events_r[1:]
        elif ingestionOrder[i] == "s":
            # receive the first record from the event stream
            if len(events_s) == 0:
                continue
            rec = events_s[0]
            stream_buffer.ingest_s(rec)
            n_s += 1
            events_s = events_s[1:]

    print("\nRecords in buffer r:")
    for rec in stream_buffer.buffer_r:
        print(rec)
    print("Records in buffer s:")
    for rec in stream_buffer.buffer_s:
        print(rec)
    print("Merged records in buffer t:")
    for rec in stream_buffer.fetch_results():
        print(rec)

    print(f"length of |event_t| = {len(events_t)}, |r| = {n_r}, |s| = {n_s}.")
    print(f"joined time-series in {time.time() - ts} s.")
