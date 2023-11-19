import ssl
import asyncio
import os
import nats
import base64
import pandas as pd
from joblib import load
from tabpfn import *

# func to load the trained model
def init_model():
    model = load('model.joblib')
    return model

# read env variables needed to connect to NATS
TOKEN = os.getenv('NATS_TOKEN')
NATS_ADDRESS = os.getenv('NATS_ADDRESS')

# list of columns to drop when reading incoming features DataFrame
to_drop = ['acc_z_mpf', 'acc_z_iqr', 'acc_x_three_quarters', 'acc_y_three_quarters', 'acc_z_three_quarters', 'acc_y_kurtosis_f', 'acc_z_kurtosis_f', 'acc_y_skewness_f', 'acc_z_skewness_f', 'acc_x_iqr', 'acc_y_iqr', 'acc_y_one_quarter', 'acc_y_wilson_amp', 'acc_z_wilson_amp', 'acc_y_wf', 'acc_y_p2p', 'acc_z_p2p', 'acc_x_wf', 'acc_y_mav', 'acc_z_mav', 'acc_y_stdev', 'acc_x_mad', 'acc_z_wf', 'acc_x_p2p', 'acc_x_kurtosis_f', 'acc_x_skewness_f', 'acc_x_mav', 'acc_y_enwacto_1', 'acc_x_enwacto_1', 'acc_x_autoregyw_2', 'acc_y_autoregyw_1', 'acc_x_autoregburg_1', 'acc_y_autoregburg_1', 'acc_x_autoregburg_2', 'acc_x_autoregburg_3', 'acc_x_autoregburg_4', 'acc_y_autoregburg_2', 'acc_y_autoregburg_3', 'acc_z_autoregyw_3', 'acc_z_autoregburg_2', 'acc_z_autoregburg_3', 'acc_z_autoregburg_4', 'acc_x_mpf', 'acc_x_wilson_amp', 'acc_z_one_quarter', 'acc_x_slope_change', 'acc_y_slope_change', 'acc_z_slope_change', 'acc_x_rms', 'acc_x_mean', 'acc_y_mad', 'acc_y_zerocr', 'acc_y_autoregyw_2', 'acc_y_autoregyw_4', 'acc_z_autoregyw_1']

# async communication needed for NATS
async def main():
    # read ssl files
    ssl_ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ssl_ctx.load_verify_locations('./CA.pem')
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2 
    ssl_ctx.load_cert_chain(
        certfile='./container2-cert.pem',
        keyfile='./container2-key.pem')

    # load the model, open connection to NATS
    model = init_model()
    nc = await nats.connect(servers=[f"nats://{TOKEN}@{NATS_ADDRESS}:4222"], tls=ssl_ctx, tls_hostname="nats")
    js = nc.jetstream()

    # create consumer
    sub_feats = await js.pull_subscribe("feats", "RPI-sub-feats", "RPI")

    while True:
        try:
            # consume latest features with a timeout
            messages = await asyncio.wait_for(sub_feats.fetch(1), timeout=300.0)
        except asyncio.TimeoutError:
            print("No new messages, sleeping for 2 seconds.")
            await asyncio.sleep(2)
            continue 

        try:
            # predict the activity for received features
            for message in messages:
                # decode from base64, reconstruct DataFrame, and convert to tensor
                decoded_feats = base64.b64decode(message.data)
                decoded_feats_str = decoded_feats.decode('utf-8')  
                featuresDf = pd.read_json(decoded_feats_str, orient='split')
                featuresDf = featuresDf.drop(columns=to_drop)
                if featuresDf.empty == True:
                    continue
                window_data = featuresDf.values.reshape(1, -1)
                
                # print features dataframe
                print(window_data)

                # map probabilities to class_mapping dictionary
                pred = model.predict(window_data)
                predicted_class = pred[0]
                print(f"Prediction: {predicted_class}")
                # send predicted label to predictions subject
                _ = await js.publish("predictions", f"{predicted_class}".encode(), stream="RPI")
                print("prediction sent to NATS")
        except Exception as e:
            print(f"Exception ocurred: {e}")


if __name__ == '__main__':
    asyncio.run(main())