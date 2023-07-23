[![ghcr.io release](https://img.shields.io/github/v/release/ekamil/hetzner-dyndns?label=latest%20version&style=for-the-badge)](https://github.com/ekamil/hetzner-dyndns/pkgs/container/hetzner-dyndns/versions)

## Usage

```
docker run --name hetzner-dyndns \
    -e HETZNER_DNS_API_KEY=CHANGE_ME \
    -e DYNAMIC_DOMAIN=CHANGE_ME \
    -e INTERVAL_SECONDS=900 \
    ghcr.io/ekamil/hetzner-dyndns:latest
```
