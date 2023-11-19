#!/bin/bash

# use correct context, docker logout 
docker context use $AZURE_CONTEXT
docker logout

# create resource group
echo "Creating resource group RPI-Cloud."
az group create --location westeurope --name RPI-Cloud

# create storage account
echo "Creating storage account $SA_NAME."
az storage account create --resource-group RPI-Cloud --name $SA_NAME --location westeurope --kind StorageV2 --sku Standard_LRS

# create file share
echo "Creating file share $SHARE_NAME."
az storage share-rm create --resource-group RPI-Cloud --storage-account $SA_NAME --name $SHARE_NAME --quota 1 --enabled-protocols SMB

# upload config files
echo "Uploading files to $SHARE_NAME..."
cd ../nats-config

for file in ./*; do
    az storage file upload --account-name $SA_NAME --share-name $SHARE_NAME --source $file --path $file
done

echo "Files uploaded."

# deploy app 
cd ../
docker compose up
