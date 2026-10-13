"""Unit tests for avantfax.common.validators (FormRules layer)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.common.validators import (
    FR_ARRAY,
    FR_DATE,
    FR_EMAIL,
    FR_NUMBER,
    FR_STRING,
    FormRules,
    is_valid_email,
)


class TestValidators(unittest.TestCase):
    def test_standalone_is_valid_email(self):
        """Test standalone email validator."""
        self.assertTrue(is_valid_email("user@example.com"))
        self.assertTrue(is_valid_email("admin.name+tag@sub.domain.co.kr"))
        self.assertFalse(is_valid_email("invalid-email"))
        self.assertFalse(is_valid_email("@example.com"))
        self.assertFalse(is_valid_email("user@"))

    def test_formrules_required_and_string_size(self):
        """Test required rule and string length constraints."""
        fr = FormRules()
        fr.new_rule("username", vartype=FR_STRING, minlen=3, maxlen=10, required=True, error_str="Invalid username")

        # Missing required field
        self.assertFalse(fr.process_form({}))
        self.assertIn("Invalid username", fr.get_form_errors())
        self.assertEqual(fr.get_css_error_ids(), "#username")

        # Too short string
        fr.clear_errors()
        self.assertFalse(fr.process_form({"username": "ab"}))
        self.assertIn("Invalid username", fr.get_form_errors())

        # Too long string
        fr.clear_errors()
        self.assertFalse(fr.process_form({"username": "toolongstring123"}))

        # Valid string
        fr.clear_errors()
        self.assertTrue(fr.process_form({"username": "valid_user"}))
        self.assertEqual(fr.values["username"], "valid_user")

    def test_formrules_number_and_email_types(self):
        """Test number and email vartypes."""
        fr = FormRules()
        fr.new_rule("age", vartype=FR_NUMBER, error_str="Age must be numeric", required=True)
        fr.new_rule("email", vartype=FR_EMAIL, error_str="Invalid email", required=True)

        # Invalid number and email
        self.assertFalse(fr.process_form({"age": "not_a_number", "email": "bad_email"}))
        self.assertEqual(len(fr.get_form_errors()), 2)

        # Valid
        fr.clear_errors()
        self.assertTrue(fr.process_form({"age": "25", "email": "good@test.com"}))

    def test_formrules_custom_execfunc(self):
        """Test custom validation callback function."""
        def check_positive(val):
            return int(val) > 0, "Must be positive"

        fr = FormRules()
        fr.new_rule("count", vartype=FR_NUMBER, execfunc=check_positive)

        self.assertFalse(fr.process_form({"count": "-5"}))
        self.assertIn("Must be positive", fr.get_form_errors())

        fr.clear_errors()
        self.assertTrue(fr.process_form({"count": "10"}))

    def test_html_ready_escaping(self):
        """Test html_ready output escaping."""
        fr = FormRules()
        fr.new_rule("comment", vartype=FR_STRING, sanitize=True)
        fr.process_form({"comment": "<script>alert('xss')</script>"})

        ready = fr.html_ready()
        self.assertIn("&lt;script&gt;", ready["comment"])
        self.assertNotIn("<script>", ready["comment"])


if __name__ == "__main__":
    unittest.main()
