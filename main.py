"""CLI-бот з адресною книгою та збереженням даних між запусками."""

import pickle
from datetime import datetime
from functools import wraps

from address_book import AddressBook, Birthday, Field, Name, Phone, Record
from storage import DATA_FILE, load_data, save_data


def input_error(func):
    """Повертає повідомлення замість переривання роботи бота."""

    @wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError:
            return "Contact not found."
        except ValueError as error:
            return str(error) or "Invalid command arguments."
        except IndexError:
            return "Enter user name."

    return inner


def parse_input(user_input):
    """Нормалізує команду, зберігаючи регістр імені у відображенні."""
    parts = user_input.strip().split()
    if not parts:
        return ("",)
    command, *args = parts
    return command.lower(), *args


def get_record(name, book):
    record = book.find(name)
    if record is None:
        raise KeyError(name)
    return record


@input_error
def add_contact(args, book):
    if len(args) != 2:
        raise ValueError("Usage: add <name> <phone>")
    name, phone = args
    record = book.find(name)
    if record is None:
        record = Record(name)
        # Некоректний телефон не повинен залишати в книзі порожній запис.
        record.add_phone(phone)
        book.add_record(record)
        return "Contact added."

    record.add_phone(phone)
    return "Contact updated."


@input_error
def change_contact(args, book):
    if len(args) != 3:
        raise ValueError("Usage: change <name> <old phone> <new phone>")
    name, old_phone, new_phone = args
    get_record(name, book).edit_phone(old_phone, new_phone)
    return "Contact updated."


@input_error
def show_phone(args, book):
    if len(args) != 1:
        raise ValueError("Usage: phone <name>")
    record = get_record(args[0], book)
    if not record.phones:
        return "No phone numbers saved."
    return "; ".join(phone.value for phone in record.phones)


@input_error
def show_all(args, book):
    if args:
        raise ValueError("The all command takes no arguments.")
    if not book:
        return "No contacts saved."
    return "\n".join(str(record) for record in book.data.values())


@input_error
def add_birthday(args, book):
    if len(args) != 2:
        raise ValueError("Usage: add-birthday <name> <DD.MM.YYYY>")
    name, birthday = args
    get_record(name, book).add_birthday(birthday)
    return "Birthday added."


@input_error
def show_birthday(args, book):
    if len(args) != 1:
        raise ValueError("Usage: show-birthday <name>")
    record = get_record(args[0], book)
    if record.birthday is None:
        return "Birthday is not set."
    return str(record.birthday)


@input_error
def birthdays(args, book):
    if args:
        raise ValueError("The birthdays command takes no arguments.")
    upcoming = book.get_upcoming_birthdays()
    if not upcoming:
        return "No upcoming birthdays in the next 7 days."

    grouped = {}
    for item in upcoming:
        date = datetime.strptime(item["congratulation_date"], "%Y.%m.%d")
        date_text = date.strftime("%d.%m.%Y")
        grouped.setdefault(date_text, []).append(item["name"])
    lines = [f"{day}: {', '.join(names)}" for day, names in grouped.items()]
    return "Upcoming birthdays:\n" + "\n".join(lines)


@input_error
def say_hello(args, book):
    if args:
        raise ValueError("The hello command takes no arguments.")
    return "How can I help you?"


@input_error
def close_bot(args, book):
    if args:
        raise ValueError("The exit and close commands take no arguments.")
    return "Good bye!"


def run_bot(book):
    """Обробляє команди, працюючи з уже завантаженою адресною книгою."""
    handlers = {
        "hello": say_hello,
        "add": add_contact,
        "change": change_contact,
        "phone": show_phone,
        "all": show_all,
        "add-birthday": add_birthday,
        "show-birthday": show_birthday,
        "birthdays": birthdays,
        "exit": close_bot,
        "close": close_bot,
    }
    print("Welcome to the assistant bot!")

    while True:
        try:
            user_input = input("Enter a command: ")
        except (EOFError, KeyboardInterrupt):
            print("\nGood bye!")
            break

        command, *args = parse_input(user_input)
        handler = handlers.get(command)
        if handler is None:
            print("Invalid command.")
            continue

        print(handler(args, book))
        if command in ("close", "exit") and not args:
            break


def main(filename=DATA_FILE):
    try:
        book = load_data(filename)
    except (
        OSError, pickle.PickleError, EOFError, AttributeError,
        ImportError, IndexError, KeyError, TypeError, ValueError, OverflowError
    ) as error:
        print(f"Could not load address book: {error}")
        print("The saved file was not changed.")
        return 1

    save_failed = False
    try:
        run_bot(book)
    finally:
        # Збереження відбувається також після EOF та Ctrl+C.
        try:
            save_data(book, filename)
        except (OSError, pickle.PickleError, TypeError) as error:
            print(f"Could not save address book: {error}")
            save_failed = True

    return 1 if save_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
