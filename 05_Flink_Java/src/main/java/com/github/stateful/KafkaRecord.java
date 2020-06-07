package com.github.stateful;

import java.io.Serializable;
import java.util.Properties;

import lombok.Data;


@Data
public class KafkaRecord implements Serializable
{
    String key;
    public Properties content;
    long timestamp;

    @Override
    public String toString() {
        return key + ": " + content.toString();
    }
}
