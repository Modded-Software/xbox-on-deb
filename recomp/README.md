# StarCraft: Ghost (Xbox) - Static Recompilation

Recompiles the leaked `Ghost.xbe` dev build to native code.

## Layout

```
recomp/
  README.md              this file
  tools/                  our scripts (symbol map, annotator, source grouping)
  config/                 seeds, annotations, fixups
  build/                  regenerable pipeline output (gitignored)
  src/                    generated C + manual overrides (generated is gitignored)
  docs/                   research notes (local, gitignored)
  symbols/                source-mapping output (local, gitignored)
```

The `build/` directory holds output from the `xboxrecomp` toolkit
(`refs/xboxrecomp`). The toolkit is its own repository, a fork of upstream at
`Modded-Software/xboxrecomp` that carries this project's runtime work as commits
on `main`; `scripts/19-setup-toolkit.sh` (or `make toolkit`) clones or
fast-forwards it. `refs/` is gitignored because it is a separate clone, not
because the work is uncommitted.

## Readable generated code

The generated C is named, annotated and grouped by original source file:

1. `tools/apply_symbol_map.py` - real names onto the function database.
2. `tools/annotate_gen.py` - per-function banner with source file + signature
   + hand notes from `config/annotations.csv`.
3. `tools/group_by_source.py` - one `.c` per original `.cpp`.

The design notes, audits, and architecture write-ups live in the local,
undistributed `docs/` tree.

## Why this is unusually well-set-up

The dropped build shipped **next to its linker MAP and its PDB**:

- `Ghost.map` resolves (by section:offset) to exactly the `Ghost.xbe` entry point
  `0x001B3FBB` - it describes *this* XBE, not the PC build beside it.
- It carries **24,725 real symbols**, game code included (not just the XDK).
- The PDB maps the defining object of each symbol to its **original source file**.

Recovering that mapping lets the recompiler carry real function names instead of
synthetic ones.

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

The recompiled `ghost.exe` builds (`make build`), boots, reaches the menus, and
plays missions with audio and input. Open defects, performance work, and
per-task run history are tracked in the local, undistributed `docs/` and
`diary/` trees.
