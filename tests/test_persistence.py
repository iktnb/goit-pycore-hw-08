"""Перевірки збереження даних без доступу до робочої адресної книги."""

import contextlib
import io
import pickle
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from address_book import AddressBook, Birthday, Name, Phone, Record
from main import main
from storage import DATA_FILE, load_data, save_data


ROOT = Path(__file__).resolve().parents[1]


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="hw08-test-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.path = self.folder / "contacts.pkl"
        self.book = AddressBook()
        record = Record("Іван")
        record.add_phone("0501234567")
        record.add_phone("0671234567")
        record.add_birthday("29.02.2000")
        self.book.add_record(record)
        self.book.add_record(Record("WithoutBirthday"))

    def launch_main(self, commands):
        output = io.StringIO()
        with patch("builtins.input", side_effect=commands):
            with contextlib.redirect_stdout(output):
                status = main(self.path)
        return status, output.getvalue()

    def test_first_launch_returns_empty_address_book(self):
        book = load_data(self.path)
        self.assertIsInstance(book, AddressBook)
        self.assertFalse(book)
        self.assertFalse(self.path.exists())

    def test_complete_book_round_trip_keeps_types_and_values(self):
        save_data(self.book, self.path)
        restored = load_data(self.path)
        self.assertIsInstance(restored, AddressBook)
        self.assertIsNot(restored, self.book)
        record = restored.find("ІВАН")
        self.assertIsInstance(record, Record)
        self.assertIsInstance(record.name, Name)
        self.assertEqual(record.name.value, "Іван")
        self.assertTrue(all(isinstance(phone, Phone) for phone in record.phones))
        self.assertEqual([phone.value for phone in record.phones],
                         ["0501234567", "0671234567"])
        self.assertIsInstance(record.birthday, Birthday)
        self.assertEqual(record.birthday.value, datetime(2000, 2, 29))
        self.assertIsNone(restored.find("withoutbirthday").birthday)
        self.assertEqual(restored.find("WithoutBirthday").phones, [])
        self.assertEqual(len(restored), 2)

    def test_restored_records_still_support_edits_and_validation(self):
        save_data(self.book, self.path)
        restored = load_data(self.path)
        record = restored.find("іван")
        record.edit_phone("0501234567", "0991234567")
        with self.assertRaises(ValueError):
            record.edit_phone("0991234567", "bad")
        record.add_birthday("01.01.1990")
        save_data(restored, self.path)
        reloaded = load_data(self.path).find("Іван")
        self.assertEqual(reloaded.phones[0].value, "0991234567")
        self.assertEqual(str(reloaded.birthday), "01.01.1990")
        self.assertEqual(self.book.find("Іван").phones[0].value, "0501234567")

    def test_saved_file_is_a_standard_pickle(self):
        save_data(self.book, self.path)
        with self.path.open("rb") as stream:
            restored = pickle.load(stream)
        self.assertIsInstance(restored, AddressBook)
        self.assertEqual(len(restored), 2)

    def test_empty_book_round_trip(self):
        save_data(AddressBook(), self.path)
        self.assertIsInstance(load_data(self.path), AddressBook)
        self.assertFalse(load_data(self.path))

    def test_string_filename_supported(self):
        save_data(self.book, str(self.path))
        self.assertEqual(len(load_data(str(self.path))), 2)

    def test_default_file_is_next_to_the_application(self):
        self.assertEqual(DATA_FILE, ROOT / "addressbook.pkl")

    def test_second_save_replaces_previous_state(self):
        save_data(self.book, self.path)
        self.book.delete("Іван")
        save_data(self.book, self.path)
        self.assertIsNone(load_data(self.path).find("Іван"))
        self.assertEqual(len(load_data(self.path)), 1)
        self.assertEqual(list(self.folder.iterdir()), [self.path])

    def test_failed_serialization_preserves_previous_file(self):
        save_data(self.book, self.path)
        original = self.path.read_bytes()
        self.book.unpicklable = lambda: None
        with self.assertRaises((AttributeError, pickle.PicklingError)):
            save_data(self.book, self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.folder.iterdir()), [self.path])
        self.assertEqual(len(load_data(self.path)), 2)

    def test_failed_replacement_preserves_previous_file(self):
        save_data(self.book, self.path)
        original = self.path.read_bytes()
        with patch("storage.Path.replace", side_effect=PermissionError("Read only")):
            with self.assertRaises(PermissionError):
                save_data(self.book, self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.folder.iterdir()), [self.path])

    def test_save_rejects_wrong_type_without_modifying_existing_file(self):
        save_data(self.book, self.path)
        original = self.path.read_bytes()
        with self.assertRaises(TypeError):
            save_data({}, self.path)
        self.assertEqual(self.path.read_bytes(), original)

    def test_load_rejects_wrong_object_type(self):
        self.path.write_bytes(pickle.dumps({"name": "not an address book"}))
        with self.assertRaisesRegex(ValueError, "AddressBook"):
            load_data(self.path)

    def test_load_does_not_hide_corrupted_or_empty_file(self):
        for contents in (b"not a pickle", b""):
            with self.subTest(contents=contents):
                self.path.write_bytes(contents)
                with self.assertRaises((pickle.UnpicklingError, EOFError)):
                    load_data(self.path)

    def test_exit_close_eof_and_ctrl_c_all_save(self):
        for finish in ("exit", "close", EOFError(), KeyboardInterrupt()):
            with self.subTest(finish=repr(finish)):
                self.path.unlink(missing_ok=True)
                status, output = self.launch_main([
                    "add John 0501234567", "add-birthday John 29.02.2000", finish
                ])
                self.assertEqual(status, 0)
                self.assertIn("Good bye!", output)
                record = load_data(self.path).find("john")
                self.assertEqual(record.phones[0].value, "0501234567")
                self.assertEqual(str(record.birthday), "29.02.2000")

    def test_main_loads_and_preserves_existing_contacts(self):
        save_data(self.book, self.path)
        status, output = self.launch_main([
            "all", "add New 0991234567", "phone іван", "exit"
        ])
        self.assertEqual(status, 0)
        self.assertIn("Contact name: Іван", output)
        self.assertIn("0501234567; 0671234567", output)
        self.assertEqual(len(load_data(self.path)), 3)

    def test_failed_load_exits_without_overwriting_or_asking_for_input(self):
        for contents in (b"broken", b"", pickle.dumps([])):
            with self.subTest(contents=contents):
                self.path.write_bytes(contents)
                with patch("builtins.input") as mocked_input:
                    with contextlib.redirect_stdout(io.StringIO()) as output:
                        status = main(self.path)
                self.assertEqual(status, 1)
                mocked_input.assert_not_called()
                self.assertIn("Could not load address book", output.getvalue())
                self.assertEqual(self.path.read_bytes(), contents)

    def test_failed_save_is_reported_with_error_status(self):
        with patch("main.save_data", side_effect=PermissionError("Read only")):
            status, output = self.launch_main(["add John 0501234567", "exit"])
        self.assertEqual(status, 1)
        self.assertIn("Could not save address book: Read only", output)

    def test_unexpected_loop_error_still_saves_current_book(self):
        save_data(self.book, self.path)
        with patch("main.run_bot", side_effect=RuntimeError("Unexpected error")):
            with self.assertRaises(RuntimeError):
                main(self.path)
        self.assertEqual(len(load_data(self.path)), 2)

    def test_new_process_restores_data_from_another_working_directory(self):
        app = self.folder / "application"
        app.mkdir()
        for filename in ("address_book.py", "storage.py", "main.py"):
            shutil.copy2(ROOT / filename, app / filename)

        def run(commands, working_directory):
            result = subprocess.run(
                [sys.executable, str(app / "main.py")], input="\n".join(commands) + "\n",
                text=True, capture_output=True, cwd=working_directory, timeout=10
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(result.stderr)
            return result.stdout

        run(["add John 0501234567", "add john 0671234567",
             "add-birthday John 29.02.2000", "exit"], app)
        output = run(["phone JOHN", "show-birthday John", "all", "close"], self.folder)
        self.assertIn("0501234567; 0671234567", output)
        self.assertIn("birthday: 29.02.2000", output)
        self.assertTrue((app / "addressbook.pkl").exists())
        self.assertFalse((self.folder / "addressbook.pkl").exists())
        run(["change John 0501234567 0991234567", "exit"], self.folder)
        self.assertIn("0991234567; 0671234567", run(["phone John", "exit"], app))


if __name__ == "__main__":
    unittest.main()
