# Cassandra Ansible roles

## os-setup

This role contains all the production recommended Linux configurations for Apache Cassandra.
Things like disabling swap, setting proper ulimits, and sysctl settings.

## cassandra

This role installs and starts Apache Cassandra. It can been run against one or multiple nodes just be sure to override the default variables such as cassandra_seeds as appropriate when using with multitple nodes. It's been tested to work with Amazon Linux and should work with any other RHEL derivative. 

## cassandra-exporter

This role can be run against a Apache Cassandra cluster to install and configure the [Prometheus JMX exporter](https://github.com/prometheus/jmx_exporter). It will restart Cassandra so be sure to use caution when using with production clusters.


