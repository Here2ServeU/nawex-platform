#!/bin/bash
sudo apt update && sudo apt upgrade -y
wget -O splunk.tgz 'https://download.splunk.com/products/splunk/releases/9.3.0/linux/splunk.tgz'
sudo tar -xvf splunk.tgz -C /opt
sudo /opt/splunk/bin/splunk start --accept-license
