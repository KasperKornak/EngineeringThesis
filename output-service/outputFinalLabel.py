import asyncio
from collections import Counter
import redis
import ssl
import nats
import os

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
        certfile='./container5-cert.pem',
        keyfile='./container5-key.pem')

    # open connection to NATS and Redis
    nc = await nats.connect(servers=[f"nats://{TOKEN}@{NATS_ADDRESS}:4222"], tls=ssl_ctx, tls_hostname="nats")
    js = nc.jetstream()
    r = redis.Redis(host="localhost", port=6379,
                    ssl=True, ssl_keyfile="./container5-key.pem",
                    ssl_ca_certs="./CA.pem",
                    ssl_certfile="container5-cert.pem")

    # create consumers
    sub_y = await js.pull_subscribe("predictions","RPI-sub-predictions","RPI")

    while True:
        try:
            # consume latest activity label with a timeout
            latest_label = await asyncio.wait_for(sub_y.fetch(1), timeout=300.0)
        except asyncio.TimeoutError:
            print("No new messages, sleeping for 2 minutes.")
            await asyncio.sleep(120)  
            continue  

        # retrieve last three labels from Redis
        first_val = r.get("first_val").decode()
        second_val = r.get("second_val").decode()
        third_val = r.get("third_val").decode()
        comparison_list = [latest_label, first_val, second_val, third_val]
        
        # choose the most common string
        string_counts = Counter(comparison_list)
        most_common_strings = string_counts.most_common()
        most_common_string, _ = most_common_strings[0]
        
        if most_common_string != latest_label:
            print(f"to output: {most_common_string}")
        else:
            print(f"to output: {latest_label}")

        # update redis with latest predicted label
        r.set("first_val", latest_label)
        r.set("second_val", first_val)
        r.set("third_val", second_val)
                

if __name__ == '__main__':
    asyncio.run(main())
