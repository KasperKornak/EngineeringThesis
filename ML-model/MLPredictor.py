from keras.models import load_model
import tensorflow as tf
import asyncio
import os
import nats
import base64
import pandas as pd
import numpy as np

# func to load the trained model
def init_model():
    model = load_model('model.h5')
    return model

# read env variables needed to connect to NATS
TOKEN = os.getenv('NATS_TOKEN')
NATS_ADDRESS = os.getenv('NATS_ADDRESS')

# class labels for predicted outputs
class_mapping = {
    0: "downstairs",
    1: "lying",
    2: "sitting",
    3: "squats",
    4: "standing",
    5: "upstairs",
    6:  "walking" }

# async communication needed for NATS
async def main():
    # load the model, open connection to NATS
    model = init_model()
    nc = await nats.connect(f"nats://{TOKEN}@{NATS_ADDRESS}:4222")
    js = nc.jetstream()

    # create consumer
    sub_feats = await js.pull_subscribe("feats", "RPI-sub-feats", "RPI")

    # predict the activity in main loop
    while True:
        # consume latest features
        messages = await sub_feats.fetch(1, timeout=None)

        # predict the activity 
        for message in messages:
            # decode from base64, reconstruct DataFrame and convert to tensor
            # for ML model
            decoded_feats = base64.b64decode(message.data)
            decoded_feats_str = decoded_feats.decode('utf-8')  
            featuresDf = pd.read_json(decoded_feats_str, orient='split')
            window_data = featuresDf.values.reshape(1, -1)
            window_data_tensor = tf.convert_to_tensor(window_data, dtype=tf.float64)

            # map probabilities to class_mapping dictionary
            pred = model.predict(window_data_tensor)
            predicted_class = np.argmax(pred)

            # send predicted label to predictions subject
            _ = await js.publish("predictions", f"{class_mapping[predicted_class]}".encode(), stream="RPI")

if __name__ == '__main__':
    asyncio.run(main())