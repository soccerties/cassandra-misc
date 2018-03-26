# Misc tools to use with Apache Cassandra

This repository contains miscellaneous items I've put together while working with Apache Cassandra.

## Ansible

Under the Ansible directory you can find playbooks and roles for building clusters and performing common operational tasks.

## Terraform

Coming soon

## cassandra-tracing-indexer.py

This script will select tracing data from the system_traces keyspace and index them into ElasticSearch for anaylysis. It works with ElasticSearch 5.x and indexes with two doc types: sessions and events as child items of sessions. It attempts to parse the CQL statements and index things like table of the query, columns involved, query type, etc. The parsing is not absolutely robust and will likely need tweaks to parse your queries. Before executing be sure to disable settraceprobability in Cassandra. If tracing is still enabled Cassandra will trace the scripts activity and the script will index it's own queries.


