#!/bin/bash
# function to get the tag of a Docker image
get_image_tag() {
    local image_name="$1"
    local raw_output=$(docker images --format '{{.Tag}}' "$image_name" 2>/dev/null | tr -d '\r')
    local current_tag=$(echo -n "$raw_output" | sed -E 's/default[[:space:]]*//')

    if [ -n "$current_tag" ]; then
        echo "$current_tag"
    else
        echo "Image '$image_name' not found or has no tag."
    fi
}

# create resource group
echo "Creating resource group RPI-Cloud."
az group create --location westeurope --name RPI-Cloud

# create storage account
echo "Creating storage account harrpistorage."
az storage account create --resource-group RPI-Cloud --name harrpistorage --location westeurope --kind StorageV2 --sku Standard_LRS

# create file share
echo "Creating file share nats-config."
az storage share-rm create --resource-group RPI-Cloud --storage-account harrpistorage --name nats-config --quota 1 --enabled-protocols SMB

# upload config files
echo "Uploading files to harrpistorage..."
cd ../nats-config

for file in ./*; do
    az storage file upload --account-name harrpistorage --share-name nats-config --source $file --path $file
done

echo "Files uploaded."

# deploy app 
cd ../
docker context use default
export LATEST_FEATURE_EXTRACTOR_TAG=$(get_image_tag "feature_extractor")
export LATEST_ML_PREDICTOR_TAG=$(get_image_tag "ml_predictor")
docker context use har-azure
docker compose up