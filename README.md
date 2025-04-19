# Home Inventory & Object Memory System

A smart, AI-assisted inventory and object tracking system designed to bring order to physical clutter. Combines NFC tagging, photo metadata, and domain-specific reasoning to support memory, cleanup, travel prep, and donation workflows.

---

## Why This Exists

We all accumulate gear, cables, tools, and sentimental objects that eventually blur into a pile. This system helps catalog them *with context* — where they are, what they're for, whether they're still needed — and gives gentle guidance when it's time to find, use, or let go.

---

## Core Ideas

- NFC tags + readers on bins, shelves, tools
- Photo recognition + AI tagging
- ChatGPT-style prompts like:
  - “Where does this go?”
  - “Do I already have one?”
  - “Is this ready to take on a trip?”
- Travel checklists, donation suggestions, usage stats

---

## Modules

- `/scripts/` - Readers, loggers, photo processors
- `/domain/` - Rules for USB cables, batteries, AV gear, etc.
- `/data/` - Example logs, tag maps
- `/docs/` - Vision, ideas, and future directions
