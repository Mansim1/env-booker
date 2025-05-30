from wtforms import ValidationError

FORBIDDEN_TOKENS = [";", "--", "/*", "*/", "@@"]

def no_sql_injection(form, field):
    data = field.data or ""
    for token in FORBIDDEN_TOKENS:
        if token in data:
            field.errors[:] = []
            raise ValidationError("Invalid characters in field.")
