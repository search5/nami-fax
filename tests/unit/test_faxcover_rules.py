"""faxcover like the original: values go into the template with PostScript-safe text, exact symbols (XXXX-to is not XXXX-to-company),
the page count can count the cover page, only .ps (or .html when allowed) templates are accepted, HTML covers go through html2ps."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from namifax.cli import faxcover as mod


def _run(capsys, tmp_path, template, args, name="cover.ps", **module):
    path = tmp_path / name
    path.write_text(template, encoding="utf-8")
    argv = ["faxcover", "-f", "Sender", "-n", "5551234", "-C", str(path), *args]
    from contextlib import ExitStack
    with ExitStack() as stack:
        for k, v in module.items():
            stack.enter_context(patch.object(mod, k, v))
        stack.enter_context(patch.object(mod, "cli_session", side_effect=RuntimeError("no db")))
        mod.run_faxcover(argv)
    return capsys.readouterr().out


def test_symbols_are_matched_exactly(capsys, tmp_path):
    out = _run(capsys, tmp_path, "(To: XXXX-to) (Co: XXXX-to-company) (Fax: XXXX-to-fax-number)\n", ["-t", "Rita", "-x", "Beta"])
    assert out == "(To: Rita) (Co: Beta) (Fax: 5551234)\n"


def test_an_unknown_symbol_is_left_empty(capsys, tmp_path):
    assert _run(capsys, tmp_path, "(XXXX-nothing)\n", []) == "()\n"


def test_parentheses_and_backslashes_cannot_break_the_postscript(capsys, tmp_path):
    out = _run(capsys, tmp_path, "(XXXX-regarding)\n", ["-r", r"Re: a) (b \ c"])
    assert out == "(Re: a\\) \\(b \\\\ c)\n"


def test_accents_become_octal_codes(capsys, tmp_path):
    out = _run(capsys, tmp_path, "(XXXX-to)\n", ["-t", "José"])
    assert out == "(Jos\\216)\n"                      # é in the Mac Roman encoding the original used


def test_characters_the_font_cannot_show_become_a_question_mark(capsys, tmp_path):
    out = _run(capsys, tmp_path, "(XXXX-to)\n", ["-t", "김 Kim"])
    assert out == "(? Kim)\n"


def test_html_entities_are_decoded_first(capsys, tmp_path):
    out = _run(capsys, tmp_path, "(XXXX-to)\n", ["-t", "A &amp; B"])
    assert out == "(A & B)\n"


def test_the_page_count_can_include_the_cover_page(capsys, tmp_path):
    assert _run(capsys, tmp_path, "(XXXX-page-count)\n", ["-p", "3"]) == "(3)\n"
    assert _run(capsys, tmp_path, "(XXXX-page-count)\n", ["-p", "3"], NUM_PAGES_FOLLOW=True) == "(4)\n"


def test_comments_are_wrapped_into_numbered_lines(capsys, tmp_path):
    out = _run(capsys, tmp_path, "(XXXX-comments0)\n(XXXX-comments1)\n", ["-c", "alpha beta gamma", "-z", "10"])
    assert out == "(alpha beta)\n(gamma)\n"


def test_a_template_of_another_kind_is_ignored_for_the_default(capsys, tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "default.ps").write_text("(default XXXX-to)\n")
    out = _run(capsys, tmp_path, "(odd XXXX-to)\n", ["-t", "Rita"], name="cover.txt", INSTALLDIR=str(tmp_path), COVERPAGE_FILE="default.ps")
    assert out == "(default Rita)\n"


def test_an_html_cover_is_used_only_when_allowed_and_goes_through_html2ps(capsys, tmp_path):
    html = "<p>XXXX-to</p><p>XXXX-regarding</p>\n"
    run = MagicMock(return_value=MagicMock(returncode=0, stdout=b"%!PS-from-html2ps\n"))
    with patch("subprocess.run", run):
        out = _run(capsys, tmp_path, html, ["-t", "Rita", "-r", "<b>x</b>"], name="cover.html", USE_HTML_COVERPAGE=True)
    assert "%!PS-from-html2ps" in out
    assert run.call_args.args[0][0].endswith("html2ps")
    (tmp_path / "images").mkdir(exist_ok=True)
    (tmp_path / "images" / "plain.ps").write_text("(plain)\n")
    out2 = _run(capsys, tmp_path, "<p>x</p>\n", [], name="cover.html", USE_HTML_COVERPAGE=False,
                INSTALLDIR=str(tmp_path), COVERPAGE_FILE="plain.ps")
    assert out2 == "(plain)\n"
