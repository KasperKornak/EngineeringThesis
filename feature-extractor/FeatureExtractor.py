import asyncio
import nats
import pandas as pd
import base64
import ssl
import os
from SignalFeatures import *

# read env variables needed to connect to NATS
TOKEN = os.getenv('NATS_TOKEN')
NATS_ADDRESS = os.getenv('NATS_ADDRESS')

# async communication needed for NATS
async def main():
    # read ssl files
    ssl_ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ssl_ctx.load_verify_locations('./CA.pem')
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.load_cert_chain(
        certfile='./container1-cert.pem',
        keyfile='./container1-key.pem')

    nc = await nats.connect(servers=[f"nats://{TOKEN}@{NATS_ADDRESS}:4222"], tls=ssl_ctx, tls_hostname="nats")
    js = nc.jetstream()

    # create consumers
    sub_x = await js.pull_subscribe("x", "RPI-sub-x", "RPI")
    sub_y = await js.pull_subscribe("y", "RPI-sub-y", "RPI")
    sub_z = await js.pull_subscribe("z", "RPI-sub-z", "RPI")

    # consume data in 500-data-points tranches
    while True:
        windowDf = pd.DataFrame(columns=['x', 'y', 'z'])
        try:
            x_data = await asyncio.wait_for(sub_x.fetch(500), timeout=300.0)
            y_data = await asyncio.wait_for(sub_y.fetch(500), timeout=300.0)
            z_data = await asyncio.wait_for(sub_z.fetch(500), timeout=300.0)
        except asyncio.TimeoutError:
            print("No new messages, sleeping for 30 seconds.")
            await asyncio.sleep(30)
            continue
        
        try:
            x_data_list = [m.data.decode() for m in x_data]
            y_data_list = [m.data.decode() for m in y_data]
            z_data_list = [m.data.decode() for m in z_data]

            print("=======\nDecoded data")
            print(x_data_list)
            print(y_data_list)
            print(z_data_list)

            # export data from sensors to pandas DataFrame
            windowDf['x'] = x_data_list
            windowDf['y'] = y_data_list
            windowDf['z'] = z_data_list

            print("=======\Constructed dataframe")
            print(windowDf.head())

            # treat data points as floats
            windowDf['x'] = windowDf['x'].astype(float)
            windowDf['y'] = windowDf['y'].astype(float)
            windowDf['z'] = windowDf['z'].astype(float)

            print("=======\nDataframe as float")
            print(windowDf.head())

            # calculate features of the given window
            # send them to feats subject
            print("=======\nFeatures dataframe")
            feats = feats_df(windowDf)
            print(feats)

            print("=======\nDataframe as JSON")
            json_data = feats.to_json(orient='split')
            print(json_data)

            print("=======\nBase64 JSON dataframe")
            base64_encoded_data = base64.b64encode(json_data.encode()).decode()
            print(base64_encoded_data)

            _ = await js.publish("feats", f"{base64_encoded_data}".encode(), stream="RPI")
            print("Features published to NATS")
        
        except Exception as e:
            continue

if __name__ == '__main__':
    asyncio.run(main())
