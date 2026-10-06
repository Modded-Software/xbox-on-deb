#!/usr/bin/env python3
"""Emit the kernel-import and library catalogues for Ghost.xbe.

Cross-references the 137 kernel ordinals Ghost imports against the xboxrecomp
kernel bridge (src/kernel/kernel_thunks.c + kernel_bridge.c), so the gap list is
mechanical rather than guessed.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
SYMBOLS = os.path.join(ROOT, "symbols")
XR = os.path.join(os.path.dirname(ROOT), "refs", "xboxrecomp")

a = json.load(open(os.path.join(BUILD, "analysis.json")))

thunks = open(os.path.join(XR, "src/kernel/kernel_thunks.c"), encoding="utf-8", errors="replace").read()
bridge = open(os.path.join(XR, "src/kernel/kernel_bridge.c"), encoding="utf-8", errors="replace").read()
impl = set(int(m) for m in re.findall(r"case\s+(\d+)\s*:", thunks))
impl |= set(int(m) for m in re.findall(r"ordinal\s+(\d+)", bridge))

os.makedirs(SYMBOLS, exist_ok=True)
with open(os.path.join(SYMBOLS, "ghost.kernel_imports.txt"), "w") as fh:
    fh.write("# ordinal  status  name\n")
    for i in sorted(a["kernel_imports"], key=lambda x: x["ordinal"]):
        status = "impl" if i["ordinal"] in impl else "MISSING"
        fh.write(f"{i['ordinal']:>4}  {status:7} {i['name']}\n")

with open(os.path.join(SYMBOLS, "ghost.libraries.json"), "w") as fh:
    json.dump({"libraries": a["libraries"], "sections": a["sections"],
               "xdk_version": a["xdk_version"]}, fh, indent=1)

missing = [i for i in a["kernel_imports"] if i["ordinal"] not in impl]
print(f"kernel imports: {len(a['kernel_imports'])}  missing: {len(missing)}")
for i in missing:
    print(f"  MISSING #{i['ordinal']} {i['name']}")
print("libraries:", [l.get("name") for l in a["libraries"]])

# Unimplemented instructions, bucketed by section. Most entries in data-heavy
# sections (BINK*, DOLPHIN-like tables) are decode noise from disassembling
# data; the real ones are port I/O (in/out) and the privileged interrupt
# sequence (cli/sti/int/int1) -- exactly the hardware+preemption escape hatch.
summary_path = os.path.join(BUILD, "recomp_all", "summary.json")
if os.path.exists(summary_path):
    s = json.load(open(summary_path))
    secs = [(int(x["virtual_addr"], 16), int(x["virtual_addr"], 16) + x["virtual_size"], x["name"])
            for x in a["sections"]]

    def section_of(va):
        for lo, hi, name in secs:
            if lo <= va < hi:
                return name
        return "?"

    real_mnemonics = {"in", "out", "insb", "insd", "outsb", "outsd", "cli", "sti", "int", "int1"}
    with open(os.path.join(SYMBOLS, "ghost.unimplemented.txt"), "w") as fh:
        fh.write("# mnemonic  section  va  (in/out are port I/O -> GPU/APU MMIO)\n")
        for mn, addrs in sorted(s["unimplemented"].items()):
            for va in sorted(set(addrs)):
                fh.write(f"{mn:8} {section_of(va):10} 0x{va:08X}\n")
    real = [(mn, va) for mn, addrs in s["unimplemented"].items()
            if mn in real_mnemonics for va in addrs]
    in_text = [(mn, va) for mn, va in real if section_of(va) in (".text", "D3D", "XACTENG", "WMADEC")]
    print(f"unimplemented instructions: {sum(len(v) for v in s['unimplemented'].values())} total, "
          f"{len(real)} hardware/int, {len(in_text)} in code sections")

