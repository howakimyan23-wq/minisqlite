import json
import os
import re


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "minidb.json")
LEGACY_DB_FILE = os.path.join(os.path.dirname(BASE_DIR), "minidb.json")
VERSION = "2.0"
tables = {}


def load_database():
    global tables
    database_file = DB_FILE
    migrate = False
    if not os.path.exists(database_file) and os.path.exists(LEGACY_DB_FILE):
        database_file = LEGACY_DB_FILE
        migrate = True
    if not os.path.exists(database_file):
        tables = {}
        return
    try:
        with open(database_file, "r", encoding="utf-8") as file:
            loaded = json.load(file)
        if not isinstance(loaded, dict):
            raise ValueError("Տվյալների բազայի ձևաչափը սխալ է։")
        tables = loaded
        for table in tables.values():
            table.setdefault("primary_key", None)
            table.setdefault("foreign_keys", {})
            table.setdefault("indexes", [])
        if migrate:
            save()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(f"Չհաջողվեց կարդալ տվյալների բազան։ {error}") from error


def save():
    with open(DB_FILE, "w", encoding="utf-8") as file:
        json.dump(tables, file, ensure_ascii=False, indent=2)


def split_top_level(text, separator=","):
    parts, current = [], []
    quoted = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            current.append(char)
            if quoted and index + 1 < len(text) and text[index + 1] == "'":
                current.append("'")
                index += 1
            else:
                quoted = not quoted
        elif char == separator and not quoted:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    if quoted:
        raise ValueError("Տեքստային արժեքի չակերտները փակված չեն։")
    parts.append("".join(current).strip())
    if any(not part for part in parts):
        raise ValueError("Արժեքների ցանկը սխալ է։")
    return parts


def parse_value(value):
    value = value.strip()
    if value.upper() == "NULL":
        return None
    if re.fullmatch(r"'(?:''|[^'])*'", value):
        return value[1:-1].replace("''", "'")
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    raise ValueError("Անթույլատրելի արժեք։ Օգտագործիր INTEGER, TEXT կամ NULL։")


def check_table(name):
    if name not in tables:
        raise ValueError(f"Աղյուսակը '{name}' գոյություն չունի։")


def table_meta(table):
    table.setdefault("primary_key", None)
    table.setdefault("foreign_keys", {})
    table.setdefault("indexes", [])
    return table


def check_type(column, data_type, value, nullable=True):
    if value is None and nullable:
        return
    if data_type == "INTEGER" and not isinstance(value, int):
        raise ValueError(f"{column} պետք է լինի INTEGER։")
    if data_type == "TEXT" and not isinstance(value, str):
        raise ValueError(f"{column} պետք է լինի TEXT։")


def check_constraints(name, row, ignore_row=None):
    table = table_meta(tables[name])
    primary_key = table.get("primary_key")
    if primary_key and row.get(primary_key) is None:
        raise ValueError(f"PRIMARY KEY '{primary_key}' չի կարող լինել NULL։")
    if primary_key:
        for other in table["rows"]:
            if other is not ignore_row and other.get(primary_key) == row.get(primary_key):
                raise ValueError(f"PRIMARY KEY '{primary_key}' պետք է եզակի լինի։")
    for column, reference in table.get("foreign_keys", {}).items():
        value = row.get(column)
        if value is None:
            continue
        ref_table, ref_column = reference
        check_table(ref_table)
        if not any(item.get(ref_column) == value for item in tables[ref_table]["rows"]):
            raise ValueError(f"FOREIGN KEY '{column}' հղում է չգտնվող գրառման։")


