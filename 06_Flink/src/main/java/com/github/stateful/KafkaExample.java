package com.github.stateful;



import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.DataStreamSink;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer;
import org.apache.flink.streaming.util.serialization.SimpleStringSchema;
//import org.apache.flink.streaming.kafka.test.base.CustomWatermarkExtractor;
//import org.apache.flink.streaming.kafka.test.base.KafkaEvent;
//import org.apache.flink.streaming.kafka.test.base.KafkaEventSchema;
//import org.apache.flink.streaming.kafka.test.base.KafkaExampleUtil;
//import org.apache.flink.streaming.kafka.test.base.RollingAdditionMapper;

/**
 * A simple example that shows how to read from and write to modern Kafka. This will read String messages
 * from the input topic, parse them into a POJO type {@link KafkaEvent}, group by some key, and finally
 * perform a rolling addition on each key for which the results are written back to another topic.
 *
 * <p>This example also demonstrates using a watermark assigner to generate per-partition
 * watermarks directly in the Flink Kafka consumer. For demonstration purposes, it is assumed that
 * the String messages are of formatted as a (word,frequency,timestamp) tuple.
 *
 * <p>Example usage:
 * 	--input-topic machine.data --output-topic machine.out --bootstrap.servers localhost:9092
 * 	--zookeeper.connect localhost:2181 --group.id myconsumer
 */
public class KafkaExample extends KafkaExampleUtil {

    public static void main(String[] args) throws Exception {
        System.out.println(args[0]);
        // parse input arguments
        final ParameterTool parameterTool = ParameterTool.fromArgs(args);
        System.out.println(parameterTool.getRequired("input-topic"));
        StreamExecutionEnvironment env = KafkaExampleUtil.prepareExecutionEnv(parameterTool);

        FlinkKafkaConsumer<String> source = new FlinkKafkaConsumer<>(
                parameterTool.getRequired("input-topic"),
                new SimpleStringSchema(),
                parameterTool.getProperties());

        DataStreamSink<String> streamexample = env.addSource(source).print();
        //DataStream<KafkaEvent> input = env
//        DataStream<String> input = env
//                .addSource(
//                        new FlinkKafkaConsumer(
//                                parameterTool.getRequired("input-topic"),
//                                //new KafkaEventSchema(),
//                                new SimpleStringSchema(),
//                                parameterTool.getProperties())
//                                .assignTimestampsAndWatermarks(new CustomWatermarkExtractor()))
//                .print();
                //.keyBy("word")
                //.map(new RollingAdditionMapper());

//        input.addSink(
//                new FlinkKafkaProducer(
//                        parameterTool.getRequired("output-topic"),
//                        new KeyedSerializationSchemaWrapper(new KafkaEventSchema()),
//                        parameterTool.getProperties(),
//                        FlinkKafkaProducer.Semantic.EXACTLY_ONCE));

        env.execute("Modern Kafka Example");
    }

}
