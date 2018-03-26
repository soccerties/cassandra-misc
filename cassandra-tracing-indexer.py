#!/usr/bin/env python
from cassandra.cluster import Cluster
from cassandra.util import datetime_from_uuid1
from cassandra.query import dict_factory
from elasticsearch5 import helpers, Elasticsearch
import csv
import time
import json
import sys
import sqlparse
import argparse
import datetime
import logging
import uuid

parser = argparse.ArgumentParser(description="This script selects tracing data from a Cassandra cluster and indexes the data into ElasticSearch")

parser.add_argument('-c', '--cluster', help="string of Cassandra hosts to connect to separated by commas", default="locahost")
parser.add_argument('-e', '--elasticsearch', help="elasticsearch host to send indexes to", default="localhost")
parser.add_argument('-i', '--index', help="The elasticsearch index name.", default="cassandra-tracing")
parser.add_argument('-b', '--batch_size', help="batch size to query cassandra and index into elasticsearch at a time", default=1000, type=int)
parser.add_argument('-n', '--cluster_name', help="Cassandra cluster name to index with. Default is cluster name connected to with -c")
parser.add_argument('-v', '--verbose', help="enable verbose logging output", action="store_true")

args = parser.parse_args()

class Trace_loader:

    c_events_query_str = "SELECT session_id, event_id, activity, source, source_elapsed, thread, unixTimestampOf(event_id) as started_at FROM events"
    c_sessions_query_str = "SELECT * from sessions"

    time_pattern = '%Y-%m-%d %H:%M:%S'

    es_session_doc_type = 'session'
    es_event_doc_type = 'event'

    epoch = datetime.datetime.utcfromtimestamp(0) #for conversion to UTC timestamp ms

    def __init__(self, args):
        self.args = args

        if self.args.verbose:
            log_level = logging.DEBUG
        else:
            log_level = logging.INFO

        self.l = logging.getLogger()
        self.l.setLevel(log_level)
        o_h = logging.StreamHandler(sys.stdout)
        self.l.addHandler(o_h)

        self.l.debug(self.args)

        self.es_url = 'http://'+args.elasticsearch+':9200'
        self.es = Elasticsearch(self.es_url)
        self.es_index_name = self.args.index

        self.setup_cassandra()

        if self.args.cluster_name is None:
            self.cluster_name = self.cassandra_session.cluster.metadata.cluster_name
        else:
            self.cluster_name = self.args.cluster_name

        self.setup_elasticsearch()

        self.process_traces()

    def setup_cassandra(self):
        self.c = Cluster(self.args.cluster.split(','), control_connection_timeout=None)
        self.cassandra_session = self.c.connect()
        self.cassandra_session.default_fetch_size = self.args.batch_size
        self.cassandra_session.row_factory = dict_factory
        self.cassandra_session.set_keyspace('system_traces')
        self.cassandra_events_stmt = self.cassandra_session.prepare(self.c_events_query_str)
        self.cassandra_sessions_stmt = self.cassandra_session.prepare(self.c_sessions_query_str)

    def setup_elasticsearch(self):
        self.es_url = 'http://' + self.args.elasticsearch + ':9200'
        self.es = Elasticsearch(self.es_url)

        try:
            self.create_index()
        except:

            pass

    def merge_two_dicts(self, x, y):
        z = x.copy()   # start with x's keys and values
        z.update(y)    # modifies z with y's keys and values & returns None
        return z

    def process_traces(self):
        self.process_sessions()
        self.process_events()

    def process_sessions(self):
        sessions = self.cassandra_session.execute(self.cassandra_sessions_stmt)
        counter = 0
        batch = []
        for s in sessions:
            self.l.debug("processing "+str(s))
            if s['coordinator'] is not None:  # filter out empty traces
                if s['request'] == 'Execute batch of CQL3 queries':
                    s['query_type'] = 'BATCH'
                else:
                    params = self.parse_params(s['parameters'])

                es_data = self.merge_two_dicts(params, s)

                es_data.pop('parameters', None)

                es_data['session_id'] = str(es_data['session_id'])
                es_data['cluster'] = self.cluster_name

                batch.append({
                    '_index': self.es_index_name,
                    '_type': self.es_session_doc_type,
                    '_id': es_data['session_id'],
                    '_source': es_data
                })

                if len(batch) >= self.args.batch_size:
                    counter = counter + 1
                    print(counter, batch[0])

                    helpers.bulk(self.es, batch)
                    batch = []
    # this isn't used but leaving here as it's usefull if csv import is only option
    def process_sessions_csv(self, filename):
        with open(filename) as f:
            sessions = csv.DictReader(f)
            counter = 0
            batch = []
            for s in sessions:
                self.l.debug("processing "+str(s))
                if s['coordinator'] is not None and s['coordinator'] is not '' and s['parameters'] is not '':  # filter out empty traces
                    if s['request'] == 'Execute batch of CQL3 queries':
                        s['query_type'] = 'BATCH'
                    else:
                        params_no_single = s['parameters'].replace("'",'"')
                        #params_escape_double = s['parameters'].replace('""','\\"')
                        try:
                            params_json = json.loads(params_no_single)
                            params = self.parse_params(params_json)
                        except:
                            continue

                    es_data = self.merge_two_dicts(params, s)

                    es_data.pop('parameters', None)

                    my_dt = datetime.datetime.strptime(es_data['started_at'][:-5], "%Y-%m-%d %H:%M:%S")
                    es_data['started_at'] = my_dt



                    es_data['session_id'] = str(es_data['session_id'])
                    es_data['cluster'] = self.cluster_name

                    batch.append({
                        '_index': self.es_index_name,
                        '_type': self.es_session_doc_type,
                        '_id': es_data['session_id'],
                        '_source': es_data
                    })

                    if len(batch) >= self.args.batch_size:
                        counter = counter + 1
                        print(counter, batch[0])

                        helpers.bulk(self.es, batch)
                        batch = []


    def process_events(self):
        events = self.cassandra_session.execute(self.cassandra_events_stmt)
        counter = 0
        batch = []
        for row in events:
            # add cluster name to doc
            row['cluster'] = self.cluster_name

            batch.append({
                '_index': self.es_index_name,
                '_type': self.es_event_doc_type,
                '_parent': row['session_id'],
                '_routing': row['session_id'],
                '_id': row['event_id'],
                '_source': row
            })

            if len(batch) >= self.args.batch_size:
                counter = counter + 1
                r = helpers.bulk(self.es, batch)
                print(counter, r)
                batch = []

    # this isn't used but leaving here as it's usefull if csv import is only option
    def process_events_csv(self, filename):
        with open(filename) as f:
            csvreader = csv.DictReader(f)
            counter = 0
            batch = []
            for row in csvreader:
                # extract time from UUID for indexing
                event_uuid = uuid.UUID(row['event_id'])
                event_dt = datetime_from_uuid1(event_uuid)
                #row['started_at'] = event_dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                row['started_at'] = datetime_from_uuid1(event_uuid)

                # add cluster name to doc
                row['cluster'] = self.cluster_name

                batch.append({
                    '_index': self.es_index_name,
                    '_type': self.es_event_doc_type,
                    '_parent': row['session_id'],
                    '_routing': row['session_id'],
                    '_id': row['event_id'],
                    '_source': row
                })

                if len(batch) >= self.args.batch_size:
                    counter = counter + 1
                    r = helpers.bulk(self.es, batch)
                    print(counter, r)
                    batch = []

    def create_index(self):
        schema = {
            "settings": {
                "index.mapping.total_fields.limit": 2000,
                "number_of_shards": 1,
                "number_of_replicas": 0
            },
            "mappings": {
                self.es_session_doc_type: {
                    "_source":    {"enabled": True},
                    "properties": {
                        "query_type":        {"type": "keyword"},
                        "columns":           {"type": "keyword"},
                        "table":             {"type": "keyword"},
                        "where":             {"type": "text"},
                        "consistency_level": {"type": "keyword"},
                        "query":             {"type": "text"},
                        "page_size":         {"type": "integer"},
                        "coordinator":       {"type": "keyword"},
                        "session_id":        {"type": "keyword"},
                        "duration":          {"type": "integer"},
                        "request":           {"type": "keyword"},
                        "cluster":           {"type": "keyword"},
                        "started_at":        {"type": "date",
                                              "format": "strict_date_optional_time||epoch_millis"},

                    },
                },
                self.es_event_doc_type: {
                    "_source": {"enabled": True},
                    "_parent": {
                        "type": self.es_session_doc_type
                    },
                    "properties": {
                        "source_elapsed" : {"type": "integer"},
                        "started_at"        : {"type": "date",
                                            "format": "strict_date_optional_time||epoch_millis"}
                    }
                }
            },
            "refresh": True
        }

        self.es.indices.create(index=self.es_index_name,body=json.dumps(schema))

    def delete_index(self, index_name):
        self.es.indices.delete(index=index_name)

    def index_doc(doc, id, doc_type=es_session_doc_type, routing=None):

        res = es.index(index=self.es_index_name,
                       doc_type=doc_type,
                       id=id,
                       body=doc,
                       routing=routing)
        print(res['created'])

    def parse_params(self, params):

        if 'query' in params:
            s = sqlparse.parse(params['query'])[0]
            if s.get_type() == "SELECT":
                cql = {
                    'query_type': s.get_type(),
                    'columns': s.tokens[2].value.split(','),
                    'table': s.tokens[6].value,
                    'where': s.tokens[-1].value[6:-1]
                }
            elif s.get_type() == "UPDATE":
                cql = {
                    'query_type': s.get_type(),
                    #'columns': '',
                    'table': s.tokens[2].value,
                    'where': s.tokens[-1].value[6:-1]
                }
            elif s.get_type() == "INSERT":
                cql = {
                    'query_type': s.get_type(),
                    #'table': s.tokens[4].tokens[0].value
                }
                #if s.tokens[4].tokens[1].is_whitespace:
                    #cql['columns'] = s.tokens[4].tokens[2].tokens[1].value.split(',')
                #    pass
                #else:
                    #cql['columns'] = s.tokens[4].tokens[1].tokens[1].value.split(',')
                #    pass
            elif s.get_type() == "DELETE":
                cql = {
                    'query_type': s.get_type(),
                    'table': s.tokens[4].normalized
                }
            else:
                cql = {
                    'query_type': s.get_type(),
                }
        else:
            cql = {
                'query_type': 'UNKNOWN'
            }

        result = self.merge_two_dicts(cql, params)
        return result

# start instance if called directly
if __name__ == "__main__":
    Trace_loader(args)
