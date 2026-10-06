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
	@echo "  build          build ghost.exe"
	@echo "  test           run the full test suite"
	@echo "  test-input     input tests only"
	@echo "  test-mouse     mouse tests only"
	@echo "  test-gameplay  mission/gameplay tests only"
	@echo "  test-one       one test: make test-one T=<substring>"
	@echo "  scene          print + record the current scene fingerprint"
	@echo "  stop           stop the game and its wineserver (alias: kill)"
	@echo "  relaunch       stop then launch a fresh game"
	@echo "  log            tail the latest runtime log (LINES=200)"
	@echo "  toolkit        clone/update the toolkit fork (refs/xboxrecomp)"
	@echo "  clean          remove build output"
	@echo "  help           this list"
