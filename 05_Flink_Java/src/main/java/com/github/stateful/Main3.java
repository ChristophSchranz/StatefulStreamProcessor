package com.github.stateful;

import java.util.Properties;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.streaming.api.TimeCharacteristic;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.timestamps.AscendingTimestampExtractor;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaProducer;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaProducer.Semantic;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;

public class Main3
{
    static String TOPIC_IN = "machine.data";
    static String TOPIC_OUT = "machine.out";
    static String BOOTSTRAP_SERVER = "localhost:9092";

    @SuppressWarnings("serial")
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

        Producer<String> p = new Producer<String>(BOOTSTRAP_SERVER, StringSerializer.class.getName());

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
                                "myKey".getBytes(), value.getBytes())),
                        parameterTool.getProperties(),
                        Semantic.EXACTLY_ONCE);

        // create a stream to ingest data from Kafka with key/value
        DataStream<KafkaRecord> stream = env.addSource(kafkaConsumer);

        stream
                .filter((record) -> record.content != null && !record.content.isEmpty())
                .keyBy(record -> record.content.getProperty("quantity"))  // TODO should be thing
                .timeWindow(Time.seconds(5))
                .allowedLateness(Time.milliseconds(500))
                .aggregate(new AggregateFunction<KafkaRecord, String, String>()  // kafka aggregate API is very simple but same can be achieved by Flink's reduce
                {
                    @Override
                    public String createAccumulator() {
                        return "";
                    }

                    @Override
                    public String add(KafkaRecord record, String accumulator) {
                        return accumulator + " + " + record.content;
                    }

                    @Override
                    public String getResult(String accumulator) {

                        return accumulator;
                    }

                    @Override
                    public String merge(String a, String b) {
                        System.out.println("in merge");
                        System.exit(2);
                        return a+b;
                    }
                })
                .addSink(kafkaProducer);

        // produce a number as string every second
//        new NumberGenerator(p, TOPIC_IN).start();

        // for visual topology of the pipeline. Paste the below output in https://flink.apache.org/visualizer/
        System.out.println( env.getExecutionPlan() );

        // start flink
        env.execute();
    }
}

