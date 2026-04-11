# PR Description

## Summary

This PR syncs the fork to upstream `v9.0.4` and keeps the local custom deployment features used in production.

## Upstream base

- Upstream repo: `wenfxl/openai-cpa`
- Upstream version merged: `v9.0.4`

## Custom changes preserved in this fork

### 1. LuckMail imported mailbox mode

- support for using user-uploaded LuckMail mailbox pool
- support for `specified_email`
- OTP retrieval via order flow instead of purchase token flow when imported-pool mode is enabled

### 2. HTTP dynamic proxy pool

- supports one or more dynamic HTTP proxy gateways
- queue-based multi-thread dispatch
- intended for providers that rotate IP by request / connection

### 3. HeroSMS fixes

- HeroSMS API can bypass the global registration proxy
- balance / prices panel remains usable under unstable registration proxies

### 4. Telegram fixes

- direct-send mode by default
- separate Telegram `use_proxy` toggle
- improved success / stop templates
- stop-template variable rendering fixed

### 5. Clash subscription self-service

- Web UI can update Clash subscription URL
- Web UI can trigger pool refresh script
- Web UI can read back actual detected strategy groups
- Clash strategy group field can be selected from a dropdown after refresh

## Operational notes

- app path: `/opt/openai-cpa`
- clash pool path: `/opt/mihomo-pool`
- app container mounts:
  - `/opt/openai-cpa/data:/app/data`
  - `/opt/mihomo-pool:/opt/mihomo-pool`
  - `/var/run/docker.sock:/var/run/docker.sock`
  - `/usr/bin/docker:/usr/local/bin/docker:ro`

## Suggested target branches

- release branch: `release/bfansye-custom-v9.0.4`
- long-term working branch: `main-bfansye`
