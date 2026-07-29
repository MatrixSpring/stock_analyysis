from src.core.exceptions import ParamValidateError


def check_not_empty(value, msg: str):
    if value is None or str(value).strip() == "":
        raise ParamValidateError(msg)


def check_positive_number(num, msg: str):
    if not isinstance(num, (int, float)) or num <= 0:
        raise ParamValidateError(msg)
