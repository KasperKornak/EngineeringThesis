#!/bin/bash

# due to limited disk space, image removal is needed
# delete old images
docker rmi feature_extractor:1.0 --force
docker rmi ml_predictor:1.0 --force

# change directory to ML-model
cd ../ML-model
docker build -t ml_predictor:1.0 .

# change directory to feature-extractor
cd ../feature-extractor
docker build -t feature_extractor:1.0 .

# run docker compose up
cd ..
docker compose up