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
.PHONY: kill
kill: ## Stop any running game and its wineserver.
	bash scripts/16-kill-recomp.sh

.PHONY: log
log: ## Show the tail of the runtime boot log: make log LINES=500
	bash scripts/17-show-log.sh "$(LINES)"

.PHONY: patch
patch: ## Regenerate the toolkit patch from refs/xboxrecomp.
	git -C refs/xboxrecomp diff -- \
		src/input/xinput_device.c \
		src/kernel/kernel_bridge.c \
		src/kernel/nv2a_gpu.h \
		src/kernel/nv2a_gpu_d3d11.cpp \
		src/kernel/nv2a_pb_exec.c \
		src/kernel/xbox_memory_layout.c \
		src/usb/ohci.c \
		src/usb/usb_gamepad.c \
		src/usb/usb_gamepad.h \
		src/video/fb_present.c \
		src/video/video_player.h \
		> recomp/patches/xboxrecomp-input-perf.patch

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
	@echo "  kill           stop the game and its wineserver"
	@echo "  log            tail the runtime boot log (LINES=200)"
	@echo "  patch          regenerate the toolkit patch"
	@echo "  clean          remove build output"
	@echo "  help           this list"
