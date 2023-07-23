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
WILDCARD = "*"
INTERVAL = 15  # * 60  # seconds
READ_ONLY = False


class Zone(BaseModel):
    id: str
    name: str


class Record(BaseModel):
    zone: Zone
    name: str
    type: Literal["A", "NS", "SOA", "MX", "TXT", "SRV"]
    value: str
    ttl: int | None = 7200
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
        can_update_record = None
        for record in get_records(zone):
            logger.info(f"\t{record.name} {record.ttl} IN {record.type} {record.value}")
            if zone.name == DOMAIN and record.name == WILDCARD:
                can_update_record = record
        if zone.name == DOMAIN:
            if read_only:
                logger.info(f"R/O: existing record: {can_update_record} ")
                return
            my_ip = get_my_ip()
            if can_update_record:
                update_record(can_update_record, my_ip)
            else:
                create_record(Record(zone=zone, name=WILDCARD, type="A", value=my_ip))


if __name__ == "__main__":
    logger.info("Starting script")
    while True:
        main(read_only=READ_ONLY)
        logger.info(f"Sleep for {INTERVAL} seconds")
        time.sleep(INTERVAL)
