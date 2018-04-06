## example-playbook.yml
This playbook is an example of using the roles to setup and configure Cassandra

## rolling-restart.yml
Sometimes Cassandra gets in an unstable state. For example if there's a schema disagreement that can't be reset.
And the only way to solve the issue is restarting all the nodes in a cluster.
This playbook goes through an entire cluster, one by one, gracefully stopping and restarting the Cassandra service.

## upgrade-cassandra.yml
This playbook is an example of performing a cluster upgrade. It upgrades nodes following the recommended procedure.
It uses the serial Ansible option to upgrade each node, one at a time.
