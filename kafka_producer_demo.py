from kafka import KafkaProducer
import pandas as pd
import os
import time
from json import dumps

KAFKA_TOPIC_NAME_CONS = "orderstopicdemo"
#add on list N localhost server if you use N servers
KAFKA_BOOTSTRAP_SERVERS_CONS = 'localhost:9092'

if __name__ == '__main__':
    print("Kafka producer application is started ")

    kafka_producer_obj = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS_CONS,
                                       value_serializer=lambda x: dumps(x).encode('utf-8'))
    
    input_path = '/home/ochrifi/Documents/Project/RealTimeAnalysis/in'

    df_order = pd.read_csv(os.path.join(input_path,'orders.csv'))

    print(df_order.head(1))

    list_order = df_order.to_dict(orient='records')

    print(list_order[0])

    for message in list_order:
        print(f'message to be send: {message}')
        kafka_producer_obj.send(KAFKA_TOPIC_NAME_CONS, message)
        time.sleep(1)