def parse_condition(condition):
    match = re.fullmatch(
        r"\s*([\w.]+)\s*(=|!=|<>|<=|>=|<|>|LIKE)\s*(NULL|'(?:''|[^'])*'|-?\d+)\s*",
        condition,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("WHERE պայմանը սխալ է։")
    return match.group(1), match.group(2).upper(), parse_value(match.group(3))


def split_logic(text, operator):
    parts, current, quoted = [], [], False
    index = 0
    marker = f" {operator} "
    while index < len(text):
        char = text[index]
        if char == "'":
            quoted = not quoted
            current.append(char)
            if quoted is False and index + 1 < len(text) and text[index + 1] == "'":
                current.append("'")
                index += 1
        elif not quoted and text[index:index + len(marker)].upper() == marker:
            parts.append("".join(current).strip())
            current = []
            index += len(marker) - 1
        else:
            current.append(char)
        index += 1
    parts.append("".join(current).strip())
    return parts


def resolve_value(row, column):
    if column in row:
        return row[column]
    matches = [value for key, value in row.items() if key.endswith("." + column)]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(f"Սյունակը '{column}' միանշանակ չէ կամ գոյություն չունի։")


def like(value, pattern):
    if not isinstance(value, str) or not isinstance(pattern, str):
        return False
    regex = "^" + re.escape(pattern).replace(r"%", ".*").replace(r"_", ".") + "$"
    return re.match(regex, value, re.DOTALL) is not None


def compare(actual, operator, expected):
    if operator == "LIKE":
        return like(actual, expected)
    if operator == "=" or operator == "LIKE":
        return actual == expected
    if operator in ("!=", "<>"):
        return actual != expected
    if actual is None or expected is None:
        return False
    return {"<": actual < expected, "<=": actual <= expected,
            ">": actual > expected, ">=": actual >= expected}[operator]


def matches(row, condition):
    or_parts = split_logic(condition, "OR")
    for or_part in or_parts:
        and_parts = split_logic(or_part, "AND")
        if all(compare(resolve_value(row, parse_condition(part)[0]),
                       parse_condition(part)[1], parse_condition(part)[2])
               for part in and_parts):
            return True
    return False


def parse_columns(raw):
    columns, primary_key = {}, None
    foreign_keys = {}
    for definition in split_top_level(raw):
        parts = definition.split()
        if not parts:
            raise ValueError("Սյունակի կառուցվածքը սխալ է։")
        if parts[0].upper() == "PRIMARY":
            match = re.fullmatch(r"PRIMARY\s+KEY\s*\((\w+)\)", definition, re.IGNORECASE)
            if not match:
                raise ValueError("PRIMARY KEY-ի ձևաչափը սխալ է։")
            primary_key = match.group(1)
            continue
        if parts[0].upper() == "FOREIGN":
            match = re.fullmatch(r"FOREIGN\s+KEY\s*\((\w+)\)\s+REFERENCES\s+(\w+)\s*\((\w+)\)", definition, re.IGNORECASE)
            if not match:
                raise ValueError("FOREIGN KEY-ի ձևաչափը սխալ է։")
            foreign_keys[match.group(1)] = (match.group(2), match.group(3))
            continue
        if len(parts) < 2 or parts[1].upper() not in ("INTEGER", "TEXT"):
            raise ValueError("Աջակցվում են միայն INTEGER և TEXT տեսակները։")
        column, data_type = parts[0], parts[1].upper()
        if not re.fullmatch(r"\w+", column) or column in columns:
            raise ValueError("Սյունակի անունը սխալ է կամ կրկնվում է։")
        columns[column] = data_type
        extra = " ".join(parts[2:]).upper()
        if "PRIMARY KEY" in extra:
            primary_key = column
        reference = re.search(r"REFERENCES\s+(\w+)\s*\((\w+)\)", " ".join(parts[2:]), re.IGNORECASE)
        if reference:
            foreign_keys[column] = (reference.group(1), reference.group(2))
    if not columns:
        raise ValueError("Աղյուսակը պետք է ունենա սյունակներ։")
    if primary_key and primary_key not in columns:
        raise ValueError("PRIMARY KEY սյունակը գոյություն չունի։")
    for column in foreign_keys:
        if column not in columns:
            raise ValueError("FOREIGN KEY սյունակը գոյություն չունի։")
    return columns, primary_key, foreign_keys


def execute_select(command):
    pattern = (r"SELECT\s+(DISTINCT\s+)?(.+?)\s+FROM\s+(\w+)"
               r"(?:\s+INNER\s+JOIN\s+(\w+)\s+ON\s+([\w.]+)\s*=\s*([\w.]+))?"
               r"(?:\s+WHERE\s+(.+?))?(?:\s+GROUP\s+BY\s+([\w.]+))?"
               r"(?:\s+ORDER\s+BY\s+([\w.]+)(?:\s+(ASC|DESC))?)?"
               r"(?:\s+LIMIT\s+(\d+))?$")
    match = re.fullmatch(pattern, command, re.IGNORECASE)
    if not match:
        return False
    distinct, projection, name, join_name, left_key, right_key, condition, group_by, order_by, direction, limit = match.groups()
    check_table(name)
    base = table_meta(tables[name])
    rows = []
    for source in base["rows"]:
        row = dict(source)
        row.update({f"{name}.{key}": value for key, value in source.items()})
        rows.append(row)
    if join_name:
        check_table(join_name)
        joined = []
        for left in rows:
            for right in tables[join_name]["rows"]:
                combined = dict(left)
                combined.update(right)
                combined.update({f"{join_name}.{key}": value for key, value in right.items()})
                if resolve_value(combined, left_key) == resolve_value(combined, right_key):
                    joined.append(combined)
        rows = joined
    if condition:
        rows = [row for row in rows if matches(row, condition)]
    if order_by:
        rows.sort(key=lambda row: (resolve_value(row, order_by) is None, resolve_value(row, order_by)), reverse=direction.upper() == "DESC")
    if group_by:
        groups = {}
        for row in rows:
            groups.setdefault(resolve_value(row, group_by), []).append(row)
        rows = [group[0] | {"__group__": group} for group in groups.values()]
    aggregate_items = []
    for item in split_top_level(projection):
        aggregate = re.fullmatch(r"(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(\*|[\w.]+)\s*\)", item, re.IGNORECASE)
        aggregate_items.append(aggregate.groups() if aggregate else None)
    if any(aggregate_items):
        groups = [row.get("__group__", [row]) for row in rows] if group_by else [rows]
        projection_items = split_top_level(projection)
        columns = [item.strip() for item in projection_items]
        output = []
        for group in groups:
            result = {}
            for item, aggregate in zip(projection_items, aggregate_items):
                if aggregate:
                    function, column = aggregate
                    values = [resolve_value(row, column) for row in group] if column != "*" else group
                    values = [value for value in values if value is not None]
                    if function.upper() == "COUNT": value = len(values)
                    elif function.upper() == "SUM": value = sum(values)
                    elif function.upper() == "AVG": value = sum(values) / len(values) if values else None
                    elif function.upper() == "MIN": value = min(values) if values else None
                    else: value = max(values) if values else None
                    result[item.strip()] = value
                else:
                    result[item.strip()] = resolve_value(group[0], item.strip())
            output.append(result)
        rows = output
    else:
        columns = [key.strip() for key in split_top_level(projection)] if projection.strip() != "*" else list(base["columns"])
        if projection.strip() == "*" and join_name:
            columns = list(base["columns"]) + list(tables[join_name]["columns"])
    if distinct:
        unique, filtered = set(), []
        for row in rows:
            values = tuple(resolve_value(row, column) for column in columns)
            if values not in unique:
                unique.add(values)
                filtered.append(row)
        rows = filtered
    if limit:
        rows = rows[:int(limit)]
    if not rows:
        print("Տվյալներ չկան։")
        return True
    print(" | ".join(columns))
    print("-" * 40)
    for row in rows:
        print(" | ".join(str(resolve_value(row, column)) for column in columns))
    print(f"({len(rows)} տող)")
    return True


def execute(command):
    command = command.strip().rstrip(";").strip()
    if not command:
        return
    lowered = command.lower()
    if lowered in (".exit", ".quit"):
        raise SystemExit
    if lowered == ".help":
        print("CREATE/INSERT/SELECT/UPDATE/DELETE, DROP TABLE, ALTER TABLE ADD COLUMN, CREATE INDEX")
        print("WHERE, AND, OR, LIKE, ORDER BY, LIMIT, DISTINCT, COUNT/SUM/AVG/MIN/MAX, GROUP BY, INNER JOIN")
        print(".tables, .schema/.describe, .database, .count, .version, .exit/.quit")
        return
    if lowered == ".tables":
        print("\n".join(tables) if tables else "Աղյուսակներ չկան։")
        return
    if lowered == ".version":
        print(f"MiniSQLite version {VERSION}")
        return
    count_match = re.fullmatch(r"\.count(?:\s+(\w+))?", command, re.IGNORECASE)
    if count_match:
        name = count_match.group(1)
        if name:
            check_table(name)
            print(f"{name}: {len(tables[name]['rows'])} տող")
        else:
            print(f"Ընդամենը՝ {sum(len(table['rows']) for table in tables.values())} տող")
        return
    if lowered == ".database":
        for name, table in tables.items():
            print(f"\nԱղյուսակ՝ {name}\nՍյունակներ՝ {table['columns']}")
            for row in table["rows"]:
                print(row)
        if not tables:
            print("Տվյալների բազան դատարկ է։")
        return
    schema = re.fullmatch(r"\.(?:schema|describe)\s+(\w+)", command, re.IGNORECASE)
    if schema:
        name = schema.group(1)
        check_table(name)
        print(tables[name]["columns"])
        return
    match = re.fullmatch(r"CREATE\s+TABLE\s+(\w+)\s*\((.+)\)", command, re.IGNORECASE)
    if match:
        name, definition = match.groups()
        if name in tables:
            raise ValueError("Այս աղյուսակն արդեն գոյություն ունի։")
        columns, primary_key, foreign_keys = parse_columns(definition)
        tables[name] = {"columns": columns, "rows": [], "primary_key": primary_key, "foreign_keys": foreign_keys, "indexes": []}
        save()
        print(f"Աղյուսակը '{name}' ստեղծվեց։")
        return
    match = re.fullmatch(r"DROP\s+TABLE\s+(\w+)", command, re.IGNORECASE)
    if match:
        name = match.group(1)
        check_table(name)
        del tables[name]
        save()
        print(f"Աղյուսակը '{name}' հեռացվեց։")
        return
    match = re.fullmatch(r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+)\s+(INTEGER|TEXT)", command, re.IGNORECASE)
    if match:
        name, column, data_type = match.groups()
        check_table(name)
        table = table_meta(tables[name])
        if column in table["columns"]:
            raise ValueError("Այս սյունակն արդեն գոյություն ունի։")
        table["columns"][column] = data_type.upper()
        for row in table["rows"]:
            row[column] = None
        save()
        print(f"Սյունակը '{column}' ավելացվեց։")
        return
    match = re.fullmatch(r"CREATE\s+(?:INDEX\s+(\w+)\s+ON\s+(\w+)\s*\((\w+)\)|INDEX\s+ON\s+(\w+)\s*\((\w+)\))", command, re.IGNORECASE)
    if match:
        index_name, name, column, fallback_name, fallback_column = match.groups()
        name, column = name or fallback_name, column or fallback_column
        check_table(name)
        if column not in tables[name]["columns"]:
            raise ValueError("Index-ի սյունակը գոյություն չունի։")
        index_name = index_name or f"idx_{name}_{column}"
        table_meta(tables[name])["indexes"].append({"name": index_name, "column": column})
        save()
        print(f"Index '{index_name}' ստեղծվեց։")
        return
    match = re.fullmatch(r"INSERT\s+INTO\s+(\w+)(?:\s*\(([^)]+)\))?\s+VALUES\s*\((.+)\)", command, re.IGNORECASE)
    if match:
        name, raw_columns, raw_values = match.groups()
        check_table(name)
        table = table_meta(tables[name])
        columns = [item.strip() for item in raw_columns.split(",")] if raw_columns else list(table["columns"])
        if len(columns) != len(set(columns)) or any(column not in table["columns"] for column in columns):
            raise ValueError("INSERT սյունակների ցանկը սխալ է։")
        values = split_top_level(raw_values)
        if len(values) != len(columns):
            raise ValueError("Արժեքների քանակը չի համապատասխանում սյունակներին։")
        row = {column: None for column in table["columns"]}
        for column, raw_value in zip(columns, values):
            value = parse_value(raw_value)
            check_type(column, table["columns"][column], value, nullable=column != table.get("primary_key"))
            row[column] = value
        check_constraints(name, row)
        table["rows"].append(row)
        save()
        print("Տվյալն ավելացվեց։")
        return
    if lowered.startswith("select "):
        if execute_select(command):
            return
    match = re.fullmatch(r"UPDATE\s+(\w+)\s+SET\s+(\w+)\s*=\s*([^ ]+(?:\s+[^ ]+)?)\s+WHERE\s+(.+)", command, re.IGNORECASE)
    if match:
        name, column, raw_value, condition = match.groups()
        check_table(name)
        table = table_meta(tables[name])
        if column not in table["columns"]:
            raise ValueError("Այդ սյունակը գոյություն չունի։")
        value = parse_value(raw_value)
        check_type(column, table["columns"][column], value, nullable=column != table.get("primary_key"))
        for row in table["rows"]:
            if matches(row, condition):
                row[column] = value
                check_constraints(name, row, ignore_row=row)
        save()
        print("Տվյալները փոփոխվեցին։")
        return
    match = re.fullmatch(r"DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+))?", command, re.IGNORECASE)
    if match:
        name, condition = match.groups()
        check_table(name)
        rows = tables[name]["rows"]
        tables[name]["rows"] = [row for row in rows if condition and not matches(row, condition)] if condition else []
        save()
        print(f"Ջնջվեց {len(rows) - len(tables[name]['rows'])} տող։")
        return
    raise ValueError("Անհայտ կամ սխալ հրաման։ Գրիր .help։")


def main():
    load_database()
    print("MiniSQLite")
    print("Type .help for help.")
    while True:
        try:
            command = input("\nminidb> ")
            if command.strip().lower() in (".exit", ".quit"):
                print("Ցտեսություն։")
                break
            execute(command)
        except SystemExit:
            print("Ցտեսություն։")
            break
        except (ValueError, KeyError) as error:
            print("ՍԽԱԼ:", error)
        except EOFError:
            print("\nՑտեսություն։")
            break
        except KeyboardInterrupt:
            print("\nՕգտագործիր .exit հրամանը։")


if __name__ == "__main__":
    main()
