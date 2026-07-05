#!/usr/bin/env python3
"""Reapply MWMDeadpool's custom microWakeWord models onto upstream's
home-assistant-voice.yaml.

Upstream ships THREE wake words wired through the config: okay_nabu (kept),
hey_jarvis and hey_mycroft. The hey_jarvis / hey_mycroft ids are referenced not
just in `micro_wake_word.models` but also by the "Wake word sensitivity" select
lambda (`id(hey_jarvis).set_probability_cutoff(...)`). So we can't just drop them
— we SLOT-SWAP them, matching the hand-maintained device configs:

    hey_jarvis  -> hey_margot   (model URL swapped, id swapped, lambda id() swapped)
    hey_mycroft -> hey_laszlo

okay_nabu and stop are left verbatim (their URLs track upstream). Upstream's
per-slot probability cutoffs are preserved (we only rename the id() target).
Comments that mention jarvis/mycroft are left as-is (mirrors the device configs).

Deterministic, idempotent, and fails LOUD if the upstream slots it relies on are
gone — so a silent wake-word change can never ship.

Usage: apply_custom_wakewords.py <path-to-home-assistant-voice.yaml>
"""
import re
import sys
from ruamel.yaml import YAML

CUSTOM_BASE = "https://github.com/MWMDeadpool/micro-wake-word-models/raw/main/models/v2"
# upstream id -> (our id, our model url)
SLOT_MAP = {
    "hey_jarvis": ("hey_margot", f"{CUSTOM_BASE}/hey_margot.json"),
    "hey_mycroft": ("hey_laszlo", f"{CUSTOM_BASE}/hey_laszlo.json"),
}
REQUIRED_KEEP = ["okay_nabu", "stop"]


def die(msg):
    sys.stderr.write(f"[apply-custom-wakewords] FATAL: {msg}\n")
    sys.exit(1)


def main():
    if len(sys.argv) != 2:
        die("expected exactly one arg: path to home-assistant-voice.yaml")
    path = sys.argv[1]

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    with open(path) as f:
        doc = yaml.load(f)

    mww = doc.get("micro_wake_word")
    if mww is None or "models" not in mww:
        die("no `micro_wake_word.models` block found — upstream layout changed")

    ids_present = {m.get("id") for m in mww["models"] if isinstance(m, dict)}

    # 1) Swap the model entries (idempotent: skip a slot already swapped).
    for up_id, (our_id, our_url) in SLOT_MAP.items():
        if up_id in ids_present:
            for m in mww["models"]:
                if isinstance(m, dict) and m.get("id") == up_id:
                    m["model"] = our_url
                    m["id"] = our_id
                    break
        elif our_id in ids_present:
            pass  # already applied on a previous run
        else:
            die(f"upstream slot '{up_id}' missing and '{our_id}' not present — "
                f"upstream restructured its wake-word models; refusing to ship")

    for keep in REQUIRED_KEEP:
        if keep not in ids_present:
            die(f"upstream no longer defines required model '{keep}'")

    # Serialize, then fix the sensitivity-lambda id() references via text pass.
    from io import StringIO
    buf = StringIO()
    yaml.dump(doc, buf)
    text = buf.getvalue()

    # 2) Rename id(hey_jarvis) -> id(hey_margot), id(hey_mycroft) -> id(hey_laszlo)
    for up_id, (our_id, _url) in SLOT_MAP.items():
        text = re.sub(rf"id\(\s*{re.escape(up_id)}\s*\)", f"id({our_id})", text)

    # 3) Fail loud if any orphaned reference survived.
    leftovers = []
    for up_id, (our_id, _url) in SLOT_MAP.items():
        if re.search(rf"id\(\s*{re.escape(up_id)}\s*\)", text):
            leftovers.append(f"id({up_id})")
        if our_id not in text:
            die(f"expected our model id '{our_id}' not found after transform")
    if leftovers:
        die(f"orphaned upstream id references remain: {leftovers}")

    with open(path, "w") as f:
        f.write(text)
    print(f"[apply-custom-wakewords] OK — slots swapped: "
          f"{', '.join(f'{k}->{v[0]}' for k, v in SLOT_MAP.items())}")


if __name__ == "__main__":
    main()
