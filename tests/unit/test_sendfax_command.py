"""The commands the Send Fax page runs are the ones the original ran.

``tests/fixtures/legacy_sendfax_commands.json`` was recorded by running the original ``submit_fax()`` (PHP 5.6) with
stand-ins for ``sendfax`` and ``faxcover`` that write down their arguments, for the same inputs as below. Two things
the original did are left out on purpose: options whose value is empty (``-x ''``, ``-S ''``: it passed them anyway) and the
placeholders for empty address parts in the comment (``{to-address:''}``), which carry no information.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from namifax.services.sendfax_command import Sender, SendRequest, build_plan

LEGACY = json.loads((Path(__file__).parent.parent / "fixtures" / "legacy_sendfax_commands.json").read_text())

SENDER = Sender(name="Alice Sender", username="alice", email="alice@corp.test", company="Corp Inc", location="Seoul",
                voicenumber="+82 2 555 0100", faxnumber="+82 2 555 0101")

SCENARIOS = {
    "plain_file": (dict(destinations="5550100"), ["/tmp/a.pdf"]),
    "all_options": (dict(destinations="5550100", to_person="Bob Receiver", to_company="Acme Ltd", regarding="Invoice 42",
                         comments="Hello there!", modem="ttyS0", priority="10", numtries="3", killtime="3",
                         killtime_unit="days", sendtime=True, sendtime_hour="14", sendtime_min="30", tsi="MY TSI",
                         notify_requeue=True, to_location="Busan", to_voicenumber="051 555 0111"),
                    ["/tmp/a.pdf", "/tmp/b.pdf"]),
    "many_destinations": (dict(destinations="5550100;5550101;5550102"), ["/tmp/a.pdf"]),
    "cover_only": (dict(destinations="5550100", coverpage=True, whichcover="standard.ps", to_person="Bob", to_company="Acme",
                        regarding="Hi", comments="Please read"), []),
    "cover_and_file": (dict(destinations="5550100", coverpage=True, whichcover="urgent.ps"), ["/tmp/a.pdf"]),
    "address_in_comments": (dict(destinations="5550100", comments="note", to_address="Main St 1", to_zip="12345",
                                 to_city="Town"), ["/tmp/a.pdf"]),
}
CONFIG = dict(images_dir="/inst/images", tmp_dir="/tmp/")
VALUELESS = {"sendfax": {"-D", "-R", "-n"}, "faxcover": set()}


def _normalise(command: dict) -> list[str]:
    """The recorded arguments without the empty options and empty address placeholders; temporary paths made generic."""
    args, out, i = command["args"], [], 0
    while i < len(args):
        arg = args[i]
        if re.fullmatch(r"-[A-Za-z]", arg) and arg not in VALUELESS[command["cmd"]] and i + 1 < len(args):
            value = args[i + 1]
            if arg == "-c":
                value = re.sub(r"\{to-(?:address|zip|city):''\}", "", value)
            if value != "":
                out += [arg, value]
            i += 2
            continue
        out.append(arg)
        i += 1
    return [re.sub(r"/tmp/(?!a\.pdf|b\.pdf)\S+", "<tmp>", a) for a in out]


def _plan(name):
    fields, files = SCENARIOS[name]
    return build_plan(SendRequest(files=files, **fields), SENDER, **CONFIG)


def _argv(step):
    return [re.sub(r"/tmp/\S+(?<!a\.pdf)(?<!b\.pdf)$", "<tmp>", a) for a in step.argv[1:]]


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_the_commands_match_the_original(name):
    plan = _plan(name)
    assert [(s.argv[0], _argv(s)) for s in plan.steps] == [(c["cmd"], _normalise(c)) for c in LEGACY[name]]


def test_with_a_cover_page_only_the_cover_is_made_first_and_sent_as_the_file():
    plan = _plan("cover_only")
    cover, send = plan.steps
    assert cover.argv[0] == "faxcover" and cover.stdout_to and send.argv[-1] == cover.stdout_to
    assert cover.stdout_to.startswith("/tmp/") and cover.stdout_to.endswith(".ps")
    assert plan.cleanup == [cover.stdout_to]


def test_several_destinations_go_into_a_file_one_per_line():
    plan = _plan("many_destinations")
    (path, content), = plan.files_to_write.items()
    assert content == "5550100\n5550101\n5550102\n" and "-z" in plan.steps[0].argv and path in plan.steps[0].argv


def test_a_single_destination_has_no_spaces_or_semicolons_and_the_person_in_front():
    plan = build_plan(SendRequest(destinations=" 555 0100;\r\n", to_person="Bob", files=["/x.pdf"]), SENDER, **CONFIG)
    assert plan.steps[0].argv[plan.steps[0].argv.index("-d") + 1] == "Bob@5550100"


def test_the_destination_file_drops_characters_hylafax_does_not_dial():
    plan = build_plan(SendRequest(destinations="555-0100;(555)0101", files=["/x.pdf"]), SENDER, **CONFIG)
    assert list(plan.files_to_write.values()) == ["5550100\n5550101\n"]


def test_the_modem_any_adds_no_host_option_and_a_named_modem_does():
    anyone = build_plan(SendRequest(destinations="1", modem="any", files=["/x"]), SENDER, **CONFIG).steps[0].argv
    named = build_plan(SendRequest(destinations="1", modem="ttyS1", files=["/x"]), SENDER, **CONFIG).steps[0].argv
    assert "-h" not in anyone and named[named.index("-h") + 1] == "ttyS1@localhost"


def test_the_default_tsi_is_used_when_the_form_has_none():
    plan = build_plan(SendRequest(destinations="1", files=["/x"]), SENDER, default_tsi="OUR TSI", **CONFIG)
    argv = plan.steps[0].argv
    assert argv[argv.index("-S") + 1] == "OUR TSI"


def test_values_with_shell_characters_stay_single_arguments():
    plan = build_plan(SendRequest(destinations="1", to_company="A; rm -rf / `x` $(y)", files=["/x"]), SENDER, **CONFIG)
    argv = plan.steps[0].argv
    assert argv[argv.index("-x") + 1] == "A; rm -rf / `x` $(y)"
