package com.github.stateful;

import java.io.Serializable;

import lombok.Data;

@SuppressWarnings("serial")
@Data
public class KafkaRecord implements Serializable
{
    String key;
    public String value; //TODO should be double
    Long timestamp;

    @Override
    public String toString()
    {
        return key+":"+value;
    }

}