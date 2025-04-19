# System Overview

## Components

- **Mobile Scanner Node**
  Raspberry Pi Zero + PN532 + battery. Reads NFC tags and logs tag events with timestamps.

- **Central Inventory Database**
  SQLite (or JSON) storing item metadata, location, history, domains, etc.

- **Domain Modules**
  Python modules that describe logic for interpreting item types (USB cables, batteries, AV gear, etc).

- **Query Interface**
  CLI, notebook, or chat frontend to answer questions like:
  - "Where's the yellow jacket?"
  - "Do I have one of these already?"
  - "What's missing from my laptop bag?"

## Optional Extensions

- Tag write tool for encoding metadata
- AR overlay or Watch notifications
- NFC-tagged cats + zone readers
