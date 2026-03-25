# Email OTP Retrieval & Mailbox Integration Utility

A Python utility for mailbox integration, one-time passcode (OTP) retrieval, message parsing, proxy-aware email polling, local JSON backup, optional Clash proxy rotation, and optional internal credential-file inventory checks.

> Use only in systems and environments you own or are explicitly authorized to test.
> Make sure your use complies with applicable laws, platform rules, and service terms.

## ✨ Features

#### Flexible mailbox and verification workflow
- **Multi-backend mailbox support**: Natively supports `cloudflare_temp_email`, `freemail`, and standard `imap` mailbox backends, with flexible switching through the configuration file.
- **Dual-path domain rotation**: Supports custom multi-domain pools defined in configuration for randomized distribution; in `freemail` mode, it can also dynamically fetch available domains from the API and rotate among them automatically.
- **OTP polling and extraction**: Automatically polls mailbox content and extracts 6-digit OTP codes from subject lines, message bodies, HTML content, or raw email payloads.
- **Robust email parsing**: Includes MIME header decoding, HTML-to-text conversion, raw mail parsing, and common encoding compatibility handling.

#### Proxy management and network resilience
- **Clash proxy rotation support**: Supports automatic outbound node switching through Clash External Controller APIs. When enabled, the workflow rotates nodes before each registration task, applies blacklist-based filtering, and verifies connectivity after switching.
- **Flexible network routing**: Supports a global proxy configuration and allows separate proxy behavior for mailbox API requests or IMAP connections to adapt to different network environments.
- **Region-aware proxy validation**: Tests outbound connectivity and can skip blocked or unsuitable regions such as `CN` / `HK` after node switching.
- **Retry handling for unstable networks**: Provides basic anti-jitter and timeout retry handling at key network request points to improve stability in unattended or unstable network scenarios.

#### CPA inventory maintenance and operations
- **Automated inventory inspection**: Provides an optional CPA maintenance mode that periodically checks account inventory in the CPA system and performs health and availability inspection.
- **Invalid credential cleanup**: Supports a configurable weekly quota threshold. When an account is identified as exhausted, deactivated, or invalid, it can be removed from inventory automatically.
- **Low-inventory replenishment**: Monitors effective account inventory in the CPA system and can trigger a preset replenishment batch when stock drops below the configured safety threshold.
- **Credential renewal support**: When stored credentials are approaching expiration or have become invalid, the system can attempt refresh-based renewal and update the stored credential set.

