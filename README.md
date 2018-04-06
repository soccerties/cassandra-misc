# Misc tools to use with Apache Cassandra

This repository contains miscellaneous items I've put together while working with Apache Cassandra.

## Ansible

Under the Ansible directory you can find playbooks and roles for building clusters and performing common operational tasks.

## Terraform

Coming soon

## cassandra-tracing-indexer.py

This script will select tracing data from the system_traces keyspace and index them into ElasticSearch for anaylysis. It works with ElasticSearch 5.x and indexes with two doc types: sessions and events as child items of sessions. It attempts to parse the CQL statements and index things like table of the query, columns involved, query type, etc. The parsing is not absolutely robust and will likely need tweaks to parse your queries. Before executing be sure to disable settraceprobability in Cassandra. If tracing is still enabled Cassandra will trace the scripts activity and the script will index it's own queries.

## cassandra-keygen.sh

Need to setup TLS on your Cassandra Cluster? Use this script to generate your certificates and keystores using a self signed Certificate Authority. Pass in your nodes as command line parameters separated by spaces.
The script will prompt for confirmation before overwriting any files and can be executed multiple times.

First edit the script and provide values appropriate for your environment.
```
OUTPUT_DIR="./keys"
# Password to unlock CA key
CA_OUT_PASSWORD="1234"
# Password to unlock node keystore and private key
KEYSTORE_PASS="keypass"
# Password for CA cert truststore to validate certs
TRUSTSTORE_PASS="trustpass"
CERT_VALIDITY=1095 # in days
CA_VALIDITY=1095   # in days
ROOT_CN="ABC-rootCA"
CERT_OU="Cassandra"
CERT_O="ABC-Company"
CERT_C="US"
KEYSIZE=2048
```
Then execute the script.
```
cassandra-keygen.s 192.168.0.101 192.168.0.102 192.168.0.103
```
