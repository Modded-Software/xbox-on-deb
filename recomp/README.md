# StarCraft: Ghost (Xbox) — Static Recompilation

Turn the leaked `Ghost.xbe` dev build into native code instead of running it
under Cxbx-Reloaded, whose HLE makes the boot sequence take ~5 minutes and whose
D3D path is a dead end for this title.

This directory is the project. The emulator work lives at the repo root; this is
a separate direction.

## Layout

```
recomp/
  README.md              this file
  docs/                   research notes and the plan (read these first)
  tools/                  our scripts (symbol map, annotator, source grouping)
  symbols/                our source-mapping files (committed)
  config/                 seeds, annotations, fixups (committed)
  build/                  regenerable pipeline output (gitignored)
  src/                    generated C + manual overrides (generated is gitignored)
```

The `build/` directory holds output from the `xboxrecomp` toolkit
(`refs/xboxrecomp`). The toolkit is its own repository, a fork of upstream at
`Modded-Software/xboxrecomp` that carries this project's runtime work as commits
on `main`; `scripts/19-setup-toolkit.sh` (or `make toolkit`) clones or
fast-forwards it. `refs/` is gitignored because it is a separate clone, not
because the work is uncommitted.

## Readable generated code

The generated C is named, annotated and grouped by original source file:

1. `tools/apply_symbol_map.py` — real names onto the function database.
2. `tools/annotate_gen.py` — per-function banner with source file + signature
   + hand notes from `config/annotations.csv`.
3. `tools/group_by_source.py` — one `.c` per original `.cpp`.

See [docs/07-decomp-workflow.md](docs/07-decomp-workflow.md),
[docs/10-architecture.md](docs/10-architecture.md) for the whole system, and
[docs/11-audit.md](docs/11-audit.md) for its complexity and known problems.

## Why this is unusually well-set-up

The dropped build shipped **next to its linker MAP and its PDB**:

- `Ghost.map` resolves (by section:offset) to exactly the `Ghost.xbe` entry point
  `0x001B3FBB` — it describes *this* XBE, not the PC build beside it.
- It carries **24,725 real symbols**, game code included (not just the XDK).
- `Ghost.pdb` maps the defining object of each symbol to its **original source
  file** (`c:/star/code/game/ai/aiclass.cpp`, …).

We already produced a source map with **16,114 / 17,307 (93.1%) of detected
functions named** and **8,188 (47.3%) tied to a source file**, across 222 source
files. The reference port had to rebuild this with Ghidra/IDA and got ~134 names.

See [docs/04-source-map.md](docs/04-source-map.md).

## Pipeline (run on Linux)

```bash
# one-time
uv venv .venv-recomp && uv pip install --python .venv-recomp/bin/python capstone pefile

# analysis (from refs/xboxrecomp)
cd refs/xboxrecomp
../../.venv-recomp/bin/python -m tools.xbe_parser <Ghost.xbe> --json <out>/analysis.json
../../.venv-recomp/bin/python -m tools.rtti <Ghost.xbe> -o <out>/rtti.json
../../.venv-recomp/bin/python -m tools.disasm <Ghost.xbe> --analysis-json <out>/analysis.json -o <out>/disasm -v
../../.venv-recomp/bin/python -m tools.func_id <Ghost.xbe> --functions <out>/disasm/functions.json --strings <out>/disasm/strings.json --xrefs <out>/disasm/xrefs.json -o <out>/func_id
../../.venv-recomp/bin/python -m tools.abi_analysis <Ghost.xbe> --functions <out>/disasm/functions.json --identified <out>/func_id/identified_functions.json --output-dir <out>/abi

# our symbol map
../../.venv-recomp/bin/python recomp/tools/build_symbol_map.py
```

## Status

Research and analysis complete; generation/runtime bring-up not started. See
[docs/05-strategy.md](docs/05-strategy.md) for the plan and
[docs/06-open-questions.md](docs/06-open-questions.md) for what is unresolved.
