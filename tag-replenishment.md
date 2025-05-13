# NFC Tag Inventory & Replenishment Protocol

To prevent catastrophic loss of organizational ability, the system must track and maintain a minimum viable quantity of unassigned NFC tags.

---

## 🎯 Goal

Ensure there are always enough available tags to support:
- Ongoing organization
- Project tracking
- High-frequency consumables (e.g., trash bags, batteries)

---

## 🧮 Tag Inventory Tracking

Each tag is logged in the system as one of:

- `assigned` – linked to an item or zone
- `available` – unused, in stock
- `reserved` – pre-allocated for a process or automation

---

## ⚠️ Reorder Threshold

- Set a `min_threshold` (e.g., 10 tags)
- Alert when `available_tags <= min_threshold`:
  > "Warning: NFC tag inventory low (8 remaining). Suggest reorder."

Optionally trigger:
- Email alert
- Pop-up in dashboard
- Label printer sticker that says “Reorder Tags” and tapes itself to your monitor (future enhancement)

---

## 🧠 Special Tags

Reserve specific tags for system continuity:

| Tag ID | Purpose        |
|--------|----------------|
| 00001  | "More Tags Here" – marks the location of backup tag supply |
| 00002  | "This Bin Contains Trash Bags" – linked to usage rate, suggests reorder when depleted |

---

## 📦 Bonus: Tag Lifecycle Hooks

- When a tag is removed from an item:
  - Mark as `available`
  - Log disassociation time and context

- When adding a tag:
  - Prompt user for classification and priority

---

## 🐱 Why This Matters

Without available tags, nothing can be found.
Without the ability to *track the tags themselves*, the system collapses into recursive absurdity.
Plan accordingly.
