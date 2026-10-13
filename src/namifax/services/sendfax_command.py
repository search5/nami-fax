"""The ``sendfax`` / ``faxcover`` command lines for a fax submitted from the web form (the original's ``submit_fax()``).

``build_plan`` only decides *what to run*: it needs no HylaFAX and touches no file, so it can be checked against the commands
the original produced. The caller writes ``files_to_write``, runs the steps in order (the output of a step with
``stdout_to`` goes to that file), and removes ``cleanup`` afterwards. Arguments are a list, never a shell string, so values
typed into the form cannot be taken for shell syntax.

Left out compared with the original: options whose value is empty (it passed ``-x ''`` and the like) and the placeholders
for empty address parts in the comment (``{to-address:''}``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from namifax.common.helpers import genpasswd


class NothingToSend(ValueError):
    """The form has neither a file nor a cover page, so there is nothing to submit."""


@dataclass
class Sender:
    name: str = ""
    username: str = ""
    email: str = ""
    company: str = ""
    location: str = ""
    voicenumber: str = ""
    faxnumber: str = ""


@dataclass
class SendRequest:
    destinations: str = ""
    files: List[str] = field(default_factory=list)
    modem: Optional[str] = None
    to_person: str = ""
    to_company: str = ""
    regarding: str = ""
    comments: str = ""
    to_location: str = ""
    to_voicenumber: str = ""
    to_address: str = ""
    to_zip: str = ""
    to_city: str = ""
    tsi: str = ""
    coverpage: bool = False
    whichcover: str = ""
    notify_requeue: bool = False
    priority: str = "*"
    numtries: str = ""
    killtime: str = ""
    killtime_unit: str = "hours"
    sendtime: bool = False
    sendtime_hour: str = ""
    sendtime_min: str = ""


@dataclass
class Step:
    argv: List[str]
    stdout_to: Optional[str] = None


@dataclass
class Plan:
    steps: List[Step]
    files_to_write: Dict[str, str] = field(default_factory=dict)
    cleanup: List[str] = field(default_factory=list)


def _opt(flag: str, value: Optional[str]) -> List[str]:
    return [flag, value] if value not in (None, "") else []


def _destinations(request: SendRequest, tmp_dir: str) -> tuple[List[str], Dict[str, str], str]:
    """(options naming the destinations, files to write, the first number)."""
    parts = request.destinations.strip().split(";")
    if len([p for p in parts if p.strip()]) > 1:
        lines = [re.sub(r'[^\w,#*@ "]', "", p) for p in parts if p.strip()]
        path = tmp_dir + genpasswd()
        return ["-z", path], {path: "".join(f"{line}\n" for line in lines)}, lines[0]
    number = re.sub(r"[;\s]", "", request.destinations)
    return ["-d", f"{request.to_person}@{number}" if request.to_person else number], {}, number


def build_plan(request: SendRequest, sender: Sender, *, images_dir: str, tmp_dir: str, default_tsi: str = "") -> Plan:
    if not request.files and not request.coverpage:
        raise NothingToSend("no file and no cover page")

    comment = request.comments
    for key, value in (("to-address", request.to_address), ("to-zip", request.to_zip), ("to-city", request.to_city)):
        if value:
            comment += f"{{{key}:'{value}'}}"           # picked up again by faxcover (the only way to carry them)
    comment = comment.replace("!", "&#33;")

    tsi = request.tsi or default_tsi
    killtime = f"now + {request.killtime} {request.killtime_unit}" if request.killtime else ""
    sendtime = f"{request.sendtime_hour}:{request.sendtime_min}" if request.sendtime and request.sendtime_hour and request.sendtime_min else ""
    priority = request.priority if request.priority and request.priority != "*" else ""

    identity = [*_opt("-o", sender.username), *_opt("-f", sender.email)]
    timing = [*_opt("-t", request.numtries), *_opt("-k", killtime), *_opt("-S", tsi), *_opt("-P", priority),
              *_opt("-a", sendtime)]
    sendfax_args = [*identity, *_opt("-x", request.to_company), *_opt("-c", comment), *_opt("-r", request.regarding),
                    *_opt("-y", request.to_location), *_opt("-V", request.to_voicenumber), *_opt("-X", sender.company),
                    *_opt("-Y", sender.location), *_opt("-U", sender.voicenumber), *_opt("-W", sender.faxnumber), *timing]
    modem = ["-h", f"{request.modem}@localhost"] if request.modem and request.modem != "any" else []
    where, to_write, first = _destinations(request, tmp_dir)
    requeue = "-R" if request.notify_requeue else "-D"

    if request.files:
        cover = ["-C", f"{images_dir}/{request.whichcover}"] if request.coverpage else ["-n"]
        return Plan([Step(["sendfax", requeue, *cover, *sendfax_args, *modem, *where, *request.files])], to_write)

    # only a cover page: make it with faxcover, then send the result as the one file
    cover_file = tmp_dir + genpasswd() + ".ps"
    cover_args = [*_opt("-f", sender.name), *_opt("-t", request.to_person), *_opt("-x", request.to_company),
                  *_opt("-c", comment), *_opt("-r", request.regarding), *_opt("-l", request.to_location),
                  *_opt("-v", request.to_voicenumber), *_opt("-X", sender.company), *_opt("-L", sender.location),
                  *_opt("-V", sender.voicenumber), *_opt("-N", sender.faxnumber)]
    return Plan(
        [Step(["faxcover", *cover_args, "-C", f"{images_dir}/{request.whichcover}", "-p", "0", "-n", first],
              stdout_to=cover_file),
         Step(["sendfax", requeue, "-n", *identity, *_opt("-r", request.regarding), *timing, *modem, *where, cover_file])],
        to_write, cleanup=[cover_file])
