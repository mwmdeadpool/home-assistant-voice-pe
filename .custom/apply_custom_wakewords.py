#!/usr/bin/env python3
"""Reapply MWMDeadpool's custom microWakeWord models onto upstream's
home-assistant-voice.yaml.

Deterministic + idempotent: rebuilds the `micro_wake_word.models` list to exactly
  [ okay_nabu (from upstream), hey_margot, hey_laszlo, stop (from upstream) ]
keeping upstream's okay_nabu/stop entries verbatim (so their URLs/flags track
upstream), dropping upstream extras (hey_jarvis/hey_mycroft), and injecting the
two custom models. Fails LOUD (non-zero exit) if the upstream anchors it relies
on are missing — so a silent wake-word drop can never ship.

Usage: apply_custom_wakewords.py <path-to-home-assistant-voice.yaml>
"""
import sys
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

CUSTOM_BASE = "https://github.com/MWMDeadpool/micro-wake-word-models/raw/main/models/v2"
# id -> model URL, in the order they should appear between okay_nabu and stop
CUSTOM_MODELS = [
    ("hey_margot", f"{CUSTOM_BASE}/hey_margot.json"),
    ("hey_laszlo", f"{CUSTOM_BASE}/hey_laszlo.json"),
]
KEEP_FROM_UPSTREAM = ["okay_nabu", "stop"]  # anchors that must survive upstream


def die(msg):
    sys.stderr.write(f"[apply-custom-wakewords] FATAL: {msg}\n")
    sys.exit(1)


def main():
    if len(sys.argv) != 2:
        die("expected exactly one arg: path to home-assistant-voice.yaml")
    path = sys.argv[1]

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # don't wrap long model URLs
    with open(path) as f:
        doc = yaml.load(f)

    mww = doc.get("micro_wake_word")
    if mww is None or "models" not in mww:
        die("no `micro_wake_word.models` block found — upstream layout changed")

    models = mww["models"]
    by_id = {}
    for m in models:
        if isinstance(m, dict) and "id" in m:
            by_id[m["id"]] = m

    for anchor in KEEP_FROM_UPSTREAM:
        if anchor not in by_id:
            die(f"upstream no longer defines model id '{anchor}'; refusing to "
                f"generate a config that would silently change wake behaviour")

    # Build the exact desired list, reusing upstream entries verbatim for anchors.
    new_models = [by_id["okay_nabu"]]
    for mid, url in CUSTOM_MODELS:
        entry = CommentedMap()
        entry["model"] = url
        entry["id"] = mid
        new_models.append(entry)
    new_models.append(by_id["stop"])

    mww["models"] = new_models

    with open(path, "w") as f:
        yaml.dump(doc, f)

    ids = [m.get("id") for m in new_models]
    expected = ["okay_nabu", "hey_margot", "hey_laszlo", "stop"]
    if ids != expected:
        die(f"post-write model ids {ids} != expected {expected}")
    print(f"[apply-custom-wakewords] OK — models now: {ids}")


if __name__ == "__main__":
    main()
