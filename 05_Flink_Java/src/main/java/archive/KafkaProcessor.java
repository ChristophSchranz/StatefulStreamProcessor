package archive;

// make sure that the maven dependencies are correctly set!

import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.SingleOutputStreamOperator;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaProducer;

import java.util.HashMap;
import java.util.Map;

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
public class KafkaProcessor extends KafkaExampleUtil {

    private static Object JSONKeyValueDeserializationSchema;

    public static void main(String[] args) throws Exception {
        // load input arguments or using defaults if none were given
        if (args.length <= 1) {
            System.out.println("no arguments were given, using default arguments:");
            args = new String[]{"--input-topic", "machine.data", "--output-topic", "machine.out", "--bootstrap.servers",
                    "localhost:9092", "--zookeeper.connect", "localhost:2181", "--group.id", "myconsumer"};
        } else
            System.out.println("Arguments:");
        for (String a: args)
            System.out.print(a + " ");
        System.out.println();

        // parse input arguments to new instance of Flink's ParameterTool class
        final ParameterTool parameterTool = ParameterTool.fromArgs(args);
        StreamExecutionEnvironment env = KafkaExampleUtil.prepareExecutionEnv(parameterTool);

//      input string {"thing": "R0815", "quantity": "vaCurr_X10", "phenomenonTime": 1554101188221, "result": 5.81060791015625}

        // create hash map
        HashMap<String, String> kSchema = new HashMap<>();


        // create Kafka Consumer
        FlinkKafkaConsumer<String> source = new FlinkKafkaConsumer<>(
                parameterTool.getRequired("input-topic"),
//                new JSONDeserializationSchema(),
                new SimpleStringSchema(),  // load records as String, should be changed later
                parameterTool.getProperties());

        // create data-stream
        DataStream<String> input = env.addSource(source);
//                keyBy("timestamp");
//                map(new RollingAdditionMapper());

        // parse intput to Hashmap and print the quantity
        SingleOutputStreamOperator<String> parsedInput = input
                .map(KafkaProcessor::toHashMap)
                .map(map -> map.get("quantity"));
        parsedInput.print();

        // print input in stdout
        input.print();
//        System.out.println(input.toString());

        // add sink to data-stream
        parsedInput.addSink(
                new FlinkKafkaProducer<>(
                        parameterTool.getRequired("output-topic"),
                        new SimpleStringSchema(),  // load records as String, should be changed later
                        parameterTool.getProperties())
//                        FlinkKafkaProducer.Semantic.EXACTLY_ONCE)
        );

        // execute the data-stream
        env.execute("Modern Kafka Example");
    }


    public static Map<String, String> toHashMap(String input) {
        Map<String, String> map = new HashMap<String, String>();
        String[] pairs = input.replace("{", "").replace("}", "").split(",");

        for (String pair: pairs) {
            String[] s = pair.split(":");
            map.put(s[0].replace("\"", "").trim(), s[1].replace("\"", "").trim());
        }
        return map;
    }
}
