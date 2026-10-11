#!/usr/bin/env bash
# ===========================================================================
# Golden Platform - Splunk bootstrap
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
set -eux

ADMIN_PASSWORD="${admin_password}"
HEC_TOKEN="${hec_token}"

# Basic packages
apt-get update -y
apt-get install -y wget curl gnupg lsb-release

# Install Splunk Enterprise (Ubuntu example)
wget -O /tmp/splunk.deb 'https://download.splunk.com/products/splunk/releases/9.1.0/linux/splunk-9.1.0-ae6821b7c64b-linux-2.6-amd64.deb'
dpkg -i /tmp/splunk.deb

/opt/splunk/bin/splunk enable boot-start --accept-license --answer-yes --no-prompt --seed-passwd "$ADMIN_PASSWORD"

# Enable HEC and create token
/opt/splunk/bin/splunk http-event-collector enable -auth "admin:$${ADMIN_PASSWORD}"
/opt/splunk/bin/splunk http-event-collector create k8s-hec -uri https://localhost:8088 -disabled 0 -index main -auth "admin:$${ADMIN_PASSWORD}" || true

# Configure HEC token
cat <<EOF >/opt/splunk/etc/system/local/inputs.conf
[http://k8s-hec]
token = $${HEC_TOKEN}
index = main
disabled = 0
EOF

/opt/splunk/bin/splunk restart

# Install Fluent Bit
curl https://raw.githubusercontent.com/fluent/fluent-bit/master/install.sh | bash

cat <<EOF >/etc/fluent-bit/fluent-bit.conf
[SERVICE]
    Flush 1
    Daemon Off
    Log_Level info

[INPUT]
    Name tail
    Path /var/log/syslog
    Tag host.*

[OUTPUT]
    Name splunk
    Match host.*
    Host 127.0.0.1
    Port 8088
    Splunk_Token $${HEC_TOKEN}
    Splunk_Send_Raw On
    tls Off
EOF

systemctl restart fluent-bit || true
