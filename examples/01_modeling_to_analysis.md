# Example — 3D Frame Modeling → Analysis → Result

## 1 NEW

```json
{
  "command": "NEW",
  "argument": {}
}
```

## 2 NODE

```json
{
  "endpoint": "DB:NODE",
  "mode": "create",
  "data": {
    "1": {"X":0,"Y":0,"Z":0},
    "2": {"X":6,"Y":0,"Z":0},
    "3": {"X":6,"Y":6,"Z":0},
    "4": {"X":0,"Y":6,"Z":0},
    "5": {"X":0,"Y":0,"Z":3},
    "6": {"X":6,"Y":0,"Z":3},
    "7": {"X":6,"Y":6,"Z":3},
    "8": {"X":0,"Y":6,"Z":3}
  }
}
```

## 3 ELEM

```json
{
  "endpoint": "DB:ELEM",
  "mode": "create",
  "data": {
    "1": {"TYPE":"BEAM","MATL":1,"SECT":1,"NODE":[1,5]},
    "2": {"TYPE":"BEAM","MATL":1,"SECT":1,"NODE":[2,6]},
    "3": {"TYPE":"BEAM","MATL":1,"SECT":1,"NODE":[3,7]},
    "4": {"TYPE":"BEAM","MATL":1,"SECT":1,"NODE":[4,8]},
    "5": {"TYPE":"BEAM","MATL":1,"SECT":1,"NODE":[5,6]},
    "6": {"TYPE":"BEAM","MATL":1,"SECT":1,"NODE":[6,7]},
    "7": {"TYPE":"BEAM","MATL":1,"SECT":1,"NODE":[7,8]},
    "8": {"TYPE":"BEAM","MATL":1,"SECT":1,"NODE":[8,5]}
  }
}
```

## 4 Query

```json
{
  "endpoint": "DB:NODE"
}
```

## 5 ANAL

```json
{
  "command": "ANAL",
  "argument": {}
}
```

## 6 Beam forces

```json
{
  "endpoint": "POST:TABLE:BEAMFORCE",
  "mode": "create",
  "data": {
    "TABLE_NAME": "BeamForce",
    "TABLE_TYPE": "BEAMFORCE",
    "UNIT": {"FORCE":"KN","DIST":"M"},
    "NODE_ELEMS": {"TO":"1 to 8"},
    "LOAD_CASE_NAMES": ["DL(ST)","LL(CB)"],
    "PARTS": ["Part I","Part J"]
  }
}
```
