#!/usr/bin/env python3

import json
import time
from os import environ
from typing import Literal

import requests
from loguru import logger
from pydantic import BaseModel

API_KEY = environ["HETZNER_DNS_API_KEY"]
DOMAIN = environ["DYNAMIC_DOMAIN"]
ORIGIN = "@"
WILDCARD = "*"
INTERVAL = int(environ.get("INTERVAL_SECONDS", 15 * 60))
READ_ONLY = False
DEFAULT_TTL = INTERVAL


class Zone(BaseModel):
    id: str
    name: str


class Record(BaseModel):
    zone: Zone
    name: str
    type: Literal["A", "NS", "SOA", "MX", "TXT", "SRV"]
    value: str
    ttl: int | None = DEFAULT_TTL
    id: str | None = None


def get_zones() -> list[Zone]:
    # Get Zones
    # GET https://dns.hetzner.com/api/v1/zones

    response = requests.get(
        url="https://dns.hetzner.com/api/v1/zones",
        headers={
            "Auth-API-Token": API_KEY,
        },
    )
    response.raise_for_status()
    for zone in response.json()["zones"]:
        yield Zone(**zone)


def get_records(zone: Zone) -> list[Record]:
    # Get Record
    # GET https://dns.hetzner.com/api/v1/records/{RecordID}

    response = requests.get(
        url="https://dns.hetzner.com/api/v1/records",
        params={
            "zone_id": zone.id,
        },
        headers={
            "Auth-API-Token": API_KEY,
        },
    )
    response.raise_for_status()
    for record in response.json()["records"]:
        yield Record(zone=zone, **record)


def create_record(record: Record):
    logger.info(f"Creating new record: {record}")
    response = requests.post(
        url="https://dns.hetzner.com/api/v1/records",
        headers={
            "Content-Type": "application/json",
            "Auth-API-Token": API_KEY,
        },
        data=json.dumps(
            {
                "value": record.value,
                "ttl": record.ttl,
                "type": record.type,
                "name": record.name,
                "zone_id": record.zone.id,
            }
        ),
    )


def update_record(record: Record, new_value: str):
    # Update Record
    # PUT https://dns.hetzner.com/api/v1/records/{RecordID}
    logger.info(f"Updating record {record} to value={new_value}")

    response = requests.put(
        url=f"https://dns.hetzner.com/api/v1/records/{record.id}",
        headers={
            "Content-Type": "application/json",
            "Auth-API-Token": API_KEY,
        },
        data=json.dumps(
            {
                "value": new_value,
                "ttl": record.ttl,
                "type": record.type,
                "name": record.name,
                "zone_id": record.zone.id,
            }
        ),
    )
    response.raise_for_status()


def get_my_ip():
    response = requests.get("https://ifconfig.me")
    response.raise_for_status()
    return response.text


def main(read_only=False):
    for zone in get_zones():
        logger.info(f"Zone {zone.id} name: {zone.name}")
        for record in get_records(zone):
            logger.info(f"\t{record.name} {record.ttl} IN {record.type} {record.value}")
        if zone.name == DOMAIN:
            if read_only:
                logger.info(f"R/O: doing nothing")
            else:
                create_record_for_my_ip(zone)


def create_record_for_my_ip(zone):
    my_ip = get_my_ip()
    new_wildcard_record = Record(zone=zone, name=WILDCARD, type="A", value=my_ip)
    create_record(new_wildcard_record)
    new_origin_record = Record(zone=zone, name=ORIGIN, type="A", value=my_ip)
    create_record(new_origin_record)


if __name__ == "__main__":
    logger.info("Starting script")
    # TODO: ratelimit
    while True:
        try:
            main(read_only=READ_ONLY)
        except:
            logger.exception("Unhandled exception")
        logger.info(f"Sleep for {INTERVAL} seconds")
        time.sleep(INTERVAL)
