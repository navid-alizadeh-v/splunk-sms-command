# Splunk AbuseIPDB Enrichment

**A custom Splunk search command for IP reputation enrichment using AbuseIPDB, with SQLite caching, public-IP validation, API request controls, and structured enrichment metadata.**

![Splunk](https://img.shields.io/badge/Platform-Splunk-000000?logo=splunk&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![AbuseIPDB](https://img.shields.io/badge/Threat%20Intelligence-AbuseIPDB-red)
![Cache](https://img.shields.io/badge/Cache-SQLite-003B57?logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

**Splunk AbuseIPDB Enrichment** is a custom Splunk search command that enriches IP address fields with reputation intelligence from [AbuseIPDB](https://www.abuseipdb.com/).

The app is designed to help SOC analysts and security engineers add external IP reputation context to existing Splunk searches without repeatedly making unnecessary API requests.

Instead of manually checking suspicious IP addresses or building separate enrichment logic into every detection search, analysts can use a reusable command directly in SPL.

The app combines reputation enrichment with local SQLite caching, public-IP validation, request handling, and structured status fields. This makes it useful as a building block for threat hunting, alert triage, investigation workflows, and security dashboards.

> **Design principle:** Enrich only the data that needs enrichment, reuse cached intelligence when available, and make the result and processing status visible to the analyst.

## Key Features

### 1. Native SPL workflow

The app exposes an `abuseipdb` custom search command that can be added to an existing SPL pipeline.

Analysts can select an IP field, run enrichment, and continue using the returned fields in tables, dashboards, alerts, and downstream searches.

This approach avoids requiring analysts to leave Splunk every time they need additional context for an IP address.

### 2. SQLite caching to reduce redundant API requests

Repeatedly requesting the reputation of the same IP address can waste API quota, increase latency, and create unnecessary dependency on an external service.

The app uses a local SQLite database to cache enrichment results.

When a usable cached result is available, the app can reuse it rather than requesting the same information again. Cache-related metadata helps analysts distinguish cached results from other processing paths.

Benefits include:

- Fewer redundant requests to AbuseIPDB.
- More efficient use of API request quotas.
- Reduced external API dependency during repeated investigations.
- Faster processing when valid cached data is available.
- Local persistence of cached intelligence between searches.
- Cache configuration to control how cached data is reused and refreshed.

The cache is a performance optimization, not a guarantee that reputation data is permanently current. An IP's reputation may change after a result is cached, so cache lifetime and refresh behavior should be configured according to operational requirements.

The cache database is stored locally on the Splunk server and should not be committed to source control.

### 3. Public-IP validation

Private, loopback, link-local, and other non-public IP addresses are not useful targets for public AbuseIPDB reputation lookups in the same way that globally routable addresses are.

The app validates IP addresses and avoids sending non-public addresses to AbuseIPDB for reputation checks.

This helps prevent unnecessary external requests for internal infrastructure addresses and reduces wasted API quota.

It is especially useful when enrichment is applied to large datasets containing a mixture of internal and external source and destination addresses.

**Operational note:** Public-IP validation does not replace internal asset inventory, internal threat intelligence, or private-network detection rules. Internal addresses may still be important for security investigations and should be analyzed using appropriate internal telemetry.

### 4. Input and output field handling

The command accepts an IP field through an argument such as `ip=src_ip`.

Enrichment results are added to the search results using a dedicated `abuseipdb_` field prefix. This keeps the returned intelligence identifiable and helps avoid confusion with existing fields.

The command also preserves the original search fields so that analysts can correlate the enrichment results with the events that produced them.

For example, the original `src_ip` field can remain available alongside `abuseipdb_ipAddress` and the reputation metadata.

### 5. Structured enrichment metadata

The app returns more than a reputation score. It also exposes fields describing the result and how it was obtained.

These fields help analysts interpret the enrichment output rather than treating every result as an identical live API response.

Depending on the processing path, metadata can indicate whether the result was obtained online, whether a cached result was used, the cache age, and whether processing encountered an error.

This distinction is important for SOC workflows: **a successful enrichment, a cache hit, and an unsuccessful external lookup are not the same operational outcome.**

### 6. API request and rate-limit handling

AbuseIPDB API usage is subject to the limits associated with the account and API plan.

The app includes request-handling logic for API responses and rate-limit-related conditions. It also supports configurable API key rotation according to the app's configuration and implementation.

These mechanisms help make the enrichment workflow more manageable when the command is used repeatedly.

They do not remove AbuseIPDB's rate limits, guarantee uninterrupted API availability, or increase the account's permitted quota. Actual behavior depends on the configured keys, API responses, and the limits imposed by AbuseIPDB.

### 7. Error visibility

Enrichment can fail for reasons such as network connectivity, API errors, rate limits, or invalid input.

The app provides status and error metadata so analysts can distinguish a reputation result from a lookup that did not complete successfully.

This is preferable to interpreting a missing reputation value as evidence that an IP address is safe.

**A failed lookup must not be interpreted as a clean reputation result.**

### 8. Lightweight implementation

The app uses Python's standard library for its core functionality, including HTTP requests and SQLite database operations.

The implementation avoids requiring a separate database server or an additional Python package installation for its core API and cache logic.

The app is designed to run within a Splunk installation that supports the configured Python search-command runtime. Validate compatibility with your specific Splunk deployment before rolling it out to production.

---

## Architecture

At a high level, the enrichment workflow is:

1. A Splunk search produces events containing an IP field.
2. The `abuseipdb` command reads the selected field.
3. The app validates the IP address.
4. Non-public addresses are excluded from public reputation lookups.
5. For eligible addresses, the app checks the local SQLite cache.
6. If a suitable cached result is available, it can be reused.
7. If a fresh lookup is required, the app uses the configured AbuseIPDB API request logic.
8. The enrichment fields and processing metadata are added to the results.
9. The resulting dataset remains available to the rest of the SPL pipeline.

```text
Splunk Search
     |
     v
IP Field Selection
     |
     v
IP Validation
     |
     +---- Non-public / ineligible IP
     |              |
     |              v
     |       No public lookup
     |
     v
SQLite Cache Lookup
     |
     +---- Valid cached result
     |              |
     |              v
     |       Reuse cached data
     |
     +---- Cache miss / refresh required
                    |
                    v
            AbuseIPDB API Request
                    |
                    v
          Response / Error Handling
                    |
                    v
        Enrichment + Status Metadata
                    |
                    v
             Splunk Search Results
```

*The diagram describes the logical workflow; the precise execution path depends on the input and the cache/API response.*

## Screenshots

### 1. IP reputation enrichment in Splunk

This example shows the enrichment fields returned by the custom command, including reputation information and processing status.

![IP reputation enrichment results](docs/images/01-splunk-enrichment-results.png)

### 2. Cache behavior and processing metadata

Cache-related fields make it easier to understand whether a result was served from local storage and how old the cached data is.

![Cache and status fields](docs/images/02-cache-and-status.png)

### 3. IP validation and non-public address handling

This example demonstrates how the command handles IP addresses that should not be sent to a public reputation service. Use a real test result from your own Splunk environment.

![IP validation and private IP handling](docs/images/03-input-validation-and-private-ips.png)

> Replace these image paths with the screenshots included in this repository. Redact API keys, tokens, internal hostnames, sensitive event data, and any information that should not be publicly disclosed.

---

## Requirements

- A Splunk installation that supports the configured custom Python search-command runtime.
- Access to the Splunk server's app directory for installation and configuration.
- An AbuseIPDB API key for live reputation lookups.
- Outbound network connectivity from the Splunk server to the AbuseIPDB API endpoint for live requests.
- Write access to the configured local cache directory.
- A compatible Python runtime and SQLite support.

The core API and cache implementation uses Python standard-library modules. No additional third-party Python package is required for those core operations.

## Installation

### 1. Install the app

Copy or extract the app into the Splunk apps directory:

```text
$SPLUNK_HOME/etc/apps/splunk-abuseipdb-enrichment/
```

The repository structure is expected to include files such as:

```text
splunk-abuseipdb-enrichment/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── bin/
│   ├── abuseipdb.py
│   └── abuseipdb_core.py
├── default/
│   └── commands.conf
├── metadata/
│   └── default.meta
└── local/
    └── abuseipdb_keys.example.json
```

The cache database is runtime data and should be created in its configured location rather than shipped as part of the source repository.

### 2. Configure the API key

Create the local configuration file using the provided example:

```text
local/abuseipdb_keys.json
```

Use `local/abuseipdb_keys.example.json` as the template and follow the configuration format expected by the app.

The real configuration file must remain private. Do not commit it, include it in a public ZIP archive, or place API keys directly in source code.

Set appropriate ownership and restrictive file permissions for the Splunk service account. For example, on a Linux Splunk installation running as `splunk`:

```bash
chown splunk:splunk local/abuseipdb_keys.json
chmod 600 local/abuseipdb_keys.json
```

Adjust ownership and paths for your environment.

### 3. Verify the Splunk command configuration

The app defines the custom command in:

```text
default/commands.conf
```

It also includes command metadata under:

```text
metadata/default.meta
```

After installing or changing the app, validate the configuration and restart Splunk when required by the deployment.

Example configuration inspection:

```bash
$SPLUNK_HOME/bin/splunk btool commands list abuseipdb --debug
```

Run administrative commands using the appropriate account and operational procedures for your environment.

---

## Usage

### Basic example

Assume the search results contain an IP address in a field named `src_ip`.

```spl
| makeresults
| eval src_ip="8.8.8.8"
| abuseipdb ip=src_ip
| table src_ip abuseipdb_ipAddress abuseipdb_abuseConfidenceScore abuseipdb_countryCode abuseipdb_isp abuseipdb_totalReports abuseipdb_status abuseipdb_error
```

This example creates a test event, selects `src_ip` as the input field, and displays a subset of the returned enrichment fields.

The result depends on the current cache state, API availability, configuration, and the data returned by AbuseIPDB. The example IP is for demonstration purposes and is not an assertion that a particular reputation result will always be returned.

### Enrich an existing search

The command can be placed after a search that produces an IP field:

```spl
index=firewall
| abuseipdb ip=src_ip
| table _time src_ip dest_ip abuseipdb_abuseConfidenceScore abuseipdb_countryCode abuseipdb_isp abuseipdb_totalReports abuseipdb_status
```

Replace the index and field names with those used in your environment.

### Enrich destination addresses

```spl
index=firewall
| abuseipdb ip=dest_ip
| table _time src_ip dest_ip abuseipdb_ipAddress abuseipdb_abuseConfidenceScore abuseipdb_countryCode abuseipdb_status
```

This can be useful when investigating outbound connections or reviewing destination IP addresses. Whether an address is appropriate for public reputation lookup depends on its validity and routability.

### Display cache and request status

```spl
index=firewall
| abuseipdb ip=src_ip
| table src_ip abuseipdb_ipAddress abuseipdb_check_mode abuseipdb_cache_hit abuseipdb_cache_age_days abuseipdb_status abuseipdb_error
```

Use the metadata to distinguish cache behavior from the online lookup path and to identify processing errors.

Field availability and values depend on the path taken by the command.

---

## Output Fields

The app uses an `abuseipdb_` prefix for its enrichment fields.

| Field | Description |
|---|---|
| `abuseipdb_ipAddress` | IP address associated with the enrichment result. |
| `abuseipdb_isWhitelisted` | Whitelist-related value returned by the API, when available. |
| `abuseipdb_abuseConfidenceScore` | AbuseIPDB abuse-confidence score. Interpret it in the context of the source data and investigation. |
| `abuseipdb_countryCode` | Country code returned by AbuseIPDB, when available. |
| `abuseipdb_usageType` | Reported usage classification, when available. |
| `abuseipdb_isp` | ISP information returned by the service, when available. |
| `abuseipdb_domain` | Domain information returned by the service, when available. |
| `abuseipdb_hostnames` | Hostname information returned by the service, when available. |
| `abuseipdb_totalReports` | Total report count returned by AbuseIPDB, when available. |
| `abuseipdb_lastReportedAt` | Timestamp of the last reported activity, when available. |
| `abuseipdb_check_mode` | Indicates the processing mode, such as an online or offline path. |
| `abuseipdb_cache_hit` | Indicates whether a cached result was used. |
| `abuseipdb_cache_age_days` | Age of the cached result, when applicable. |
| `abuseipdb_status` | Processing status for the enrichment operation. |
| `abuseipdb_error` | Error details when the operation encounters an issue, if available. |

A missing field, an unavailable API value, a skipped lookup, and an unsuccessful request should not automatically be treated as equivalent outcomes.

## Security and Operational Considerations

### Protect API credentials

- Keep the real API-key configuration out of version control.
- Use restrictive filesystem permissions.
- Never place API keys in SPL queries, screenshots, README examples, or public issue reports.
- Rotate credentials immediately if they are exposed.
- Follow your organization's secret-management policies.

### Treat reputation as an investigative signal

An AbuseIPDB score is one source of threat intelligence, not a definitive verdict.

A high score may support further investigation, while a low score does not guarantee that an address is benign. Reputation should be evaluated alongside firewall telemetry, DNS activity, endpoint logs, authentication events, asset context, and other available intelligence.

### Account for cache freshness

Cached results can become outdated. Select cache settings that balance API efficiency with the freshness required by your use case.

For time-sensitive investigations, verify the cache behavior and refresh policy before relying on a result as current intelligence.

### Plan for API and network failures

Live enrichment depends on connectivity and the service's availability and rate limits. Monitor error and status fields, and ensure that a failed external lookup is not interpreted as a clean reputation result.

### Consider Splunk deployment architecture

In distributed or clustered deployments, validate the app's configuration, cache location, file permissions, and execution behavior on the components that run the search command. A local SQLite cache is local to the filesystem where it is stored; do not assume that all Splunk search peers share the same cache.

## Troubleshooting

### Unknown search command

Check that the app is installed in the correct Splunk apps directory, enabled, and configured with the expected command and metadata settings.

Inspect the effective configuration:

```bash
$SPLUNK_HOME/bin/splunk btool commands list abuseipdb --debug
```

Review Splunk's search and application logs for configuration or command-loading errors.

### API lookup fails

Check:

- That the local API-key configuration exists and is valid.
- That the Splunk service account can read the configuration.
- That the Splunk server has the required outbound network connectivity.
- Whether the API response indicates a rate limit or another service-side error.
- The returned `abuseipdb_status` and `abuseipdb_error` fields.

Avoid printing API keys or complete secret configuration files while troubleshooting.

### Cached results appear instead of a new lookup

Review `abuseipdb_cache_hit`, `abuseipdb_cache_age_days`, and `abuseipdb_check_mode`.

Confirm that the cache settings match your intended refresh behavior. A cache hit is not necessarily a problem; it is often the expected behavior when a reusable cached result is available.

### Original input fields are missing

Check the installed version of the command and confirm that the output handling preserves the original search results. Test with a small search using `makeresults` before troubleshooting a large production search.

## Repository Layout

| Path | Purpose |
|---|---|
| `bin/abuseipdb.py` | Splunk custom search-command entry point. |
| `bin/abuseipdb_core.py` | Core enrichment, API request, and cache logic. |
| `default/commands.conf` | Custom search-command configuration. |
| `metadata/default.meta` | Command and app metadata permissions. |
| `local/abuseipdb_keys.example.json` | Example API-key configuration template. |
| `local/abuseipdb_keys.json` | Private runtime configuration; must not be committed. |
| `README.md` | Project documentation and usage examples. |
| `LICENSE` | MIT license. |
| `.gitignore` | Excludes private configuration and runtime artifacts. |

## Contributing

Issues, suggestions, and improvements are welcome.

When submitting a bug report, include:

- The Splunk version and deployment type.
- A minimal SPL example that reproduces the issue.
- Relevant status and error fields.
- Sanitized log excerpts, if necessary.
- Expected versus actual behavior.

Do not include API keys, authentication tokens, sensitive logs, or confidential network information in issues or pull requests.

## Disclaimer

This project is provided for security operations, investigation, and threat-intelligence enrichment purposes. It is not a substitute for a complete detection strategy, incident-response process, or independent validation of threat intelligence.

AbuseIPDB is an external service, and its API availability, response fields, rate limits, and usage conditions are governed by the service provider.

This project is not affiliated with or endorsed by AbuseIPDB or Splunk.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.


---

# 👤 Author

**Navid Alizadeh**

www.linkedin.com/in/navid-alizadeh-vaghasloo

Security Operations Center Analyst
Splunk | SOC | Threat Detection | Incident Response

---

⭐ If this project is useful to you, consider giving the repository a star.