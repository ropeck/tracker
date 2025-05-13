# Zone Scoring & Cleanup Heatmap

Use smart signals to rank and visualize your physical storage zones, highlighting where cleanup will make the most difference.

---

## 🔥 Zone Health Scoring System

Each zone receives a score based on the following signals:

| Signal                 | Weight     | Description |
|------------------------|------------|-------------|
| 📦 Item density        | Medium     | # of items per bin/area |
| ⏱️ Last accessed age   | High       | Time since item or zone interaction |
| ❓ Unknown classification | High    | % of `misc`, `float`, or undefined items |
| 📷 Missing metadata     | Medium     | No image, no tags, no known use |
| 🔁 Recent churn         | High       | Added/removed without proper zone update |
| 🧯 Emergency override   | Very High  | User-flagged urgent clutter or risks |

---

## 🎨 Score Range & Status

| Score     | Meaning               | Visual |
|-----------|------------------------|--------|
| 0–20      | Healthy                | 🟢 Green |
| 21–50     | Light clutter          | 🟡 Yellow |
| 51–75     | Likely uncurated       | 🟠 Orange |
| 76–100    | Critical / chaotic     | 🔴 Red |

---

## 🗺️ Heatmap Dashboard

- Show zone grid/list with color indicators
- Hover/click shows:
  - Last action
  - Unknown item % or tags
  - Suggested resolution

---

## 💡 Effort vs Impact

Estimate which zones to clean based on:
- High score (bad)
- Low effort (few items, recently scanned)
- Past user complaints or recurring clutter

This helps prioritize high-reward cleanup with low time investment.
