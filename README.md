[![ghcr.io release](https://img.shields.io/github/v/release/ekamil/hetzner-dyndns?label=latest%20version&style=for-the-badge)](https://github.com/ekamil/hetzner-dyndns/pkgs/container/traefik-home/versions)

## Usage

```
docker run --name hetzner-dyndns \
    ghcr.io/ekamil/hetzner-dyndns:latest
```

### Docker compose
```yaml
version: '3'

services:
  hetzner-dyndns:
    image: ghcr.io/ekamil/hetzner-dyndns:latest  # or use a specific tag version
    container_name: hetzner-dyndns

```
