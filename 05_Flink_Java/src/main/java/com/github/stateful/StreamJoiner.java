package com.github.stateful;

import java.text.NumberFormat;
import java.util.*;

import com.google.gson.Gson;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.streaming.api.TimeCharacteristic;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.timestamps.AscendingTimestampExtractor;
import org.apache.flink.streaming.api.windowing.assigners.SlidingEventTimeWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaProducer;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaProducer.Semantic;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;

public class StreamJoiner
{
    static String TOPIC_IN;
    static String TOPIC_OUT;
    static String BOOTSTRAP_SERVER;


    public static void main( String[] args ) throws Exception {
        // load input arguments or using defaults if none were given
        if (args.length <= 1) {
            System.out.println("no arguments were given, using default arguments:");
            args = new String[]{"--input-topic", "machine.data", "--output-topic", "machine.out",
                    "--bootstrap.servers", "localhost:9092", "--zookeeper.connect", "localhost:2181",
                    "--group.id", "myconsumer", "--client.id", "flink"};
        } else
            System.out.println("Arguments:");
        for (String a: args)
            System.out.print(a + " ");
        System.out.println();

        // parse input arguments to new instance of Flink's ParameterTool class
        final ParameterTool parameterTool = ParameterTool.fromArgs(args);
        TOPIC_IN = parameterTool.getRequired("input-topic");
        TOPIC_OUT = parameterTool.getRequired("output-topic");
        BOOTSTRAP_SERVER = parameterTool.getRequired("bootstrap.servers");

//        Producer<String> p = new Producer<String>(BOOTSTRAP_SERVER, StringSerializer.class.getName());
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        // to use allowed lateness, set to EventTime
        env.setStreamTimeCharacteristic(TimeCharacteristic.EventTime);

//        Properties props = new Properties();
//        props.put("bootstrap.servers", BOOTSTRAP_SERVER);
//        props.put("client.id", "flink");

        // consumer to get both key/values per Topic
        FlinkKafkaConsumer<KafkaRecord> kafkaConsumer = new FlinkKafkaConsumer<>(TOPIC_IN,
                new KafkaSchema(),
                parameterTool.getProperties());

        // for allowing Flink to handle late elements
        kafkaConsumer.assignTimestampsAndWatermarks(new AscendingTimestampExtractor<KafkaRecord>()
        {
            @Override
            public long extractAscendingTimestamp(KafkaRecord record)
            {
                return record.timestamp;
            }
        });

        kafkaConsumer.setStartFromLatest();

//        // Create Kafka producer from Flink API
//        Properties prodProps = new Properties();
//        prodProps.put("bootstrap.servers", BOOTSTRAP_SERVER);

        FlinkKafkaProducer<String> kafkaProducer =
                new FlinkKafkaProducer<String>(TOPIC_OUT,
                        ((value, timestamp) -> new ProducerRecord<byte[], byte[]>(TOPIC_OUT,
                                "Flink_vaPower".getBytes(), value.getBytes())),
                        parameterTool.getProperties(),
                        Semantic.EXACTLY_ONCE);

        // create a stream to ingest data from Kafka with key/value
        DataStream<KafkaRecord> stream = env.addSource(kafkaConsumer);

        stream
                .filter((record) -> record.content != null && !record.content.isEmpty())
                .filter((record) -> quantity_contains(record.content.getProperty("quantity")))
                .keyBy(record -> quantity_group(record.content.getProperty("quantity")))
                .window(SlidingEventTimeWindows.of(Time.seconds(1), Time.milliseconds(250)))
                .allowedLateness(Time.milliseconds(250))
                .aggregate(new AggregateFunction<KafkaRecord, ArrayList<KafkaRecord>, String>()  // kafka aggregate API is very simple but same can be achieved by Flink's reduce
                {
                    @Override
                    public ArrayList<KafkaRecord> createAccumulator() {
                        return new ArrayList<KafkaRecord>();
                    }

                    @Override
                    public ArrayList<KafkaRecord> add(KafkaRecord record, ArrayList<KafkaRecord> accumulator) {
                        accumulator.add(record);
                        return accumulator;
                    }

                    @Override
                    // the functions join works similar to Vertica's INTERPOLATE ON PREVIOUS VALUE
                    public String getResult(ArrayList<KafkaRecord> accumulator) {
//                        // To print the accumulated records, uncomment this:
//                        return accumulator.toString();
                        System.out.println("Aggregating a sum of " + accumulator.size() + " values.");

                        // sort KafkaRecords in accumulator by Event Time
                        accumulator.sort(StreamJoiner::compare_timestamps);

                        Gson gson = new Gson();

                        // search for the two latest join partners
                        KafkaRecord latest_r = null;
                        KafkaRecord latest_s = null;
                        String joined_records = "";
                        for (int idx=accumulator.size()-1; idx>=0; idx--) {
                            if (accumulator.get(idx).content.getProperty("quantity").startsWith("vaTorque_C")) {
                                latest_r = accumulator.get(idx);
                            }
                            if (accumulator.get(idx).content.getProperty("quantity").startsWith("actSpeed_C")) {
                                latest_s = accumulator.get(idx);
                            }
                            // if there is a value of both metrics, join them
                            if (latest_r == null || latest_s == null)
                                continue;

                            // join selected records and append them to the joined_records ArrayList
                            Properties payload = new Properties();
                            payload.put("thing", latest_s.content.getProperty("thing"));
                            payload.put("quantity", "power" + quantity_group(latest_r.content.getProperty("quantity")));

                            // choose smaller timestamp
                            if (latest_r.content.getProperty("phenomenonTime").compareTo(
                                    latest_s.content.getProperty("phenomenonTime")) < 0)
                                payload.put("phenomenonTime", latest_r.content.getProperty("phenomenonTime"));
                            else
                                payload.put("phenomenonTime", latest_s.content.getProperty("phenomenonTime"));

                            // calculate the resulting power and transfer it into a non-scientific float
                            double res = Math.abs((2*Math.PI/60)
                                    * Double.parseDouble(latest_r.content.getProperty("result"))
                                    *  Double.parseDouble(latest_s.content.getProperty("result")));
			    
                            // some cosmetics
                            if (res > 20000)
                                res = 20000;

                            // calculate power level
                            int level = (int) (res/20000.1*5);
                            switch(level) {
                            case 0: payload.put("level", "  0% ...  20%");
                                break;
                            case 1: payload.put("level", " 20% ...  40%");
                                break;
                            case 2: payload.put("level", " 40% ...  60%");
                                break;
                            case 3: payload.put("level", " 60% ...  80%");
                                break;
                            case 4: payload.put("level", " 80% ... 100%");
                                break;
                            default: payload.put("level", "  0% ...  20%");
                                break;
                            }

                            payload.put("duration", 1);
                            payload.put("result", res);

                            // append
                            joined_records = gson.toJson(payload) + "\n" + joined_records;
                        }

                        // the payload must be a String were the record payloads are separated by "\n"
//                        return payload.toString() + "\n" + payload.toString();
                        return joined_records;
                    }

                    @Override
                    public ArrayList<KafkaRecord> merge(ArrayList<KafkaRecord> a, ArrayList<KafkaRecord> b) {
                        System.out.println("in merge");
                        System.exit(2);
                        a.addAll(b);
                        return a;
                    }
                })
                .filter((payload) -> payload != null && !payload.isEmpty())
                .flatMap(new LineSplitter())
                .keyBy((record) -> record)
                .addSink(kafkaProducer);

        // produce a number as string every second
//        new NumberGenerator(p, TOPIC_IN).start();

        // for visual topology of the pipeline. Paste the below output in https://flink.apache.org/visualizer/
        System.out.println( env.getExecutionPlan() );

        // start flink
        env.execute("Stream Joiner");
    }


    /* checks whether or not the quantity is of interest for the aggregation or not. */
    private static boolean quantity_contains(String quantity) {
        if (quantity.startsWith("vaTorque_C"))
            return true;
        if (quantity.startsWith("actSpeed_C"))
            return true;
        // return otherwise
        return false;
    }

    /* returns the postfix of the quantity with 3 letters, e.g. Z13*/
    private static String quantity_group(String quantity) {
        int q_len = quantity.length();
        return quantity.substring(q_len - 3);
    }

    /* returns the postfix of the quantity with 3 letters, e.g. Z13*/
    private static int compare_timestamps(KafkaRecord rec_1, KafkaRecord rec_2) {
        long time_1 = Long.parseLong(rec_1.content.getProperty("phenomenonTime"));
        long time_2 = Long.parseLong(rec_2.content.getProperty("phenomenonTime"));
        return (int)(time_1 - time_2);
    }
}
