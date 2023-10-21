import asyncio
from collections import Counter
import redis
from telegram import Bot
from telegram.error import TelegramError
import ssl
import nats
import os

# read env variables needed to connect to NATS, Redis, Telegram
TOKEN = os.getenv('NATS_TOKEN')
NATS_ADDRESS = os.getenv('NATS_ADDRESS')
REDIS_PASSWORD=os.getenv('REDIS_PASSWORD')
REDIS_ADDRESS=os.getenv('REDIS_ADDRESS')
TELEGRAM_KEY=os.getenv('TELEGRAM_KEY')
TELEGRAM_CHAT=os.getenv('TELEGRAM_CHAT')


# async communication needed for NATS
async def main():
    # read ssl files
    ssl_ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ssl_ctx.load_verify_locations('./CA.pem')
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2  
    ssl_ctx.load_cert_chain(
        certfile='./container5-cert.pem',
        keyfile='./container5-key.pem')

    # open connection to NATS, Redis
    nc = await nats.connect(servers=[f"nats://{TOKEN}@{NATS_ADDRESS}:4222"], tls=ssl_ctx, tls_hostname="nats")
    js = nc.jetstream()
    r = redis.Redis(host=REDIS_ADDRESS, port=7379,
                    ssl=True, ssl_keyfile="./container5-key.pem",
                    ssl_ca_certs="./CA.pem",
                    ssl_certfile="container5-cert.pem",
                    password=REDIS_PASSWORD)
    
    # init previous activity value for Telegram comparison
    r.set("previous_prediction", "placeholder")

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

        # decode message from NATS
        for message in latest_label:
            encoded_latest_label = message.data.decode()
        
        print("=======\nEncoded latest prediction")
        print(encoded_latest_label)

        # retrieve last three labels from Redis as well as current and previous predictions
        first_val = r.get("first_val")
        second_val = r.get("second_val")
        third_val = r.get("third_val")
        prevPrediction = r.get("previous_prediction")

        print("=======\nRedis values")
        print(f"First value: {first_val}")
        print(f"Second value: {second_val}")
        print(f"Third value: {third_val}")
        print(f"Previous prediction: {prevPrediction}")

        if first_val is not None:
            first_val = first_val.decode()
        else: 
            first_val = "placeholder"

        if second_val is not None:
            second_val = second_val.decode()
        else: 
            first_val = "placeholder"

        if third_val is not None:
            third_val = third_val.decode()
        else: 
            first_val = "placeholder"

        print("=======\nRedis values again")
        print(f"First value: {first_val}")
        print(f"Second value: {second_val}")
        print(f"Third value: {third_val}")
        print(f"Previous prediction: {prevPrediction}")
        
        comparison_list = [encoded_latest_label, first_val, second_val, third_val]
        
        print("=======\nComparison list")
        print(f"Comparison list: {comparison_list}")

        # choose the most common string
        string_counts = Counter(comparison_list)
        most_common_string = string_counts.most_common(1)[0][0]
        
        print("=======\nMost common strings")
        print(string_counts)
        print(most_common_string)

        if most_common_string != encoded_latest_label:
            print(f"to output (if): {most_common_string}")
        else:
            print(f"to output (else): {encoded_latest_label}")

        # update redis with latest predicted label
        r.set("first_val", encoded_latest_label)
        r.set("second_val", first_val)
        r.set("third_val", second_val)

        # send final output to nats
        _ = await js.publish("output", f"{most_common_string}".encode(), stream="RPI")
        print("output sent to NATS")
        

        print("=======\nTelegram")
        print(f"Most common string: {most_common_string}")
        print(f"Previous prediction: {prevPrediction}")
        if most_common_string != prevPrediction.decode():
            try:    
                r.set("previous_prediction", most_common_string)
                # initialize a Telegram bot
                bot = Bot(token=TELEGRAM_KEY)

                # send the NATS message content to Telegram
                await bot.send_message(chat_id=TELEGRAM_CHAT, text=most_common_string)

            except TelegramError as e:
                print(f"Telegram Error: {e}")
                

if __name__ == '__main__':
    asyncio.run(main())
