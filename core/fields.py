from django.core.exceptions import FieldError
from django.db import models

from .encryption import decrypt, encrypt


class EncryptedTextField(models.TextField):
    """Stored in the database as encrypted text; plain text in Python. Only 'is null' lookups are allowed,
    because every encryption of the same value looks different (random IV), so SQL could never match it."""

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return None if value is None else encrypt(value)

    def from_db_value(self, value, expression, connection):
        return None if value is None else decrypt(value)

    def get_lookup(self, lookup_name):
        if lookup_name != "isnull":
            raise FieldError("Encrypted fields cannot be searched in SQL. Use a blind-index field for exact matches.")
        return super().get_lookup(lookup_name)
