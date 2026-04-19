# Spec: Tag Color and Icon — US-155

## Scope

Color validation, predefined icon catalog, default color assignment, and chip rendering.

---

## Scenario: Set a valid hex color when creating a tag

WHEN an admin creates or updates a tag with `{ color: "#FF5733" }`
THEN the `color` field is stored as provided
AND the tag chip renders with that background or border color in the UI

WHEN `color` is provided as `"FF5733"` (missing `#` prefix)
THEN the API returns `400 Bad Request` with `error.code="invalid_color_format"`

WHEN `color` is provided as `"#GGG000"` (invalid hex characters)
THEN the API returns `400 Bad Request` with `error.code="invalid_color_format"`

WHEN `color` is `"#fff"` (3-digit hex shorthand)
THEN the API returns `400 Bad Request` with `error.code="invalid_color_format"` — only 6-digit hex is accepted

### Scenario: Default color when none is specified

WHEN a tag is created without a `color` field
THEN `color` is set to `"#6B7280"` (neutral gray, Tailwind `gray-500`)
AND the chip renders with this default color

### Scenario: Clear a color (reset to default)

WHEN an admin PATCHes a tag with `{ color: null }`
THEN `color` is reset to the default `"#6B7280"`
AND an `audit_events` record is written with `action=tag.updated`, `fields_changed=["color"]`

---

## Scenario: Set an icon from the predefined catalog

WHEN an admin creates or updates a tag with `{ icon: "star" }`
AND `"star"` is a valid member of the icon catalog
THEN the icon is stored and rendered as a small glyph inside or alongside the tag chip

WHEN `icon` is a value not in the predefined catalog (e.g. `"unicorn"`)
THEN the API returns `400 Bad Request` with `error.code="invalid_icon"` and `allowed_values=[<catalog list>]`

### Predefined icon catalog (initial set — extensible)

| Key | Description |
|-----|-------------|
| `star` | Star / highlight |
| `flag` | Flag / priority marker |
| `lock` | Locked / restricted |
| `bolt` | Fast / urgent |
| `bug` | Bug / defect |
| `shield` | Security / compliance |
| `clock` | Time-sensitive |
| `person` | People / stakeholder |
| `link` | External dependency |
| `wrench` | Technical / infrastructure |

### Scenario: No icon specified

WHEN a tag is created without an `icon` field
THEN `icon` is `null`
AND the chip renders without an icon glyph (text/color only)

### Scenario: Clear an icon

WHEN an admin PATCHes a tag with `{ icon: null }`
THEN `icon` is set to `null`
AND the chip renders without an icon

---

## Scenario: Tag chip rendering in work item header

WHEN a work item has tags attached
THEN each tag renders as a pill/chip in the work item header
AND the chip displays: `[icon?] label` with the tag's `color` as the chip background (low opacity) and border
AND chips are ordered alphabetically by tag name
AND if more than 5 tags are present, the first 4 are shown and a `+N` overflow badge shows the remaining count
AND clicking the overflow badge expands all chips inline

### Scenario: Chip rendering for archived tags (existing attachments)

WHEN a work item has an archived tag attached
THEN the chip renders with a strikethrough style and reduced opacity
AND a tooltip on hover shows "This tag has been archived"
AND the chip is still visible (it is not hidden)

### Scenario: Chip color contrast

WHEN a tag has a very dark or very light `color`
THEN the chip label text must maintain WCAG AA contrast (4.5:1 ratio)
AND the UI applies a contrasting text color (white or black) based on computed luminance of the background

---

## Non-Functional

- Color validation regex: `^#[0-9A-Fa-f]{6}$`
- Icon catalog is stored as a server-side constant and validated at the API layer (not DB constraint)
- The icon catalog list is exposed via `GET /api/v1/tags/icons` for frontend consumption
- Chip rendering uses Tailwind CSS utility classes; color is applied via inline `style` (not arbitrary Tailwind values)
- Maximum chip width: 160px with text truncation and full label in tooltip
