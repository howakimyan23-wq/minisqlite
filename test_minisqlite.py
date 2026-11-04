import contextlib
import io
import json
import os
import tempfile
import unittest

import minisqlite


class MiniSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        minisqlite.DB_FILE = os.path.join(self.temp_dir.name, "minidb.json")
        minisqlite.tables = {}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_insert_select_update_delete(self):
        minisqlite.execute("CREATE TABLE students (id INTEGER, name TEXT, city TEXT)")
        minisqlite.execute("INSERT INTO students VALUES (1, 'Անի', 'Երևան')")
        minisqlite.execute("INSERT INTO students VALUES (2, 'Արամ', 'Գյումրի')")
        minisqlite.execute("INSERT INTO students VALUES (3, 'Մանե', 'Երևան')")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            minisqlite.execute("SELECT * FROM students WHERE city = 'Երևան'")
        self.assertIn("Անի", output.getvalue())
        self.assertIn("Մանե", output.getvalue())
        self.assertNotIn("Արամ", output.getvalue())

        minisqlite.execute("UPDATE students SET city = 'Վանաձոր' WHERE id = 2")
        minisqlite.execute("DELETE FROM students WHERE id = 1")
        self.assertEqual(len(minisqlite.tables["students"]["rows"]), 2)
        self.assertEqual(minisqlite.tables["students"]["rows"][0]["city"], "Վանաձոր")

    def test_data_persists_after_reload(self):
        minisqlite.execute("CREATE TABLE students (id INTEGER, name TEXT)")
        minisqlite.execute("INSERT INTO students VALUES (1, 'Անի')")
        with open(minisqlite.DB_FILE, "r", encoding="utf-8") as file:
            saved = json.load(file)
        self.assertEqual(saved["students"]["rows"][0]["name"], "Անի")

        minisqlite.tables = {}
        minisqlite.load_database()
        self.assertEqual(minisqlite.tables["students"]["rows"][0]["id"], 1)

    def test_invalid_types_and_commands_do_not_change_data(self):
        minisqlite.execute("CREATE TABLE students (id INTEGER, name TEXT)")
        with self.assertRaises(ValueError):
            minisqlite.execute("INSERT INTO students VALUES ('one', 'Անի')")
        with self.assertRaises(ValueError):
            minisqlite.execute("UPDATE students SET id = 'two' WHERE id = 1")
        with self.assertRaises(ValueError):
            minisqlite.execute("NOT SQL")
        self.assertEqual(minisqlite.tables["students"]["rows"], [])

    def test_duplicate_table_and_service_commands(self):
        minisqlite.execute("CREATE TABLE students (id INTEGER)")
        with self.assertRaises(ValueError):
            minisqlite.execute("CREATE TABLE students (id INTEGER)")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            minisqlite.execute(".tables")
            minisqlite.execute(".schema students")
            minisqlite.execute(".database")
            minisqlite.execute(".help")
        text = output.getvalue()
        self.assertIn("students", text)
        self.assertIn("INTEGER", text)
        self.assertIn(".exit", text)

    def test_additional_service_commands(self):
        minisqlite.execute("CREATE TABLE students (id INTEGER, name TEXT)")
        minisqlite.execute("INSERT INTO students VALUES (1, 'Անի')")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            minisqlite.execute(".count students")
            minisqlite.execute(".count")
            minisqlite.execute(".describe students")
            minisqlite.execute(".version")
        text = output.getvalue()
        self.assertIn("students: 1 տող", text)
        self.assertIn("Ընդամենը՝ 1 տող", text)
        self.assertIn("INTEGER", text)
        self.assertIn("MiniSQLite version 2.0", text)

    def test_ddl_constraints_and_indexes(self):
        minisqlite.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        minisqlite.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, FOREIGN KEY (user_id) REFERENCES users (id))")
        minisqlite.execute("INSERT INTO users VALUES (1, 'Անի')")
        minisqlite.execute("INSERT INTO posts VALUES (1, 1, 'Բարև')")
        with self.assertRaises(ValueError):
            minisqlite.execute("INSERT INTO users VALUES (1, 'Կրկնվող')")
        with self.assertRaises(ValueError):
            minisqlite.execute("INSERT INTO posts VALUES (2, 99, 'Սխալ հղում')")
        minisqlite.execute("ALTER TABLE users ADD COLUMN city TEXT")
        minisqlite.execute("CREATE INDEX user_name_idx ON users (name)")
        self.assertIn("city", minisqlite.tables["users"]["columns"])
        self.assertEqual(minisqlite.tables["users"]["indexes"][0]["name"], "user_name_idx")
        minisqlite.execute("DROP TABLE posts")
        self.assertNotIn("posts", minisqlite.tables)

    def test_query_features_and_join(self):
        minisqlite.execute("CREATE TABLE cities (id INTEGER PRIMARY KEY, name TEXT)")
        minisqlite.execute("CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT, city_id INTEGER)")
        minisqlite.execute("INSERT INTO cities VALUES (1, 'Երևան')")
        minisqlite.execute("INSERT INTO cities VALUES (2, 'Գյումրի')")
        minisqlite.execute("INSERT INTO people VALUES (1, 'Անի', 1)")
        minisqlite.execute("INSERT INTO people VALUES (2, 'Արամ', 2)")
        minisqlite.execute("INSERT INTO people VALUES (3, 'Անի', 1)")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            minisqlite.execute("SELECT DISTINCT name FROM people ORDER BY name DESC LIMIT 1")
            minisqlite.execute("SELECT * FROM people WHERE city_id = 1 AND name LIKE 'Ա%'")
            minisqlite.execute("SELECT COUNT(*) FROM people")
            minisqlite.execute("SELECT city_id, COUNT(*) FROM people GROUP BY city_id")
            minisqlite.execute("SELECT people.name, cities.name FROM people INNER JOIN cities ON people.city_id = cities.id")
        text = output.getvalue()
        self.assertIn("(1 տող)", text)
        self.assertIn("3", text)
        self.assertIn("Երևան", text)


if __name__ == "__main__":
    unittest.main()
