# RTI Audio Distribution Amp for Home Assistant

A custom Home Assistant integration for RTI audio distribution amplifiers
(tested on the **AD-4x**). Each zone is exposed as its own device with
power, mute, source, group, and volume controls.

## Features

- UI-based setup (no YAML) — just enter the amp's IP address
- One Home Assistant device per zone (4 zones)
- Per zone:
  - **Power** switch
  - **Mute** switch
  - **Source** select (1–4), with optional custom names per source (e.g. rename "Source 2" to "Sonos")
  - **Group** select (0–4, shown as "None" for 0)
  - **Volume** slider (0–100%, converted from the device's internal dB scale)
- Configurable poll interval
- Local polling only — no cloud, no external services

## Installation

### HACS (custom repository)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**.
2. Add this repository's URL, category **Integration**.
3. Search for "RTI Audio Distribution Amp" in HACS and install it.
4. Restart Home Assistant.

### Manual

1. Copy the `custom_components/rti_audioamp` folder from this repo into
   your Home Assistant `config/custom_components/` directory, so you end
   up with `config/custom_components/rti_audioamp/...`.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for "RTI Audio Distribution Amp".
3. Enter:
   - **IP address or hostname** of the amp
   - **Password** (defaults to `rti` — currently unused by the device's
     read/write endpoints, but stored for forward compatibility)
   - **Poll interval** in seconds (default 30)
   - Optional friendly names for each of the 4 sources
4. Submit. Four zone devices will be created automatically.

Poll interval, password, and source names can all be changed later from
the integration's **Configure** option.

## Entities created

| Entity | Platform | Notes |
|---|---|---|
| Power | `switch` | On/off toggle |
| Mute | `switch` | On/off toggle |
| Source | `select` | Options are your configured source names |
| Group | `select` | `None`, `1`–`4` |
| Volume | `number` | 0–100% slider |

## Troubleshooting

- Enable debug logging for live request/response details:

  ```yaml
  logger:
    logs:
      custom_components.rti_audioamp: debug
  ```

- If entities show `Unknown`, check the log for a warning from
  `custom_components.rti_audioamp.api` — it logs the device's raw
  response when it can't recognize the expected fields, which usually
  means a firmware/model difference in the status JSON shape.
- The amp's embedded web server doesn't handle overlapping requests or
  HTTP keep-alive well; this integration serializes all requests and
  retries automatically on malformed responses, but if you still see
  intermittent `Error fetching rti_audioamp data` log entries, consider
  increasing the poll interval.

## Known limitations

- Developed and tested against a single AD-4x unit. Other RTI amp models
  may use a different number of zones/sources or a different status
  JSON shape.
- The `password` field isn't currently used by any request — the
  device's CGI endpoints don't require authentication on the unit this
  was tested against.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Based on an original Python script by Ralph Torchia for communicating
with the RTI AD-4x over its local HTTP CGI endpoints.
