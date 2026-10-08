#!/bin/bash
# Ask Claude Opus 5.5 for a technical / implementation opinion through the
# `oc` prompt wrapper (opencode in `run` mode).
#
# By default this DETACHES: it starts the query in its own session, streams all
# output to a log file, prints the log path + pid, and returns immediately so
# the caller can peek at the file and stop the run if needed.
#
# Usage:
#   bash scripts/ask-claude.sh "your technical question"
#   printf 'context...\n' | bash scripts/ask-claude.sh "your question"
#   bash scripts/ask-claude.sh --wait "question"   # run in the foreground
#   bash scripts/ask-claude.sh --chat "follow-up"  # continue the last chat
#   bash scripts/ask-claude.sh --session ses_XXX "..."  # continue that session id
#   bash scripts/ask-claude.sh --last-id           # newest session id (for --session)
#   bash scripts/ask-claude.sh --peek [LOG]        # tail the newest/given log
#   bash scripts/ask-claude.sh --stop [LOG]        # stop the newest/given run
#   bash scripts/ask-claude.sh --status            # list recent runs
#
# Env:
#   ASK_CLAUDE_MODEL    model id (default Claude Opus 5.5)
#   ASK_CLAUDE_RUN_DIR  where logs/pidfiles live (default /tmp/opencode)
#   ASK_CLAUDE_LOG      explicit log path for this run
set -euo pipefail

MODEL="${ASK_CLAUDE_MODEL:-workspace-gw-anthropic-coding-plan-passthrough/claude-opus-5-5}"
RUN_DIR="${ASK_CLAUDE_RUN_DIR:-/tmp/opencode}"
mkdir -p "$RUN_DIR"
LATEST="$RUN_DIR/ask-claude.latest"
# Use a dedicated opencode DB so `oc -c` (continue last) resumes the previous
# *consultation*, never the calling agent's own session. `oc` honours a pre-set
# OPENCODE_DB (opencode-wrapper.sh oc_wrapper_shard_db returns early).
export OPENCODE_DB="${ASK_CLAUDE_DB:-ask-claude.db}"

newest_log() {
    local log=""
    if [[ -r "$LATEST" ]]; then
        read -r log < "$LATEST"
    fi
    printf '%s' "$log"
}

last_session_id() {
    local tmp id line
    tmp="$RUN_DIR/ask-claude-sessions.$$"
    oc -- session list -n 1 > "$tmp"
    id=""
    while IFS= read -r line; do
        case "$line" in
            ses_*)
                id="${line%%[[:space:]]*}"
                break
                ;;
        esac
    done < "$tmp"
    rm -f "$tmp"
    printf '%s' "$id"
}

case "${1:-}" in
    --peek)
        log="${2:-$(newest_log)}"
        if [[ -z "$log" || ! -f "$log" ]]; then
            echo "no log (${log:-<none>})" >&2
            exit 2
        fi
        tail -n 80 "$log"
        exit 0
        ;;
    --stop)
        log="${2:-$(newest_log)}"
        pf="${log}.pid"
        if [[ -z "$log" || ! -f "$pf" ]]; then
            echo "no pidfile for ${log:-<none>}" >&2
            exit 2
        fi
        pid="$(cat "$pf")"
        if [[ -d "/proc/$pid" ]]; then
            kill -TERM "$pid"
            echo "stopped pid=$pid log=$log"
        else
            echo "pid $pid already gone"
        fi
        exit 0
        ;;
    --status)
        for pf in "$RUN_DIR"/ask-claude-*.log.pid; do
            [[ -f "$pf" ]] || continue
            pid="$(cat "$pf")"
            log="${pf%.pid}"
            if [[ -d "/proc/$pid" ]]; then
                printf 'RUNNING pid=%s log=%s\n' "$pid" "$log"
            else
                printf 'DONE    pid=%s log=%s\n' "$pid" "$log"
            fi
        done
        exit 0
        ;;
    --last-id)
        last_session_id
        printf '\n'
        exit 0
        ;;
esac

WAIT=0
CHAT_ARG=""
while true; do
    case "${1:-}" in
        --wait)    WAIT=1; shift ;;
        --detach)  WAIT=0; shift ;;
        --chat)
            CHAT_ARG="-c"
            shift
            ;;
        --session|--resume)
            if [[ -z "${2:-}" ]]; then
                echo "usage: $0 --session <session-id> \"question\"" >&2
                exit 2
            fi
            CHAT_ARG="-s $2"
            shift 2
            ;;
        --session=*)
            CHAT_ARG="-s ${1#--session=}"
            shift
            ;;
        *) break ;;
    esac
done

if [[ $# -gt 0 ]]; then
    PROMPT="$*"
else
    PROMPT="$(cat)"
fi
if [[ -z "${PROMPT//[[:space:]]/}" ]]; then
    echo "usage: $0 [--chat | --session <id>] [--wait] \"question\"" >&2
    exit 2
fi

if DIR="$(git rev-parse --show-toplevel)"; then :; else DIR="$PWD"; fi

STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="${ASK_CLAUDE_LOG:-$RUN_DIR/ask-claude-$STAMP.log}"
PIDFILE="$LOG.pid"
PROMPT_FILE="$LOG.prompt"
printf '%s' "$PROMPT" > "$PROMPT_FILE"
printf '%s\n' "$LOG" > "$LATEST"

if [[ "$WAIT" == 1 ]]; then
    cd "$DIR"
    exec oc -- run -m "$MODEL" --dir "$DIR" $CHAT_ARG "$PROMPT" >>"$LOG" 2>&1
fi

export MODEL DIR PROMPT_FILE CHAT_ARG
nohup setsid bash -c 'exec oc -- run -m "$MODEL" --dir "$DIR" $CHAT_ARG "$(cat "$PROMPT_FILE")"' \
    >>"$LOG" 2>&1 &
child=$!
echo "$child" > "$PIDFILE"
printf 'started pid=%s\nlog: %s\n' "$child" "$LOG"
printf '  peek: bash scripts/ask-claude.sh --peek %s\n' "$LOG"
printf '  stop: bash scripts/ask-claude.sh --stop %s\n' "$LOG"
printf '  id:   bash scripts/ask-claude.sh --last-id\n'