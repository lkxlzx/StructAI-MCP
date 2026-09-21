# Endpoint Registry — Recommended Schema

```json
{
  "key": "DB:NODE",
  "namespace": "db",
  "uri": "/db/NODE",
  "methods": ["GET", "POST", "PUT", "DELETE"],
  "tool_map": {
    "GET": "midas_db_query",
    "POST": "midas_db_assign",
    "PUT": "midas_db_assign",
    "DELETE": "midas_db_delete"
  },
  "request": {
    "wrapper": "Assign",
    "selector_field": null,
    "selector_value": null
  },
  "id": {
    "mode": "numeric-string"
  },
  "source_page": "03_DB_Node_Element.md"
}
```

Selector endpoint:

```json
{
  "key": "POST:TABLE:BEAMFORCE",
  "namespace": "post",
  "uri": "/post/TABLE",
  "methods": ["POST"],
  "tool_map": {
    "POST": "midas_db_assign"
  },
  "request": {
    "wrapper": "Argument",
    "selector_field": "TABLE_TYPE",
    "selector_value": "BEAMFORCE"
  },
  "source_page": "19_POST_AnalysisResult_1.md"
}
```
