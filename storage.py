"""Збереження та відновлення адресної книги за допомогою pickle."""

import pickle
from pathlib import Path
from tempfile import NamedTemporaryFile

from address_book import AddressBook


DATA_FILE = Path(__file__).resolve().with_name("addressbook.pkl")


def save_data(book, filename=DATA_FILE):
    """Зберігає всю AddressBook, замінюючи файл після успішного запису."""
    if not isinstance(book, AddressBook):
        raise TypeError("Only an AddressBook can be saved.")

    path = Path(filename)
    temporary_path = None
    try:
        # Тимчасовий файл у тій самій папці захищає попередні дані
        # від часткового перезапису, якщо серіалізація не завершиться.
        with NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.",
            suffix=".tmp", delete=False
        ) as stream:
            temporary_path = Path(stream.name)
            pickle.dump(book, stream, protocol=pickle.HIGHEST_PROTOCOL)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_data(filename=DATA_FILE):
    """Завантажує AddressBook або створює порожню при першому запуску."""
    try:
        with Path(filename).open("rb") as stream:
            book = pickle.load(stream)
    except FileNotFoundError:
        return AddressBook()

    if not isinstance(book, AddressBook):
        raise ValueError("The saved file does not contain an AddressBook.")
    return book
