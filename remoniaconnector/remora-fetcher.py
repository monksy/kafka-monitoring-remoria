#!/usr/bin/env python

import argparse
import json
import logging
import sys
import time

import requests

"""
Fetches events from Remora and ingests into KairosDB.
"""

#From https://github.com/imduffy15/remora-fetcher

KAIROS_WRITE_PATH = "/api/v1/datapoints"


def sum_lag(consumer_group_name, consumer_group_data):
    metrics = {}

    for partition in consumer_group_data['partition_assignment']:
        if {'topic', 'lag'} <= partition.keys():
            metrics[partition['topic']] = metrics.get(
                partition['topic'], 0) + partition.get('lag', 0)

    results = []
    for topic, lag in metrics.items():
        results.append((consumer_group_name, topic, lag))

    return results


def push_data(kairosdb_api, consumer_group_lag):
    for (consumer_group_name, topic, lag) in consumer_group_lag:
        metric = {
            "name": consumer_group_name,
            "timestamp": int(round(time.time() * 1000)),
            "value": lag,
            "tags": {
                "topic": topic
            }
        }
        logging.info(
            "pushing information for consumer group %s, topic %s with value %s" % (consumer_group_name, topic, lag))

        kairosdb_url = "".join([kairosdb_api, KAIROS_WRITE_PATH])
        res = requests.post(kairosdb_url, json.dumps(metric))
        logging.debug(res.text)


def ingest(remora_api, kairosdb_api):
    logging.info("Fetching events from Remora")

    consumer_groups_url = "".join([remora_api, "/consumers"])
    consumer_groups = requests.get(consumer_groups_url).json()

    logging.info("Got %s consumer groups" % (", ".join(consumer_groups)))

    for consumer_group_name in consumer_groups:
        logging.info("querying %s" % consumer_group_name)

        consumer_group_data_url = "".join(
            [remora_api, "/consumers/", consumer_group_name])
        consumer_group_data = requests.get(consumer_group_data_url).json()

        push_data(kairosdb_api, sum_lag(
            consumer_group_name, consumer_group_data))


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(
            description="Fetches events from Remora and ingests it into KairosDB.",
            epilog="Example: remora-fetcher.py -r http://52.11.127.207:9000")

        parser.add_argument("-k", action="store", dest="kairosdb_api", default="http://localhost:8080",
                            help="The URL of the KairosDB API, the default is `http://localhost:8080`")

        parser.add_argument("-r", action="store", dest="remora_api", default="http://localhost:9000",
                            help="The URL of the Remora API, the default is `http://localhost:9000`")

        parser.add_argument("-p", action="store", dest="poll_interval", default=10,
                            type=int, help="The poll interval in seconds, the default is 10")

        parser.add_argument("-d", action="store_true", dest="enable_debug",
                            default=False, help="Enables debug messages")

        args = parser.parse_args()

        if args.enable_debug:
            FORMAT = "%(asctime)-0s %(levelname)s %(message)s [at line %(lineno)d]"
            logging.basicConfig(level=logging.DEBUG,
                                format=FORMAT, datefmt="%Y-%m-%dT%I:%M:%S")
        else:
            FORMAT = "%(asctime)-0s %(message)s"
            logging.basicConfig(level=logging.INFO,
                                format=FORMAT, datefmt="%Y-%m-%dT%I:%M:%S")
            logging.getLogger("requests").setLevel(logging.WARNING)
        logging.debug("Arguments %s" % args)

        while True:
            ingest(args.remora_api, args.kairosdb_api)
            time.sleep(args.poll_interval)

    except Exception as e:
        logging.error(e)
        sys.exit(1)
