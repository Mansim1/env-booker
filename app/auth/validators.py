from wtforms import ValidationError

# Forbidden tokens to help block SQL injection
FORBIDDEN_TOKENS = [";", "--", "/*", "*/", "@@"]

def no_sql_injection(form, field):
    """Validates input against common SQL injection patterns"""
    data = field.data or ""
    for token in FORBIDDEN_TOKENS:
        if token in data:
            field.errors[:] = []
            raise ValidationError("Invalid characters in field.")
