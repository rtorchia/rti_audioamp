# Changelog

## 0.1.0

- Initial release: UI config flow, 4 zone devices, power/mute switches,
  source/group selects (with custom source naming), volume slider.
- Device-registry parent device + local `brand/` icon assets.
- Request serialization, keep-alive disabled, and automatic retry on
  malformed status responses to work around the amp's embedded web
  server quirks.
- Volume correctly converts between the device's internal dB scale and
  Home Assistant's 0–100% slider.
