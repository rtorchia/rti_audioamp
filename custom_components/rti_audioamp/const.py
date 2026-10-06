"""Constants for the RTI Audio Distribution Amp integration."""

DOMAIN = "rti_audioamp"
MANUFACTURER = "RTI"

# Config / options keys
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_PASSWORD = "rti"
DEFAULT_SCAN_INTERVAL = 30  # seconds
DEFAULT_PORT = 80

# The AD-4x has 4 physical zones. If you have an 8-zone model (AD-8x),
# change NUM_ZONES to 8 - the device's status page reports zone1..zone8.
NUM_ZONES = 4


MIN_VOLUME = 0
MAX_VOLUME = 100

# Number of physical line inputs on the amp (the AD-4x has 4, shared by
# all zones). Users can give each one a friendly name (e.g. "Sonos").
NUM_SOURCES = 4
CONF_SOURCE_NAME_PREFIX = "source_"
CONF_SOURCE_NAME_SUFFIX = "_name"


def source_name_key(source_num: int) -> str:
    """Config key for a given source's friendly name, e.g. 'source_2_name'."""
    return f"{CONF_SOURCE_NAME_PREFIX}{source_num}{CONF_SOURCE_NAME_SUFFIX}"


def default_source_name(source_num: int) -> str:
    return f"Source {source_num}"


def build_source_names(*configs: dict) -> dict[int, str]:
    """Merge one or more config/options dicts (later ones win) into a
    {source_number: friendly_name} map, falling back to "Source N" when
    a name is missing OR present-but-blank (e.g. a cleared text field)."""
    merged: dict = {}
    for cfg in configs:
        if cfg:
            merged.update(cfg)
    result: dict[int, str] = {}
    for n in range(1, NUM_SOURCES + 1):
        name = merged.get(source_name_key(n))
        if not name or not str(name).strip():
            name = default_source_name(n)
        result[n] = str(name).strip()
    return result


# Group selector labels: the device stores 0 for "no group assigned",
# which is clearer to users shown as "None" than the literal "0".
GROUP_LABELS: dict[int, str] = {0: "None", 1: "1", 2: "2", 3: "3", 4: "4"}
