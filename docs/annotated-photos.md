# Annotated Photos in the Inventory App

Annotated photos (with AI object recognition overlays and scoring) provide an intuitive way to visualize inventory, recommend cleanup actions, and track progress.

## Use Cases

### 1. Visual Inventory Viewer
- View each uploaded photo with overlay boxes and labels.
- Hover or tap objects to see:
  - Name (AI tag or user label)
  - Suggested bin or zone
  - Confidence score (is it in the right place?)
  - Cleanup recommendation

### 2. "What's in this Photo?" History
- Timeline of photos with AI-labeled inventory
- Let users click to revisit each session's cleanup suggestions
- Useful for historical tracking or proof of organization

### 3. Cleanup Assistant Mode
- Display annotated photo + checklist of suggested actions:
  - Move object to labeled bin
  - Discard empty packaging
  - Group similar items
- Interactive UX for marking items as “Done” or “Still Pending”

## API Integration Plan

- Add `/annotated/` endpoint to serve overlaid versions of photos
- Link this view to each photo’s metadata and object database
- Optional: render dynamic overlays server-side or with canvas

## Future Enhancements
- Support before/after state comparisons
- Enable drag-and-label for user corrections
- Auto-track cleanup progress using photo timelines

This module enhances the visual and practical power of the system — helping users quickly understand clutter and take action.
