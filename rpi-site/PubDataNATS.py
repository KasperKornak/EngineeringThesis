import board
import asyncio
import nats
import ssl
import os
from adafruit_lis3mdl import Rate
from adafruit_lsm6ds.lsm6ds3 import LSM6DS3 as LSM6DS

# read NATS env variables
NATS_ADDRESS = os.getenv("NATS_ADDRESS")
NATS_TOKEN = os.getenv("NATS_TOKEN")

# setup acceleration rate
accel_rate = Rate.RATE_300_HZ

# setup i2x and accelerometer
i2c = board.I2C()
accel_gyro = LSM6DS(i2c)
accel_gyro.accelerometer_data_rate = accel_rate

# async communication needed for NATS
# streaming with persistence using JetStream
async def main():
    # read ssl files
    ssl_ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ssl_ctx.load_verify_locations('./CA.pem')
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.load_cert_chain(
        certfile='./container4-cert.pem',
        keyfile='./container4-key.pem')

    # open connection to NATS and interface for JetStream
    nc = await nats.connect(f"nats://{NATS_TOKEN}@{NATS_ADDRESS}:4222", tls=ssl_ctx, tls_hostname="nats")
    js = nc.jetstream()
    print("connected to NATS")
    # counter to keep track of samples
    counter = 0
    while True:
        if counter % 3 == 0:
            acceleration = accel_gyro.acceleration

            # publish data
            _ = await js.publish("x", f"{acceleration[0] / 9.81}".encode(),stream="RPI")
            _ = await js.publish("y", f"{acceleration[1] / 9.81}".encode(),stream="RPI")
            _ = await js.publish("z", f"{acceleration[2] / 9.81}".encode(),stream="RPI")

        counter +=1 


if __name__ == '__main__':
    asyncio.run(main())