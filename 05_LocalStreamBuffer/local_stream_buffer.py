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

    :param record_dict: dict
        a dictionary storing all the necessary attributes
    """
    quantity = record_dict.pop("quantity", None)
    timestamp = record_dict.pop("timestamp", None)
    phenomenon_time = record_dict.pop("phenomenonTime", None)
    result = record_dict.pop("result", None)
    record = Record(quantity, timestamp=timestamp, phenomenon_time=phenomenon_time, result=result, kwargs=record_dict)
    return record


class Record:
    """Time-Series Records of Measurements or Events"""

    def __init__(self, quantity, timestamp=None, phenomenon_time=None, result=None, **kwargs):
        """
        :param quantity: string
            specifies the observed property by an unique string identifier
        :param timestamp: int, float, str (iso-8601), optional
            point in time in the unix format in seconds (preferred, others will be parsed),
            only one of timestamp or phenomenonTime has to be set
        :param phenomenon_time:  int, float, str (iso-8601), optional
            point in time in the unix format in seconds (preferred, others will be parsed),
            only one of timestamp or phenomenonTime has to be set
        :param result: float, int, string, object, optional
            result value of the measurement of event, default = None
        :param kwargs:
            appends more arguments into class.meta
        """
        if timestamp is not None:
            self.phenomenonTime = self.extract_time(timestamp)
        elif phenomenon_time is not None:
            self.phenomenonTime = self.extract_time(phenomenon_time)
        else:
            raise Exception("Error, Either 'timestamp' or 'phenomenon_time' has to be set!")
        self.quantity = str(quantity)
        self.result = result
        self.metadata = kwargs

    def set_quantity(self, quantity):
        self.quantity = quantity

    def get_quantity(self):
        return self.quantity

    def get(self, attribute):
        return self.metadata.get(attribute)

    def extract_time(self, timestamp):
        """
        Recursively divides a timestamp by 1000 until the time is in seconds and not in ms, µs or ns
        :param timestamp: int, float, str (iso-8601)
            timestamp, a metric format is preferred
        :return: a unix timestamp that is normalized
        """
        if not isinstance(timestamp, (int, float)):
            import dateutil.parser
            return dateutil.parser.parse(timestamp).strftime("%s")
        if timestamp >= 1e11:
            timestamp /= 1000
            return self.extract_time(timestamp)
        return timestamp

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
    def __init__(self, instant_emit=True, delta_time=sys.maxsize, left="r", right="s",
                 buffer_results=True, join_function=None, verbose=False):
        """

        :param instant_emit: boolean, default=True
            Emit (join and reduce) on each new record in the buffer
        :param delta_time: float, int, default=sys.maxsize
            Sets the maximum allowed time difference of two join candidates
        :param left: str, optional
            Sets the stream's quantity name that is joined as left record
        :param right: str, optional
            Sets the stream's quantity name that is joined as right record
        :param buffer_results: boolean, default=True
            Whether or not to buffer resulting join records
        :param join_function: function(record_left, record_right), default=None
            A function for merging the two join tuples, can be seen as projection in terms of relational algebra.
            The default is None, that inherits all attributes of both records, the function can look as follows:

            def join_fct(record_left, record_right):
                record = Record(quantity=self.result_quantity,  # default 't'
                                result=record_left.get_result() * record_right.get_result(),
                                timestamp=(record_left.get_time() + record_right.get_time()) / 2)
                # produce resulting record in Kafka or a pipeline
                return record
        """
        # unload the input and stream the messages based on the order into the buffer queues
        self.buffer_left = list()
        self.buffer_right = list()
        self.instant_emit = instant_emit
        self.buffer_out = list()
        self.delta_time = delta_time
        self.left_quantity = left
        self.right_quantity = right
        self.buffer_results = buffer_results
        self.join_function = join_function
        self.verbose = verbose

    def get_left_buffer(self):
        """Get buffer r

        :return: the buffer r
        """
        return self.buffer_left

    def get_right_buffer(self):
        """Get buffer s

        :return: the buffer s
        """
        return self.buffer_right

    def fetch_results(self):
        """Fetch the buffer for the resulting join records. The buffer is emptied when fetched

        :return: a list of resulting join records
        """
        res = self.buffer_out
        self.buffer_out = list()
        return res

    def ingest_left(self, record):
        """
        Ingests a record into the left side of the StreamBuffer instance. Emits instantly join partners if not unset.
        :param record: object
            A Measurement or Event object.
        """
        self.buffer_left.append({"ts": record.get_time(), "record": record, "was_older": False})
        if self.instant_emit:
            self.buffer_left, self.buffer_right = self.emit(buffer_pivotal=self.buffer_left,
                                                            buffer_exterior=self.buffer_right)

    def ingest_right(self, record):
        """
        Ingests a record into the right side of the StreamBuffer instance. Emits instantly join partners if not unset.
        :param record: object
            A Measurement or Event object.
        """
        self.buffer_right.append({"ts": record.get_time(), "record": record, "was_older": False})
        if self.instant_emit:
            self.buffer_right, self.buffer_left = self.emit(buffer_pivotal=self.buffer_left,
                                                            buffer_exterior=self.buffer_right)

    def emit(self, buffer_pivotal, buffer_exterior):
        """
        This function is called if a new (pivotal) Record is received and tries to find join partners within two
        buffers and reduces them. If one of the buffers is empty, it is returned immediately.
        Otherwise, four cases are checked that can lead to a join:
        Case 1: Join latest pivotal Record with Records that occurred before the pivotal's predecessor Record.
        Case 2: Join the pivotal's predecessor Record with Records that occurred between itself and the pivotal Record.
        Case 3: Join the pivotal Record with Records that occurred between itself and its pivotal predecessor Record.
            The split of case 1 and 3 is required, as it ensures the correct timestamps of the joins.
        Case 4: Join lost Records that were never the older join partner and are about to get trimmed.
            TODO try to apply inverse Case 2 in order to catch them earlier.

        :param buffer_pivotal: list of Records
            The buffer with a pivotal record, i.e., the most recently received one that is checked for partners.
        :param buffer_exterior: list of Records
            The other buffer.
        :return: tuple of two Lists of Records
            A tuple of the same buffers in same order, but reduced if join partners where found
        """
        # Check if one of the Buffers is empty
        if len(buffer_exterior) == 0 or len(buffer_pivotal) == 0:
            return buffer_pivotal, buffer_exterior

        # Case 1: Join latest pivotal Record with Records that occurred before the pivotal's predecessor Record.
        # join s_1 with r_1, this is the case if r_1 was ingested, but the event order is s_1 < r_2 < r_1 < s_0
        # load the entries as tuples (record, was_sibling) from the buffer
        r_1 = buffer_pivotal[-1]  # latest record in buffer r, this one is new.
        r_2 = None if len(buffer_pivotal) < 2 else buffer_pivotal[-2]  # second to the latest record
        s_idx = 0
        s_1 = buffer_exterior[s_idx]  # first (= oldest) record of s
        s_0 = buffer_exterior[1] if len(buffer_exterior) >= 2 else None  # subsequent record or s_1
        if r_2 is not None:
            while s_0 is not None and s_1.get("record").get_time() < r_2.get("record").get_time():
                if r_1.get("record").get_time() < s_0.get("record").get_time():
                    # print("in part 1: ", end="")
                    self.join(r_1, s_1, case="1")
                    if not s_1.get("was_older"):
                        s_1["was_older"] = True
                s_idx += 1  # load next entry in s
                s_1 = buffer_exterior[s_idx] if s_idx < len(buffer_exterior) else None
                s_0 = buffer_exterior[s_idx + 1] if s_idx + 1 < len(
                    buffer_exterior) else None  # subsequent record or s_1

        # Case 2: join r_2 with records from s with event times between r_2 and r_1
        s_idx = 0
        s_1 = buffer_exterior[s_idx]  # first (= oldest) record of s
        s_0 = buffer_exterior[s_idx + 1] if s_idx + 1 < len(buffer_exterior) else None  # subsequent record or s_1
        # if r_2 is not None:
        while s_1 is not None and s_1.get("record").get_time() < r_1.get("record").get_time():
            if r_2 is not None and r_2.get("record").get_time() < s_1.get("record").get_time():
                self.join(r_2, s_1, case="2")
                if not r_2.get("was_older"):
                    r_2["was_older"] = True
            s_idx += 1  # load next entry in s
            s_1 = buffer_exterior[s_idx] if s_idx < len(buffer_exterior) else None
            # s_2 = buffer_s[s_idx+1] if s_idx + 1 < len(buffer_s) else None

        # Case 3: join r_1 with with records from s with event times between r_2 and r_1
        s_idx = 0
        s_1 = buffer_exterior[s_idx]  # first (= oldest) record of s
        while s_1 is not None and s_1.get("record").get_time() <= r_1.get("record").get_time():
            if r_2 is None or r_2.get("record").get_time() < s_1.get("record").get_time():
                self.join(r_1, s_1, case="3")
                if not s_1.get("was_older"):
                    s_1["was_older"] = True
            s_idx += 1  # load next entry in s
            s_1 = buffer_exterior[s_idx] if s_idx < len(buffer_exterior) else None

        # try to commit & remove deprecated records based on a record criteria (cases, B and E)
        buffer_pivotal = self.strip_buffers(buffer_pivotal, buffer_exterior)
        buffer_exterior = self.strip_buffers(buffer_exterior, buffer_pivotal)

        # it is necessary to return the two modified buffers and overwrite the instance variables
        return buffer_pivotal, buffer_exterior

    def strip_buffers(self, buffer_trim, buffer_current):
        """
        Trims one buffer if the record is outdated, that is if a more recent record exists or a record's
        timestamp exceeds a certain threshold compared to this of the exterior buffer.
        :param buffer_trim: List of Records
            A buffer that is about to get trimmed, based on the two cases.
        :param buffer_current: List of Records
            The comparision buffer that remains unchanged.
        :return: List of Records
            The trimmed buffer
        """
        # Return if buffer_exterior is empty
        if len(buffer_current) == 0:
            return buffer_trim

        # Case 4: Iteratively join and trim outdated Records if they have never been the older join partner
        # This helps to join Records that
        s_1 = None if len(buffer_current) < 1 else buffer_current[-1]  # load the latest (newest) entry of s
        s_idx = 0
        s_0 = buffer_current[s_idx]
        r_1 = buffer_trim[0]
        r_2 = None if len(buffer_trim) < 2 else buffer_trim[1]
        while r_2 is not None \
                and r_1.get("record").get_time() < r_2.get("record").get_time() <= s_1.get("record").get_time():
            # commit r_2 in the data streaming framework
            # remove r_2 from the buffer r
            # some records r_1 are not joined so far as older sibling
            if not r_1.get("was_older"):
                # forward to the first s, with event time r_1 < s_0
                while s_0 is not None and s_0.get("record").get_time() <= r_1.get("record").get_time():
                    s_idx += 1
                    s_0 = buffer_current[s_idx]
                self.join(r_1, s_0, case="4")
            # remove r_1 from buffer
            buffer_trim = buffer_trim[1:]
            r_1 = buffer_trim[0]
            r_2 = None if len(buffer_trim) < 2 else buffer_trim[1]

        # Remove old Records in buffer_r if the delta time is set
        if self.delta_time != sys.maxsize:
            s_0 = buffer_current[-1]  # the current record in buffer_s
            r_1 = None if len(buffer_trim) == 0 else buffer_trim[0]  # the oldest record in buffer_r, remove candidate
            while r_1 is not None and r_1.get("record").get_time() < s_0.get("record").get_time() - self.delta_time:
                # print(f"  removing outdated record {r_1.get('record')}, leader: {s_0.get('record')}")
                # remove r_1 from buffer
                buffer_trim = buffer_trim[1:]
                r_1 = None if len(buffer_trim) < 1 else buffer_trim[0]  # the oldest record in buffer_r, remove candidate

        return buffer_trim

    def join(self, u, v, case="undefined"):
        """Joins two objects 'u' and 'v' if the time constraint holds and produces a resulting record.
        The join_function can be set arbitrary, see __init__()

        :param case: String
            Specifies the case that leads to the join
        :param u: object that holds a record regardless if it is a left or right join partner
        :param v: object that holds a record regardless if it is a left or right join partner
        """
        # check the delta time constraint, don't join if not met
        if abs(u.get('record').get_time() - v.get('record').get_time()) <= self.delta_time:
            # decide based on the defined left_quantity, which record is joined as left join partner
            if v.get('record').get_quantity() == self.left_quantity:
                record_left = v.get('record')
                record_right = u.get('record')
            else:
                # select them from the normal order, default
                record_left = u.get('record')
                record_right = v.get('record')

            # apply an arbitrary join function to merge both records, if set
            if self.join_function:
                record = self.join_function(record_left=record_left, record_right=record_right)
            else:
                # apply the default join that is a merge using the records' quantity names as prefix
                record = {"r.quantity": record_left.get_quantity(), "r.phenomenonTime": record_left.get_time(),
                          "r.result": record_left.get_result(), "s.quantity": record_right.get_quantity(),
                          "s.phenomenonTime": record_right.get_time(), "s.result": record_right.get_result()}
                if record_left.get_metadata() != dict():
                    record["r.metadata"] = record_left.get_metadata()
                if record_right.get_metadata() != dict():
                    record["s.metadata"] = record_right.get_metadata()

            # print join to stdout and/or append to resulting buffer
            if self.verbose:
                print(f"New join, case {case}:\t {record}.")
            if self.buffer_results:
                self.buffer_out.append(record)


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


if __name__ == "__main__":
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
    print(f"joined time-series with {len(buffer_t)} resulting joins in {time.time() - ts} s.")