#### Archival output and privacy protection
- **Controllable local archival**: In standard mode, JSON credentials and `accounts.txt` records can be stored locally by default. In CPA replenishment mode, the separate `save_to_local` switch lets you decide whether to retain a local backup while uploading remotely.
- **CPA API upload integration**: Supports automatically pushing newly generated JSON credentials or refreshed valid credentials to the CPA internal API for centralized storage and retrieval.
- **Log privacy masking**: Includes built-in masking for mailbox domain output in standard console logs to reduce direct exposure of sensitive information.
- **Centralized YAML configuration**: Core runtime behavior—including proxy settings, retry counts, mailbox mode, output directory, Clash proxy rotation, and CPA inspection / backup parameters—is controlled through a single YAML configuration file.

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
  - [1. `email_api_mode`](#1-email_api_mode)
  - [2. `mail_domains`](#2-mail_domains)
  - [3. `gptmail_base`](#3-gptmail_base)
  - [4. `default_proxy`](#4-default_proxy)
  - [5. `clash_proxy_pool`](#5-clash_proxy_pool)
  - [6. `imap`](#6-imap)
  - [7. `freemail`](#7-freemail)
  - [8. `admin_auth`](#8-admin_auth)
  - [9. `max_otp_retries`](#9-max_otp_retries)
  - [10. `use_proxy_for_email`](#10-use_proxy_for_email)
  - [11. `enable_email_masking`](#11-enable_email_masking)
  - [12. `token_output_dir`](#12-token_output_dir)
  - [13. `cpa_mode`](#13-cpa_mode)
  - [14. `normal_mode`](#14-normal_mode)
  - [15. Configuration suggestions](#15-configuration-suggestions)
- [Usage](#usage)
- [Output Files](#output-files)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)

## Requirements

- Python 3.10+
- `PyYAML`
- `curl_cffi`
- `PySocks` (only needed if you want IMAP connections to go through a proxy)
- `requests` (used by `proxy_manager.py` for Clash controller access and proxy liveness checks)

## Installation

Install required packages:

```bash
pip install PyYAML PySocks curl_cffi requests
```

## Configuration

The project uses `config.yaml` in the repository root as the single configuration entry point.

A typical configuration looks like this:

```yaml
# [Mail backend mode]
# Available values: "imap" / "freemail" / "cloudflare_temp_email"
email_api_mode: "cloudflare_temp_email"

# [Shared settings for cloudflare_temp_email / imap]
mail_domains: "domain1.com,domain2.xyz,domain3.net"
gptmail_base: "https://your-domain.com"

# [Proxy configuration]
default_proxy: "http://127.0.0.1:7897"

# [Clash proxy rotation]
clash_proxy_pool:
  enable: false
  api_url: "http://127.0.0.1:9097"
  group_name: "节点选择"
  secret: "set-your-secret"
  test_proxy_url: "http://127.0.0.1:7897"
  blacklist:
    - "自动"
    - "故障"
    - "剩余"
    - "到期"
    - "官网"
    - "Traffic"
    - "DIRECT"
    - "REJECT"
    - "港"
    - "HK"
    - "Hongkong"
    - "台"
    - "TW"
    - "Taiwan"
    - "中"
    - "CN"
    - "China"
    - "回国"

# [Mode-specific settings: imap]
imap:
  server: "imap.gmail.com"
  port: 993
  user: ""
  pass: ""

# [Mode-specific settings: freemail]
freemail:
  api_url: "https://your-domain.com"
  api_token: ""

# [Mode-specific settings: cloudflare_temp_email]
admin_auth: ""

# [OTP resend retries]
max_otp_retries: 5

# [Mail-side proxy options]
use_proxy_for_email: false
enable_email_masking: true

# [Local output directory]
token_output_dir: ""

# [CPA maintenance mode]
cpa_mode:
  enable: false
  save_to_local: true
  api_url: "http://your-domain.com:8317"
  api_token: "xxxx"
  min_accounts_threshold: 30
  batch_reg_count: 1
  min_remaining_weekly_percent: 80
  check_interval_minutes: 60

# [Standard loop mode]
normal_mode:
  sleep_min: 5
  sleep_max: 30
```

### 1. `email_api_mode`

Selects which mailbox backend mode to use. Supported values:

- `cloudflare_temp_email`
- `freemail`
- `imap`

Mode summary:

- **`cloudflare_temp_email`**: Uses a temp-mail style backend and requires `gptmail_base` plus `admin_auth`
- **`freemail`**: Uses a Freemail-compatible API and requires `freemail.api_url` plus `freemail.api_token`
- **`imap`**: Uses a real mailbox over IMAP and requires `imap.server / port / user / pass`

### 2. `mail_domains`

Defines the mailbox domain pool. Multiple domains can be separated with commas.

Example:

```yaml
mail_domains: "a.com,b.net,c.org"
```

The script generates mailbox addresses using a random prefix plus a randomly selected domain. If you only use one domain, simply provide one value.

### 3. `gptmail_base`

Base URL for the Cloudflare Temp Mail-style backend. This is only used when `email_api_mode: "cloudflare_temp_email"`.

Example:

```yaml
gptmail_base: "https://mail-api.example.com"
```

Do not include a trailing slash.

### 4. `default_proxy`

Global proxy address used for primary network requests.

Example:

```yaml
default_proxy: "http://127.0.0.1:7897"
```

Or:

```yaml
default_proxy: "socks5://127.0.0.1:1080"
```

Leave it empty if your runtime environment already has direct connectivity.

### 5. `clash_proxy_pool`

`clash_proxy_pool` is an optional configuration block for automatic Clash node rotation via the External Controller API.

```yaml
clash_proxy_pool:
  enable: false
  api_url: "http://127.0.0.1:9097"
  group_name: "节点选择"
  secret: "set-your-secret"
  test_proxy_url: "http://127.0.0.1:7897"
  blacklist:
    - "自动"
    - "故障"
    - "剩余"
    - "到期"
    - "官网"
    - "Traffic"
    - "DIRECT"
    - "REJECT"
    - "港"
    - "HK"
    - "Hongkong"
    - "台"
    - "TW"
    - "Taiwan"
    - "中"
    - "CN"
    - "China"
    - "回国"
```

Field notes:

- `enable`: enables automatic node switching before each registration task
- `api_url`: Clash External Controller endpoint, usually on port `9090` or `9097`
- `group_name`: proxy group keyword used to locate the actual selectable Clash group
- `secret`: authentication secret for the Clash controller, if enabled
- `test_proxy_url`: local proxy endpoint used for post-switch connectivity testing
- `blacklist`: keywords used to exclude unwanted nodes such as unsupported regions or non-routable entries

Behavior summary:

- Queries the Clash controller for available proxy groups
- Fuzzily matches the configured group name against actual Clash group names
- Filters candidate nodes using the configured blacklist
- Randomly selects a node and sends the switch command through the controller API
- Verifies post-switch connectivity and skips blocked regions such as `CN` / `HK`
- Falls back to the current IP if switching fails

### 6. `imap`

When `email_api_mode` is set to `imap`, configure the following block:

```yaml
imap:
  server: "imap.gmail.com"
  port: 993
  user: "your_mailbox@example.com"
  pass: "your_app_password"
```

Field notes:

- `server`: IMAP server address, such as `imap.gmail.com` or `imap.qq.com`
- `port`: IMAP SSL port, typically `993`
- `user`: mailbox login, usually the full email address
- `pass`: IMAP password; for many providers this should be an app password or authorization code rather than the normal web password

### 7. `freemail`

When `email_api_mode` is set to `freemail`, configure:

```yaml
freemail:
  api_url: "https://your-domain.com"
  api_token: ""
```

Field notes:

- `api_url`: base URL of the Freemail-compatible API
- `api_token`: Bearer token used for authentication

### 8. `admin_auth`

When `email_api_mode` is set to `cloudflare_temp_email`, this field is used as the administrator credential for the temp-mail backend.

Example:

```yaml
admin_auth: "your_admin_secret"
```

### 9. `max_otp_retries`

Controls the maximum number of resend / retry attempts when OTP retrieval fails.

Example:

```yaml
max_otp_retries: 5
```

When messages are delayed or OTP extraction fails, the script uses this value to determine retry behavior.

### 10. `use_proxy_for_email`

Controls whether mailbox-side requests should also use the proxy.

```yaml
use_proxy_for_email: false
```

- `false`: mailbox APIs / IMAP connections are direct by default
- `true`: mailbox APIs / IMAP connections also go through the proxy

Enable this only when your mailbox API or IMAP service must be accessed through a proxy.

### 11. `enable_email_masking`

Controls whether mailbox domains are masked in console logs.

```yaml
enable_email_masking: true
```

- `true`: logs display masked mailbox output
- `false`: logs display the full mailbox address

### 12. `token_output_dir`

Specifies the local output directory.

```yaml
token_output_dir: ""
```

- Empty: output is written to the current script directory
- Set a path: output is written to the specified directory

The script creates the directory automatically when needed.

### 13. `cpa_mode`

`cpa_mode` is an optional maintenance configuration block for inventory inspection and upkeep:

```yaml
cpa_mode:
  enable: false
  save_to_local: true
  api_url: "http://your-domain.com:8317"
  api_token: "xxxx"
  min_accounts_threshold: 30
  batch_reg_count: 1
  min_remaining_weekly_percent: 80
  check_interval_minutes: 60
```

Field notes:

- `enable`: enables CPA maintenance mode
- `save_to_local`: whether to retain a local backup while uploading remotely in CPA mode
- `api_url`: CPA internal API endpoint
- `api_token`: CPA API credential / token
- `min_accounts_threshold`: triggers replenishment logic when inventory falls below this value
- `batch_reg_count`: number of items processed in each replenishment batch
- `min_remaining_weekly_percent`: threshold used in health assessment logic
- `check_interval_minutes`: inspection interval in minutes

### 14. `normal_mode`

`normal_mode` controls the wait interval between iterations in the standard loop.

```yaml
normal_mode:
  sleep_min: 5
  sleep_max: 30
```

Field notes:

- `sleep_min`: minimum wait time in seconds after each cycle
- `sleep_max`: maximum wait time in seconds after each cycle

### 15. Configuration suggestions

- **IMAP only**: focus on `email_api_mode`, `mail_domains`, `imap`, and `use_proxy_for_email`
- **Freemail API only**: focus on `email_api_mode`, `freemail.api_url`, and `freemail.api_token`
- **Cloudflare Temp Mail backend only**: focus on `email_api_mode`, `mail_domains`, `gptmail_base`, and `admin_auth`
- **Clash rotation enabled**: additionally complete the `clash_proxy_pool` block and enable Clash external control in your local environment
- **Inventory maintenance enabled**: additionally complete the full `cpa_mode` block

## Running Mihomo / Clash on a server

If you want to use Clash-based node rotation on a server, you can run Mihomo (Clash Meta compatible core) in the background and expose both a local mixed proxy port and the External Controller API.

### 1. Prepare a working directory

```bash
mkdir -p /opt/clash && cd /opt/clash
```

### 2. Download the Mihomo binary

Example for Linux x86_64:

```bash
wget https://github.com/MetaCubeX/mihomo/releases/download/v1.18.1/mihomo-linux-amd64-v1.18.1.gz
gzip -d mihomo-linux-amd64-v1.18.1.gz
mv mihomo-linux-amd64-v1.18.1 mihomo
chmod +x mihomo
```

If you use another CPU architecture, download the matching release from the Mihomo releases page.

### 3. Download your subscription-derived config

Use a Clash-compatible subscription conversion link and request a Clash-style config. The following example uses `-U "Clash-meta"` so the upstream returns the expected format:

```bash
wget -U "Clash-meta" -O /opt/clash/config.yaml 'YOUR_SUBSCRIPTION_CONVERTER_URL'
```

### 4. Check the generated ports in `config.yaml`

After downloading the config, inspect the following fields inside `/opt/clash/config.yaml`:

- `mixed-port`: the local proxy port used by this project, typically mapped to `default_proxy` and `clash_proxy_pool.test_proxy_url`
- `external-controller`: the controller address used by `clash_proxy_pool.api_url`
- `secret`: if present, copy it into `clash_proxy_pool.secret`

For example, if your Mihomo config contains:

```yaml
mixed-port: 7897
external-controller: 127.0.0.1:9097
secret: your-secret
```

Then your project config should normally match that setup:

```yaml
default_proxy: "http://127.0.0.1:7897"

clash_proxy_pool:
  enable: true
  api_url: "http://127.0.0.1:9097"
  secret: "your-secret"
  test_proxy_url: "http://127.0.0.1:7897"
```

### 5. Start Mihomo in the background

```bash
nohup ./mihomo -d /opt/clash > clash.log 2>&1 &
```

This starts Mihomo in the background and writes logs to `clash.log`.

### 6. Stop Mihomo

```bash
pkill mihomo
```

### 7. Recommended checks

Before enabling automatic node rotation in this project, confirm the following:

- Mihomo is running normally in the background
- the local mixed proxy port is reachable
- the External Controller API is reachable from the same machine
- the configured proxy group in `clash_proxy_pool.group_name` actually exists in your Clash config
- the controller `secret`, if enabled, matches the one in Mihomo's config

## Usage

Run normally:

```bash
python wfxl_openai_regst.py
```

Run once:

```bash
python wfxl_openai_regst.py --once
```

## Output Files

Typical output files include:

### JSON files

Example:

```text
token_user_example.com_1711111111.json
```

These store structured output data.

### `accounts.txt`

Example content:

```text
example@gmail.com----password123
```

Use care when storing or handling this file.

## Troubleshooting

### Clash node switching fails
Check the following:
- Clash external control is enabled
- `clash_proxy_pool.api_url` points to the correct controller endpoint
- the controller `secret` is correct if authentication is enabled
- `group_name` matches a real selectable proxy group in Clash
- `test_proxy_url` points to a working local proxy port
- the blacklist is not too strict and does not filter out all nodes

### Gmail IMAP login fails
Check the following:
- IMAP is enabled
- 2-Step Verification is enabled if App Passwords are required
- you are using an App Password, not the normal account password
- organizational policy does not block IMAP or App Passwords

### QQ Mail IMAP login fails
Check the following:
- IMAP is enabled
- you are using the mailbox authorization code
- you are not using the standard web-login password

### Mailbox is created but no email arrives
Possible causes:
- the email landed in spam
- proxy routing breaks email connectivity
- `MAIL_DOMAINS` is incorrect
- API auth is invalid
- mailbox backend is not returning the expected message list

### OTP is not extracted
Possible causes:
- the email body encoding is unusual
- the verification code is not a 6-digit number
- the message content does not match the extraction patterns
- the message detail endpoint contains the code but the list view does not

## Security Notes

- Do not expose `accounts.txt` or JSON credential outputs publicly.
- Prefer environment variables for sensitive configuration when possible.
- Restrict access to the output directory.
- If used in a team setting, add audit logging and permission boundaries.

## Notes

- This repository is intended for research, testing, and internal workflow automation.
- Please ensure your usage complies with applicable laws, platform policies, and service terms.
- Review and adapt configuration values before running in any real environment.

## Author

- wenfxl
