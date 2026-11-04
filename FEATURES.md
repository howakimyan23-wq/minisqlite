# MiniSQLite Feature Checklist

All 23 project features are implemented and covered by the project tests where behavior is applicable.

| No. | Feature | Description |
| ---: | --- | --- |
| 1 | CREATE TABLE | Creates tables with INTEGER and TEXT columns. |
| 2 | INSERT INTO | Inserts complete or selected-column records. |
| 3 | SELECT * | Retrieves records from a table. |
| 4 | WHERE | Filters records using comparison conditions. |
| 5 | UPDATE | Modifies existing records. |
| 6 | DELETE | Removes matching records, or all records without WHERE. |
| 7 | Data persistence | Saves and restores the JSON database in `minidb.json`. |
| 8 | Error handling | Reports invalid syntax, missing objects, type errors, and constraint violations. |
| 9 | REPL commands | Supports `.help`, `.tables`, `.schema`, `.database`, `.count`, `.version`, `.exit`, and `.quit`. |
| 10 | DROP TABLE | Removes an entire table. |
| 11 | ALTER TABLE ADD COLUMN | Adds a nullable INTEGER or TEXT column. |
| 12 | COUNT() | Counts rows or non-NULL values. |
| 13 | ORDER BY | Sorts query results with ASC or DESC. |
| 14 | LIMIT | Restricts the number of returned records. |
| 15 | DISTINCT | Removes duplicate result rows. |
| 16 | AND and OR | Combines multiple WHERE conditions. |
| 17 | LIKE | Supports `%` and `_` text patterns. |
| 18 | Aggregate functions | Supports SUM(), AVG(), MIN(), and MAX(). |
| 19 | GROUP BY | Groups records for aggregate queries. |
| 20 | JOIN | Supports INNER JOIN with an ON equality condition. |
| 21 | CREATE INDEX | Stores index metadata for a table column. |
| 22 | PRIMARY KEY | Enforces uniqueness and non-NULL values. |
| 23 | FOREIGN KEY | Validates references to another table. |

## Verification

```bash
python3 -m py_compile minisqlite.py test_minisqlite.py
python3 -m unittest -v
```
