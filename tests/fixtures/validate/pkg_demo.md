# Package `PKG_DEMO`

| Field | Value |
|-------|-------|
| Spec | `tests/fixtures/validate/legacy/packages/pkg_demo.pks` lines 1-8 |
| Body | `tests/fixtures/validate/legacy/packages/pkg_demo.pkb` lines 1-30 |
| Source hash | `0000` |
| Status | draft |

## Purpose

The package updates and reads rows of `DEMO_ITEMS` [PKG_DEMO.SET_STATUS:3-8] [PKG_DEMO.GET_QTY:10-18] [PKG_DEMO.ADD_QTY#2:25-28]. Why it exists: Unknown: needs human input.

## Public API

| Unit | Kind | Signature | Spec | Body |
|------|------|-----------|------|------|
| `PKG_DEMO.SET_STATUS` | PROCEDURE | `PROCEDURE SET_STATUS(P_ID IN NUMBER, P_STATUS IN VARCHAR2)` | 4 | 3-8 |
| `PKG_DEMO.GET_QTY` | FUNCTION | `FUNCTION GET_QTY(P_ID IN NUMBER) RETURN NUMBER` | 5 | 10-18 |
| `PKG_DEMO.ADD_QTY#1` | PROCEDURE | `PROCEDURE ADD_QTY(P_ID IN NUMBER)` | 6 | 20-23 |
| `PKG_DEMO.ADD_QTY#2` | PROCEDURE | `PROCEDURE ADD_QTY(P_ID IN NUMBER, P_QTY IN NUMBER)` | 7 | 25-28 |

### `PKG_DEMO.SET_STATUS`

Sets `DEMO_ITEMS.STATUS` to `P_STATUS` for the row with `ITEM_ID` = `P_ID` [PKG_DEMO.SET_STATUS:5]. It then adds 1 to `PKG_DEMO.G_COUNT` and commits [PKG_DEMO.SET_STATUS:6-7].

### `PKG_DEMO.GET_QTY`

Returns `DEMO_ITEMS.QTY` for `P_ID` [PKG_DEMO.GET_QTY:13-14]. Any error, including `NO_DATA_FOUND`, returns NULL instead [PKG_DEMO.GET_QTY:15-17].

### `PKG_DEMO.ADD_QTY#1`

Calls `PKG_DEMO.ADD_QTY#2` with a quantity of 1 [PKG_DEMO.ADD_QTY#1:22].

### `PKG_DEMO.ADD_QTY#2`

Adds `P_QTY` to `DEMO_ITEMS.QTY` [PKG_DEMO.ADD_QTY#2:27].

### Private units

None found in metadata.

## Dependencies

### Calls out

| From unit | To | Kind | Line |
|-----------|----|------|------|
| `PKG_DEMO.ADD_QTY#1` | `PKG_DEMO.ADD_QTY#2` | CALL | 22 |
| `PKG_DEMO.SET_STATUS` | `TRG_DEMO_BU` | FIRES_TRIGGER | 5 |
| `PKG_DEMO.ADD_QTY#2` | `TRG_DEMO_BU` | FIRES_TRIGGER | 27 |

### Called by

| Caller | Unit called | Line |
|--------|-------------|------|
| `PKG_DEMO.ADD_QTY#1` | `PKG_DEMO.ADD_QTY#2` | 22 |

The other units have no caller in legacy_code/ [PKG_DEMO.SET_STATUS:3] [PKG_DEMO.GET_QTY:10] [PKG_DEMO.ADD_QTY#1:20].

### Package cycles

None found in metadata.

## Tables touched

| Table / view | Operation | Unit | Line | Via |
|--------------|-----------|------|------|-----|
| `DEMO_ITEMS` | UPDATE | `PKG_DEMO.SET_STATUS` | 5 | STATIC |
| `DEMO_ITEMS` | SELECT | `PKG_DEMO.GET_QTY` | 13 | STATIC |
| `DEMO_ITEMS` | UPDATE | `PKG_DEMO.ADD_QTY#2` | 27 | STATIC |

### Triggers fired

| Unit | Statement line | Trigger | What the trigger writes |
|------|----------------|---------|-------------------------|
| `PKG_DEMO.SET_STATUS` | 5 | `TRG_DEMO_BU` | sets `UPD_DT` on the updated row [TRG_DEMO_BU:5] |
| `PKG_DEMO.ADD_QTY#2` | 27 | `TRG_DEMO_BU` | sets `UPD_DT` on the updated row [TRG_DEMO_BU:5] |

## Side effects and risks

### Transaction control

`PKG_DEMO.SET_STATUS` commits, which also commits the caller's open work [PKG_DEMO.SET_STATUS:7].

### Package state

| Variable | Visibility | Constant | Written by | Read by |
|----------|------------|----------|------------|---------|
| `PKG_DEMO.G_COUNT` | PUBLIC | no | `PKG_DEMO.SET_STATUS` [PKG_DEMO.SET_STATUS:6] | `PKG_DEMO.SET_STATUS` [PKG_DEMO.SET_STATUS:6] |

The value persists for the database session [PKG_DEMO.G_COUNT:3]. The comment at [PKG_DEMO(spec):2] says the package writes to `OLD_ITEMS`; no statement in the code does.

### Dynamic SQL

None found in metadata.

### Hardcoded values

None found in metadata.

### Other

None found in metadata.

## Error handling

| Unit | Line | Handler / raise | Effect for the caller |
|------|------|-----------------|-----------------------|
| `PKG_DEMO.GET_QTY` | 16 | WHEN OTHERS | returns NULL; the error is not raised |

## Open questions

1. What the status values mean: Unknown: needs human input.
2. Whether `OLD_ITEMS`, named only in the comment at [PKG_DEMO(spec):2], still exists outside legacy_code/.
