"""Поля контакту, записи та адресна книга з днями народження."""

import re
from collections import UserDict
from datetime import datetime, timedelta


class Field:
    """Базовий клас поля запису."""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Name(Field):
    """Обов'язкове непорожнє ім'я контакту."""

    def __init__(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Contact name must be a non-empty string.")
        super().__init__(value.strip())


class Phone(Field):
    """Номер телефону з рівно 10 цифр від 0 до 9."""

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if (
            not isinstance(value, str)
            or len(value) != 10
            or not value.isascii()
            or not value.isdigit()
        ):
            raise ValueError("Phone number must contain exactly 10 digits.")
        self._value = value


class Birthday(Field):
    """День народження: рядок DD.MM.YYYY перетворюється на datetime."""

    def __init__(self, value):
        try:
            if not isinstance(value, str) or not re.fullmatch(
                r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", value
            ):
                raise ValueError("Incorrect date format.")
            birthday = datetime.strptime(value, "%d.%m.%Y")
        except ValueError as error:
            raise ValueError("Invalid date format. Use DD.MM.YYYY") from error
        super().__init__(birthday)

    def __str__(self):
        return self.value.strftime("%d.%m.%Y")


class Record:
    """Контакт з ім'ям, телефонами та одним необов'язковим днем народження."""

    def __init__(self, name):
        self.name = Name(name)
        self.phones = []
        self.birthday = None

    def add_phone(self, phone):
        self.phones.append(Phone(phone))

    def remove_phone(self, phone):
        found_phone = self.find_phone(phone)
        if found_phone is None:
            raise ValueError("Phone number not found.")
        self.phones.remove(found_phone)

    def edit_phone(self, old_phone, new_phone):
        found_phone = self.find_phone(old_phone)
        if found_phone is None:
            raise ValueError("Phone number not found.")
        found_phone.value = new_phone

    def find_phone(self, phone):
        for saved_phone in self.phones:
            if saved_phone.value == phone:
                return saved_phone
        return None

    def add_birthday(self, birthday):
        # Створення Birthday завершується до зміни наявного значення.
        self.birthday = Birthday(birthday)

    def __str__(self):
        phones = "; ".join(phone.value for phone in self.phones)
        result = f"Contact name: {self.name.value}, phones: {phones}"
        if self.birthday is not None:
            result += f", birthday: {self.birthday}"
        return result


class AddressBook(UserDict):
    """Адресна книга з пошуком імен без залежності від регістру."""

    def _find_key(self, name):
        for saved_name in self.data:
            if saved_name.casefold() == name.casefold():
                return saved_name
        return None

    def add_record(self, record):
        if not isinstance(record, Record):
            raise TypeError("Address book entries must be Record objects.")
        previous_key = self._find_key(record.name.value)
        if previous_key is not None:
            del self.data[previous_key]
        self.data[record.name.value] = record

    def find(self, name):
        key = self._find_key(name)
        return self.data.get(key)

    def delete(self, name):
        key = self._find_key(name)
        return self.data.pop(key, None)

    def get_upcoming_birthdays(self):
        """Повертає привітання за 7 днів включно із сьогодні.

        Вихідні переносяться на понеділок. Формат результату збережено
        з попередньої роботи: name та congratulation_date (YYYY.MM.DD).
        """
        today = datetime.today().date()
        upcoming_birthdays = []

        for record in self.data.values():
            if record.birthday is None:
                continue
            birthday = record.birthday.value.date()

            for year in (today.year, today.year + 1):
                try:
                    next_birthday = birthday.replace(year=year)
                except ValueError:
                    # У невисокосний рік вітаємо народжених 29 лютого 28-го.
                    next_birthday = birthday.replace(year=year, day=28)
                if next_birthday >= today:
                    break

            days_left = (next_birthday - today).days
            if 0 <= days_left < 7:
                congratulation_date = next_birthday
                if congratulation_date.weekday() >= 5:
                    congratulation_date += timedelta(
                        days=7 - congratulation_date.weekday()
                    )

                upcoming_birthdays.append(
                    {
                        "name": record.name.value,
                        "congratulation_date": congratulation_date.strftime(
                            "%Y.%m.%d"
                        ),
                    }
                )

        return sorted(
            upcoming_birthdays, key=lambda item: item["congratulation_date"]
        )
