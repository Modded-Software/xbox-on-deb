# Xbox-on-deb developer Makefile.
#
#   make            launch the game for hands-on testing (the default target)
#   make help       list every target
#
# Recipes live in scripts/ so they are usable on their own too.

SHELL := /bin/bash
.DEFAULT_GOAL := launch

# ── default: the thing you do most ──────────────────────────────────────
.PHONY: launch
launch: ## Launch the game for manual testing (keyboard+mouse, repeat watchdog).
	bash scripts/18-launch-user.sh

.PHONY: relaunch
relaunch: ## Stop any running game and launch a fresh one.
	bash scripts/18-launch-user.sh

.PHONY: watch
watch: ## Launch with the repeating hang watchdog (diagnosis only).
	WATCH=1 bash scripts/18-launch-user.sh

# ── input record / replay ───────────────────────────────────────────────
# The user launch records every input edge with a timestamp. Replay feeds a
# recording back hands-free, at the same times and with no X focus, so a crash
# seen while playing can be reproduced deterministically. Each session has an
# explicit id; the file is pfx/drive_c/recomp-record-<SESSION>.txt in the prefix.
SESSION ?=

.PHONY: record-session
record-session: ## Record a hands-on session: make record-session SESSION=<id>
	@test -n "$(SESSION)" || { echo "usage: make record-session SESSION=<id>"; exit 2; }
	SESSION=$(SESSION) bash scripts/18-launch-user.sh

.PHONY: replay-session
replay-session: ## Replay a recording: make replay-session SESSION=<id>
	@test -n "$(SESSION)" || { echo "usage: make replay-session SESSION=<id>"; exit 2; }
	REPLAY=1 SESSION=$(SESSION) bash scripts/18-launch-user.sh

.PHONY: sessions
sessions: ## List recorded input sessions (prefix pfx/drive_c/recomp-record-*.txt).
	@set -- $(HOME)/Games/scghost-prefix/pfx/drive_c/recomp-record-*.txt; \
	if [ -e "$$1" ]; then printf '%s\n' "$$@"; else echo "no recordings yet"; fi

# ── recomp code generation ──────────────────────────────────────────────
# The generated tree (recomp/game/src/recomp/gen/) is a build artifact and is
# gitignored: it is regenerated wholesale from Ghost.xbe. Never hand-patch it.
# Corrections belong in recomp/game/src/recomp_manual.c (recomp_lookup_manual),
# recomp/config/ (seed_functions.json, annotations.csv) or recomp/tools/.
OUT ?= recomp/build/gen_fresh

.PHONY: regen
regen: ## Regenerate the recompiled C into OUT (reuses analysis): make regen OUT=DIR
	bash scripts/20-regen-recomp.sh "$(OUT)"

.PHONY: regen-full
regen-full: ## Regenerate everything incl. disassembly (seeded): make regen-full OUT=DIR
	MODE=full bash scripts/20-regen-recomp.sh "$(OUT)"

.PHONY: gen-diff
gen-diff: ## Regenerate into OUT and diff against the in-tree generated sources (finds hand edits).
	bash scripts/20-regen-recomp.sh "$(OUT)"
	-diff -ru recomp/game/src/recomp/gen "$(OUT)"

.PHONY: gen-sync
gen-sync: ## Replace the in-tree generated sources with a freshly generated OUT.
	bash scripts/20-regen-recomp.sh "$(OUT)"
	rm -f recomp/game/src/recomp/gen/*.c recomp/game/src/recomp/gen/*.h
	cp "$(OUT)"/*.c "$(OUT)"/*.h recomp/game/src/recomp/gen/

# ── build & test ────────────────────────────────────────────────────────
.PHONY: build
build: ## Build ghost.exe from the recompiled sources.
	recomp/game/build.sh

.PHONY: test
test: ## Run the full automated test suite (launches the game).
	recomp/tests/run.py

.PHONY: test-input
test-input: ## Run only the input tests.
	recomp/tests/run.py --only input

.PHONY: test-mouse
test-mouse: ## Run only the mouse tests.
	recomp/tests/run.py --only mouse

.PHONY: test-gameplay
test-gameplay: ## Run only the mission/gameplay tests.
	recomp/tests/run.py --only mission

.PHONY: test-one
test-one: ## Run one test by name substring: make test-one T=dpad
	recomp/tests/run.py --only "$(T)"

.PHONY: scene
scene: ## Print and record the current scene fingerprint.
	recomp/tests/run.py --scene --record

# ── inspect & maintain ──────────────────────────────────────────────────
.PHONY: stop
stop: ## Stop the running game and its wineserver.
	bash scripts/16-stop-recomp.sh

.PHONY: kill
kill: stop ## Alias for stop.

.PHONY: log
log: ## Show the tail of the runtime boot log: make log LINES=500
	bash scripts/17-show-log.sh "$(LINES)"

.PHONY: toolkit
toolkit: ## Clone or fast-forward the toolkit fork into refs/xboxrecomp.
	bash scripts/19-setup-toolkit.sh

.PHONY: clean
clean: ## Remove build output (keeps generated sources).
	rm -rf recomp/game/build

.PHONY: help
help: ## List the targets.
	@echo "targets:"
	@echo "  launch         launch the game for manual testing (default)"
	@echo "  regen          regenerate recompiled C into OUT (reuses analysis)"
	@echo "  regen-full     regenerate incl. disassembly (seeded)"
	@echo "  gen-diff       regenerate into OUT + diff vs in-tree gen (find hand edits)"
	@echo "  gen-sync       replace in-tree gen with freshly generated OUT"
	@echo "  build          build ghost.exe"
	@echo "  test           run the full test suite"
	@echo "  test-input     input tests only"
	@echo "  test-mouse     mouse tests only"
	@echo "  test-gameplay  mission/gameplay tests only"
	@echo "  test-one       one test: make test-one T=<substring>"
	@echo "  scene          print + record the current scene fingerprint"
	@echo "  stop           stop the game and its wineserver (alias: kill)"
	@echo "  relaunch       stop then launch a fresh game"
	@echo "  record-session record input: make record-session SESSION=<id>"
	@echo "  replay-session replay input: make replay-session SESSION=<id>"
	@echo "  sessions       list recorded input sessions"
	@echo "  log            tail the latest runtime log (LINES=200)"
	@echo "  toolkit        clone/update the toolkit fork (refs/xboxrecomp)"
	@echo "  clean          remove build output"
	@echo "  help           this list"
