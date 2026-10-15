#!/bin/bash
# Enable cut single-player content in the recompiled StarCraft: Ghost build.
#
# The only hidden-but-present level in this build is **The Borgo Refinery**
# (`1_3_REFINERY` -> `1_3_1a_Hive_StationOuter`); it ships commented out in
# `Misc/ghostsp.nsc`. This enables that mission block, idempotently, so the
# level appears in the mission-select menu. Pair it with the guest all-missions
# command-line switch (scripts/18-launch-user.sh passes it by default) so every
# mission is selectable.
#
# It is inserted *after* `1_3_REFINERYB` (Sabotage) rather than in the authored
# slot above it: `1_3_REFINERYB` must stay the first mission the chronicle
# offers so the
# canonical `--user-state --only a-mash` path (and every test built on it) is
# unaffected.
#
# Other mission IDs in the chronicle (Strike Team, the Protoss arc, ...) have
# no level package on the disc, so they cannot be enabled -- only Borgo ships
# its `.nil/.npd/.nsd`.
#
# Usage: bash scripts/21-enable-hidden-missions.sh
set -euo pipefail
source "$PWD/scripts/config.sh" || exit 1

NSC="$GAME_DATA_DIR/Misc/ghostsp.nsc"
if [ ! -f "$NSC" ]; then
    echo "ERROR: no single-player chronicle at: $NSC" >&2
    exit 1
fi

if grep -qE '^MISSION[[:space:]]+1_3_REFINERY[[:space:]]' "$NSC"; then
    echo "The Borgo Refinery is already enabled in $NSC"
    exit 0
fi

# Move the commented `//MISSION 1_3_REFINERY ... //ENDMISSION` block to an
# enabled copy right after the `1_3_REFINERYB` mission's ENDMISSION. The
# trailing [[:space:]] keeps `1_3_REFINERYB` from matching as the marker.
awk '
    $0 ~ /^\/\/MISSION[[:space:]]+1_3_REFINERY[[:space:]]/ { cblk = 1 }
    cblk {
        blk = blk substr($0, 3) "\n"
        if ($0 ~ /^\/\/ENDMISSION/) { cblk = 0; haveblk = 1 }
        next
    }
    $0 ~ /^MISSION[[:space:]]+1_3_REFINERYB/ { refb = 1 }
    {
        print
        if (refb && !inserted && $0 ~ /^ENDMISSION/) {
            printf "\n%s\n", blk
            inserted = 1
        }
    }
    END {
        if (!inserted)
            exit 9
    }
' "$NSC" > "$NSC.enabling" || {
    rm -f "$NSC.enabling"
    echo "ERROR: could not find a commented '//MISSION 1_3_REFINERY' block in $NSC" >&2
    exit 1
}

if grep -qE '^MISSION[[:space:]]+1_3_REFINERY[[:space:]]' "$NSC.enabling"; then
    mv "$NSC.enabling" "$NSC"
    echo "Enabled The Borgo Refinery (1_3_REFINERY) in $NSC"
else
    rm -f "$NSC.enabling"
    echo "ERROR: insertion produced no enabled 'MISSION 1_3_REFINERY' in $NSC" >&2
    exit 1
fi