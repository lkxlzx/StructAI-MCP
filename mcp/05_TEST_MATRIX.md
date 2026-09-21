# MCP Connector Test Matrix

## 1. MCP Layer

| Test | Input | Expected |
|---|---|---|
| initialize | valid protocolVersion | initialize result |
| tools/list | none | exactly 4 tools |
| unknown tool | `abc` | MCP method/tool error |
| invalid JSON | malformed | JSON-RPC error |
| unknown endpoint | `DB/XXX` | registry error |

## 2. DOC

```text
NEW
OPEN
SAVE
SAVEAS
STAGAS
IMPORT
IMPORTMXT
EXPORT
EXPORTMXT
ANAL
CLOSE
```

## 3. DB

### Read

```text
DB:NODE
DB:NODE:1001
DB:ELEM
DB:MATL
DB:SECT
DB:STLD
```

### Write

```text
NODE POST
NODE PUT
MATL POST
SECT PUT
BMLD POST
CONS POST
```

### Delete

```text
NODE delete selected ids
ELEM delete selected ids
```

## 4. Special methods

Verify rejection:

```text
UNIT create -> reject
STYP create -> reject
```

Verify acceptance:

```text
UNIT update -> PUT
STYP update -> PUT
```

## 5. POST

```text
POST:TABLE:ELEMENTWEIGHT
POST:TABLE:REACTIONG
POST:TABLE:BEAMFORCE
POST:TEXT:TH_DISP
```

## 6. VIEW

```text
VIEW:CAPTURE
VIEW:RESULTGRAPHIC
VIEW:ANGLE
VIEW:DISPLAY
```

## 7. OPE

```text
OPE:PROJECTSTATUS
OPE:DIVIDEELEM
OPE:AUTOMESH
OPE:LCOM-GEN
```

## 8. DESIGN

```text
DESIGN:STEEL:DSTL
DESIGN:STEEL:KDS-41-30-2022:DCO
DESIGN:STEEL:KDS-41-30-2022:CODE-ANAL

DESIGN:RC:DRC
DESIGN:RC:KDS-41-20-2022:DCO
DESIGN:RC:KDS-41-20-2022:BD-ANAL

DESIGN:SRC:AIK-SRC2K:DSRC
DESIGN:SRC:AIK-SRC2K:BC-ANAL
```

## 9. Error tests

```text
401 invalid MAPI-Key
403 access failure
404 invalid route
409 model busy (if returned)
500 upstream internal
502/503/504 upstream unavailable
timeout
connection refused
invalid JSON response
```

## 10. Safety

### Delete

Must not silently perform all delete.

### Analysis

Do not auto-retry.

### Import

Do not auto-retry unless user confirms the operation is safe to repeat.

### Export

Retries are safe only when path semantics are controlled.

## 11. Regression

每次 MIDAS API Online Manual 变化：

```text
1. update source chapter
2. diff schema
3. diff endpoint count
4. regenerate registry
5. regenerate tools/list schema
6. run golden tests
7. run smoke test against Civil
8. run smoke test against Gen
```
