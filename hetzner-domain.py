#!/usr/bin/env python3
"""
Single domain script:
hetzner-domain.py --help
"""
import json
import time
from os import environ
from typing import Literal, Any
import enum

import click
import requests
from loguru import logger
from pydantic import BaseModel

API_KEY = environ["HETZNER_DNS_API_KEY"]

INTERVAL = DEFAULT_TTL = 15 * 60

ORIGIN = "@"
WILDCARD = "*"


class Op(enum.StrEnum):
    add = enum.auto()
    add_for_ip = enum.auto()
    delete = enum.auto()
    list = enum.auto()
    loop = enum.auto()


class Zone(BaseModel):
    id: str
    name: str


class RecordType(enum.StrEnum):
    A = "A"
    NS = "NS"
    SOA = "SOA"
    MX = "MX"
    TXT = "TXT"
    SRV = "SRV"


class Record(BaseModel):
    zone: Zone
    name: str
    type: RecordType | str = RecordType.A
    value: Literal["@"] | Literal["*"] | str | None = None
    ttl: int | None = DEFAULT_TTL
    id: str | None = None

    def model_post_init(self, __context: Any) -> None:
        self.name = self.name.removesuffix(f".{self.zone.name}")


def get_zones(*, api_key: str = API_KEY) -> list[Zone]:
    # Get Zones
    # GET https://dns.hetzner.com/api/v1/zones
    response = requests.get(
        url="https://dns.hetzner.com/api/v1/zones",
        headers={
            "Auth-API-Token": api_key,
        },
    )
    response.raise_for_status()
    for zone in response.json()["zones"]:
        yield Zone(id=zone["id"], name=zone["name"])


