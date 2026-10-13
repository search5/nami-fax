"""Input validation and sanitization layer replacing legacy FormRules.php.

Provides robust rule-based form validation, email checking, date parsing,
and HTML/DB escaping.
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Callable

FR_ARRAY = 10
FR_STRING = 11
FR_NUMBER = 12
FR_DATE = 13
FR_EMAIL = 14

EMAIL_REGEX = re.compile(r"^[^@\s]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$")


def is_valid_email(email: str) -> bool:
    """Validate email address format."""
    if not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def is_valid_date(date_str: str, fmt: str = "ymd", delim: str = "/") -> bool:
    """Validate date string with specified format and delimiter."""
    if not isinstance(date_str, str):
        return False
    parts = date_str.split(delim)
    if len(parts) != 3:
        return False

    try:
        if fmt == "ymd":
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        elif fmt == "mdy":
            m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
        elif fmt == "dmy":
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            return False

        if y < 100:
            y += 2000
        datetime(year=y, month=m, day=d)
        return True
    except (ValueError, OverflowError):
        return False


class FormRules:
    """Form validation and rule enforcement class."""

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self._rules: dict[str, dict[str, Any]] = {}
        self._errors: list[str] = []
        self._form_errors: list[str] = []
        self._css_errors: list[str] = []
        self._date_fmt = "ymd"
        self._date_delim = "/"

    @property
    def values(self) -> dict[str, Any]:
        """Return processed rule values."""
        return {k: v["value"] for k, v in self._rules.items()}

    def set_date_fmt(self, fmt: str, delim: str) -> None:
        """Set date format and delimiter."""
        self._date_fmt = fmt.lower()
        self._date_delim = delim

    def new_rule(
        self,
        varname: str,
        defaultval: Any = None,
        vartype: int = FR_STRING,
        minlen: int | None = None,
        maxlen: int | None = None,
        error_str: str | None = None,
        required: bool = False,
        sanitize: bool = True,
        execfunc: Callable[[Any], tuple[bool, str] | bool] | None = None,
    ) -> bool:
        """Register a new field validation rule."""
        if not varname:
            self._errors.append("Must set variable name")
            return False

        if varname in self._rules:
            self._errors.append(f"{varname} already exists")
            return False

        if required and not error_str:
            self._errors.append(f"{varname} is required and requires error string")
            return False

        self._rules[varname] = {
            "value": defaultval,
            "vartype": vartype,
            "minlen": minlen,
            "maxlen": maxlen,
            "required": required,
            "error": error_str,
            "sanitize": sanitize,
            "execfunc": execfunc,
        }
        return True

    def clear_errors(self) -> None:
        """Reset error lists."""
        self._errors.clear()
        self._form_errors.clear()
        self._css_errors.clear()

    def get_form_errors(self) -> list[str]:
        """Return list of form-level validation errors."""
        return list(self._form_errors)

    def get_errors(self) -> list[str]:
        """Return internal error list."""
        return list(self._errors)

    def get_css_error_ids(self) -> str | None:
        """Return comma-separated CSS IDs for elements with errors."""
        if not self._css_errors:
            return None
        return "#" + ", #".join(self._css_errors)

    def process_form(self, post_data: dict[str, Any]) -> bool:
        """Validate input dictionary against configured rules."""
        valid = True

        # Check required fields
        for varname, rule in self._rules.items():
            if rule["required"]:
                if varname not in post_data or post_data[varname] in (None, ""):
                    self._form_errors.append(rule["error"] or f"{varname} is required")
                    if varname not in self._css_errors:
                        self._css_errors.append(varname)
                    valid = False

        for varname, val in post_data.items():
            if varname not in self._rules:
                continue

            rule = self._rules[varname]
            vtype = rule["vartype"]

            # Type checking
            if val is not None and val != "":
                type_ok = True
                if vtype == FR_NUMBER:
                    try:
                        float(val)
                    except ValueError:
                        type_ok = False
                elif vtype == FR_EMAIL:
                    type_ok = is_valid_email(str(val))
                elif vtype == FR_DATE:
                    type_ok = is_valid_date(str(val), fmt=self._date_fmt, delim=self._date_delim)
                elif vtype == FR_ARRAY:
                    type_ok = isinstance(val, (list, tuple))

                if not type_ok:
                    self._form_errors.append(rule["error"] or f"{varname} has invalid type")
                    if varname not in self._css_errors:
                        self._css_errors.append(varname)
                    valid = False
                    continue

                # Length constraints
                if isinstance(val, (str, list, tuple)):
                    length = len(val)
                    if rule["minlen"] is not None and length < rule["minlen"]:
                        self._form_errors.append(rule["error"] or f"{varname} too short")
                        if varname not in self._css_errors:
                            self._css_errors.append(varname)
                        valid = False
                        continue
                    if rule["maxlen"] is not None and length > rule["maxlen"]:
                        self._form_errors.append(rule["error"] or f"{varname} too long")
                        if varname not in self._css_errors:
                            self._css_errors.append(varname)
                        valid = False
                        continue

                # Custom callback function
                if rule["execfunc"] is not None:
                    res = rule["execfunc"](val)
                    func_ok = res if isinstance(res, bool) else res[0]
                    func_msg = "" if isinstance(res, bool) else res[1]

                    if not func_ok:
                        self._form_errors.append(func_msg or rule["error"] or f"{varname} failed custom check")
                        if varname not in self._css_errors:
                            self._css_errors.append(varname)
                        valid = False
                        continue

            rule["value"] = val

        return valid

    def html_ready(self) -> dict[str, Any]:
        """Return values with HTML entity escaping applied."""
        res: dict[str, Any] = {}
        for varname, rule in self._rules.items():
            val = rule["value"]
            if rule["sanitize"] and isinstance(val, str):
                res[varname] = html.escape(val, quote=True)
            else:
                res[varname] = val
        return res

    def db_ready(self) -> dict[str, Any]:
        """Return values safely typed for database insertion."""
        res: dict[str, Any] = {}
        for varname, rule in self._rules.items():
            val = rule["value"]
            if rule["vartype"] == FR_NUMBER:
                res[varname] = 0 if val is None or val == "" else val
            else:
                res[varname] = val
        return res
