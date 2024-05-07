#!/bin/sh

python hetzner-domain.py loop $DYNAMIC_DOMAINS --interval=${INTERVAL_SECONDS:-900}