def _create_record(record: Record, *, api_key: str = API_KEY) -> bool:
    logger.info(f"Creating new record: {record}")
    response = requests.post(
        url="https://dns.hetzner.com/api/v1/records",
        headers={
            "Content-Type": "application/json",
            "Auth-API-Token": api_key,
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
    match response.status_code:
        case 200:
            logger.info(f"Success")
            return True
        case 422:
            logger.info(f"Duplicate found for record {record}")
            logger.info(f"Response {response.status_code} {response.text}")
            return False
        case _:
            logger.info(f"Response {response.status_code} {response.text}")
            response.raise_for_status()


def _delete_record(record: Record, *, api_key: str = API_KEY) -> bool:
    # Delete Record
    # DELETE https://dns.hetzner.com/api/v1/records/{RecordID}
    logger.info(f"Deleting record {record}")

    response = requests.delete(
        url=f"https://dns.hetzner.com/api/v1/records/{record.id}",
        headers={
            "Content-Type": "application/json",
            "Auth-API-Token": api_key,
        },
    )
    match response.status_code:
        case 200:
            logger.info(f"Success")
            return True
        case 404:
            logger.info(f"Domain not found {record}")
            logger.info(f"Response {response.status_code} {response.text}")
            return False
        case _:
            logger.info(f"Response {response.status_code} {response.text}")
            response.raise_for_status()


def _get_records(zone: Zone, *, api_key: str = API_KEY) -> list[Record]:
    # Get Record
    # GET https://dns.hetzner.com/api/v1/records/{RecordID}

    response = requests.get(
        url="https://dns.hetzner.com/api/v1/records",
        params={
            "zone_id": zone.id,
        },
        headers={
            "Auth-API-Token": api_key,
        },
    )
    response.raise_for_status()
    for record in response.json()["records"]:
        yield Record(zone=zone, **record)


def _get_zone_for_domain(
    zone_or_domain: Zone | str, *, api_key: str = API_KEY
) -> Zone | None:
    if isinstance(zone_or_domain, Zone):
        return zone_or_domain
    for zone in get_zones(api_key=api_key):
        if zone_or_domain.endswith(zone.name):
            return zone
    logger.warning(f"Zone for domain {zone_or_domain} not found")


def _get_my_ip():
    logger.debug("Getting current ip")
    response = requests.get("https://ifconfig.me")
    response.raise_for_status()
    return response.text


def _create_records_for_my_ip(
    zone_or_domain: Zone | str, *, api_key: str = API_KEY
) -> None:
    match zone_or_domain:
        case Zone():
            zone = zone_or_domain
        case str():
            logger.info(f"Fetching zone for name {zone_or_domain}")
            zone = _get_zone_for_domain(zone_or_domain, api_key=api_key)
            if not zone:
                raise ValueError(f"Zone {zone_or_domain} not found")
        case _:
            raise ValueError(f"Invalid zone {zone_or_domain}")
    logger.info(f"Updating wildcard records for domain {zone_or_domain}")
    my_ip = _get_my_ip()
    logger.info(f"IP address: {my_ip}")
    deleted = []
    created = []
    kept = []
    if zone_or_domain == zone.name:
        record_names = (WILDCARD, ORIGIN)
    else:
        _prefix = zone_or_domain.removesuffix(zone.name).removesuffix(".")
        record_names = (f"{WILDCARD}.{_prefix}", f"{_prefix}")
    logger.warning(record_names)
    for record in _get_records(zone, api_key=api_key):
        if record.type != "A":
            continue
        for name in record_names:
            if record.name == name:
                if record.value == my_ip:
                    kept.append(name)
                else:
                    _delete_record(record, api_key=api_key)
                    deleted.append(name)
    for name in record_names:
        if name in kept:
            continue
        new_record = Record(zone=zone, name=name, type=RecordType.A, value=my_ip)
        _create_record(new_record, api_key=api_key)
        created.append(new_record)
    logger.info("Deleted {} records".format(deleted))
    logger.info("Created {} records".format(created))
    logger.info("Kept as-is {} records".format(kept))


@click.group()
def cli() -> None:
    """
    Helper for ACME flow with Hetzner
    """


@cli.command()
@click.argument("domain")
@click.argument("record_type", default=RecordType.A)
@click.argument("value", default="IP")
@click.option("--ttl", default=DEFAULT_TTL)
def add_domain(
    domain: str,
    record_type: RecordType,
    value: str | Literal["IP"],
    ttl: int = DEFAULT_TTL,
    *,
    api_key: str = API_KEY,
) -> None:
    if value == "IP":
        value = _get_my_ip()
        logger.info(
            f"Adding domain: {domain}, Type: {record_type}, Value: {value} (current IP)"
        )
    else:
        logger.info(f"Adding domain: {domain}, Type: {record_type}, Value: {value}")
    zone = _get_zone_for_domain(domain, api_key=api_key)
    if not zone:
        click.echo(f"Zone not found for {domain}", err=True)
        return
    record = Record(zone=zone, name=domain, type=record_type, value=value, ttl=ttl)
    _create_record(record, api_key=api_key)


@cli.command()
@click.argument("domain")
@click.argument("record_type")
def delete_domain(
    domain: str, record_type: RecordType, *, api_key: str = API_KEY
) -> None:
    logger.info(f"Deleting domain: {domain}")
    zone = _get_zone_for_domain(domain, api_key=api_key)
    deleted = 0
    is_origin = domain == f"{ORIGIN}.{zone.name}"
    is_wildcard = domain == f"{WILDCARD}.{zone.name}" and not is_origin
    is_non_special = not is_wildcard and not is_origin
    for record in _get_records(zone, api_key=api_key):
        if record.type != record_type:
            continue
        do_delete = False
        if is_non_special and record.name == domain:
            do_delete = True
        elif is_origin and record.name == ORIGIN:
            logger.info(f"Removing ORIGIN entry {record}")
            do_delete = True
        elif is_wildcard and record.name == WILDCARD:
            logger.info(f"Removing WILDCARD entry {record}")
            do_delete = True
        if do_delete:
            _delete_record(record, api_key=api_key)
            deleted += 1
            continue
    logger.info("Deleted {} records".format(deleted))


@cli.command()
def list_domains(*, api_key: str = API_KEY) -> None:
    logger.info(f"Listing records")
    for zone in get_zones(api_key=api_key):
        logger.info(f"Zone: {zone.name}")
        for record in _get_records(zone, api_key=api_key):
            logger.info(f"\tRecord: {record.name} {record.type} {record.value}")


@cli.command()
@click.argument("domain")
def list_records(domain: Zone | str, *, api_key: str = API_KEY) -> None:
    zone = _get_zone_for_domain(domain)
    logger.info(f"Zone: {zone.name}")
    for record in _get_records(zone, api_key=api_key):
        logger.info(f"\tRecord: {record.name} {record.type} {record.value}")


@cli.command()
@click.argument("domain")
def create_records_for_my_ip(
    zone_or_domain: Zone | str, *, api_key: str = API_KEY
) -> None:
    _create_records_for_my_ip(zone_or_domain, api_key=api_key)


@cli.command()
@click.argument("domains")
@click.option("--interval", default=INTERVAL)
def loop(domains: str, interval: int = INTERVAL, *, api_key: str = API_KEY) -> None:
    """
    Start a while loop and update DOMAINS to a current external IP address periodically
        DOMAINS is a comma-separated list of domains to upgrade
    """
    logger.info(f"Starting loop over {domains} with interval of {INTERVAL} seconds")
    while True:
        for domain in domains.split(","):
            try:
                _create_records_for_my_ip(domain, api_key=api_key)
            except Exception as e:
                logger.exception(f"Unhandled exception {e}")
        logger.info(f"Sleep for {interval} seconds")
        time.sleep(interval)


if __name__ == "__main__":
    cli()
