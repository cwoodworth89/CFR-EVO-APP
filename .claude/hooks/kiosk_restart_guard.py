#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block commands that can restart, stop or kill a kiosk service.

Why
---
On 2026-09-05 an agent restarted cfr-agent 50 seconds into a structure-fire broadcast and the call
was lost (punch list #70). The rule that the operator chooses the restart moment lived only in
`.claude/skills/kiosk-remote-ops/SKILL.md` and in memory, while `.claude/settings.json` allowlists
`Bash(ssh -o BatchMode=yes *)`, which admits a restart with no prompt.

Operator ruling 2026-09-14: block, and the operator runs restarts. permissionDecision "ask" was
tried first; in an auto-mode desktop session two harmless checks that it flagged ran without being
stopped, with and without a matching allow rule. Why was not established.

What it does
------------
Reads the command the way a shell would -- quotes, `$(...)`, heredocs, `ssh host "remote command"`,
`bash -c`, `docker exec` -- and answers permissionDecision "deny" when any simple command in it is:

  systemctl restart|stop|kill|reload|isolate|mask|disable|reboot|poweroff|...   (any unit, any flags)
  service <unit> restart|stop|reload|force-reload
  docker restart|stop|kill|rm|pause, also as `docker container <verb>`
  docker compose / docker-compose restart|stop|kill|rm|pause|down|up
      `up` recreates changed containers and is how the API is redeployed; the operator's
      2026-09-05 ruling covers "the API container rebuild if a call could be live".
  kill, pkill, killall;  reboot, poweroff, halt, shutdown;  init 0|6, telinit 0|6
  setup_kiosk.sh run as a program (it restarts cfr-agent and nginx)
  build_vector_basemap.sh --restart-tiles (it restarts cfr_tiles)

Anything else produces no output, so the normal permission rules apply. A denial tells Claude to
hand the operator the exact command instead; the operator runs it when the moment is right.

A shell script written by heredoc in the same command (`cat > /tmp/x.sh <<'SH' ... SH`, then scp
and ssh) is checked too: that is how the 2026-08/09 tile and OSRM swaps were run.

What it cannot see
------------------
Restarts inside a script file written any other way (the Write tool, a Python edit), commands
assembled at run time (eval, variables), and tools other than Bash and PowerShell. It does not know whether a call is live; that is what
`tools/kiosk_capture_state.sh` is for.

Every denial is appended to ~/.claude/kiosk-restart-guard.log. If the guard itself fails, it denies
only commands containing a trigger word, so a harness change cannot block every Bash call.
`--self-test` runs the cases at the end of this file.
"""
import datetime
import json
import os
import re
import sys

REASON = ("Blocked by the kiosk restart guard (.claude/hooks/kiosk_restart_guard.py): `{hit}` can restart, "
          "stop or kill a service on the kiosk, and a restart during a broadcast loses the call (punch list #70). "
          "Operator ruling 2026-09-14: the operator runs these, Claude does not. Do not retry, reword or script "
          "around it. If the command also did other work, run that part on its own. Then give the operator the "
          "exact command to run, noting that tools/kiosk_capture_state.sh must say SAFE first.")
LOG = os.path.join(os.path.expanduser("~"), ".claude", "kiosk-restart-guard.log")

# Cheap pre-check: text containing none of these words cannot match any rule below.
TRIGGER = re.compile(r"systemctl|service|docker|podman|kill|reboot|poweroff|halt|shutdown|init|"
                     r"setup_kiosk|build_vector_basemap", re.I)

SYSTEMCTL_VERBS = {
    "restart", "stop", "kill", "reload", "try-restart", "reload-or-restart", "try-reload-or-restart",
    "condrestart", "force-reload", "isolate", "mask", "disable", "reboot", "soft-reboot", "poweroff",
    "halt", "kexec", "suspend", "hibernate", "hybrid-sleep", "suspend-then-hibernate", "emergency",
    "rescue", "exit", "switch-root",
}
SERVICE_VERBS = {"restart", "stop", "reload", "force-reload", "try-restart", "condrestart"}
DOCKER_VERBS = {"restart", "stop", "kill", "rm", "pause"}
COMPOSE_VERBS = DOCKER_VERBS | {"down", "up"}
KILL_COMMANDS = {"kill", "pkill", "killall"}
POWER_COMMANDS = {"reboot", "poweroff", "halt", "shutdown"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}

# Options that consume the next word. Any other word starting with "-" is a flag on its own.
WRAPPER_VALUE_OPTIONS = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-U", "-T",
             "--user", "--group", "--host", "--prompt", "--chdir"},
    "doas": {"-u", "-C"},
    "env": {"-u", "--unset", "-C", "--chdir"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "--class", "--classdata"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "xargs": {"-n", "-I", "-P", "-L", "-d", "-a", "-E", "-s", "--max-args", "--replace",
              "--max-procs", "--max-lines", "--delimiter", "--arg-file", "--eof", "--max-chars"},
    "exec": {"-a"},
    "nohup": set(), "setsid": set(), "stdbuf": set(), "command": set(), "builtin": set(), "time": set(),
    # shell keywords that come before a command: `for c in ...; do docker kill $c; done`
    "do": set(), "then": set(), "else": set(), "elif": set(), "if": set(), "while": set(), "until": set(), "!": set(),
}
SSH_VALUE_LETTERS = set("BbcDEeFIiJLlmOoPpQRSWw")
DOCKER_GLOBAL_VALUE = {"-H", "--host", "-c", "--context", "--config", "-l", "--log-level",
                       "--tlscacert", "--tlscert", "--tlskey"}
COMPOSE_VALUE = {"-f", "--file", "-p", "--project-name", "--profile", "--env-file",
                 "--project-directory", "--ansi", "--progress", "--parallel"}
EXEC_VALUE = {"-e", "--env", "--env-file", "-u", "--user", "-w", "--workdir", "--detach-keys", "--index"}
SYSTEMCTL_VALUE = {"-H", "--host", "-M", "--machine", "-t", "--type", "-p", "--property", "-P",
                   "-s", "--signal", "--kill-whom", "--kill-value", "-n", "--lines", "-o", "--output",
                   "--root", "--image", "--job-mode", "--what", "--timestamp", "--state", "--when"}

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC = re.compile(r"<<(-?)[ \t]*\\?(['\"]?)([A-Za-z_][\w.-]*)\2")


# ---------------------------------------------------------------- lexing

def _close_paren(text, i):
    """text[i] is '('. Return the index of its matching ')', or len(text) if unclosed."""
    depth, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "'":
            j = text.find("'", i + 1)
            i = n if j < 0 else j + 1
            continue
        if ch == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n


def _read_heredoc(text, i, delim, strip_tabs):
    """Read heredoc lines from index i to the delimiter line. Return (body, index after it)."""
    lines, n = [], len(text)
    while i < n:
        j = text.find("\n", i)
        j = n if j < 0 else j
        line = text[i:j]
        if (line.lstrip("\t") if strip_tabs else line).rstrip("\r ") == delim:
            return "\n".join(lines), min(j + 1, n)
        lines.append(line)
        i = j + 1
    return "\n".join(lines), n


def split_commands(text):
    """Lex shell text into simple commands.

    Returns (commands, substitutions). Each command is {"words": [...], "heredocs": [...]} with
    quotes removed; each substitution is the text inside $(...) or backticks, scanned separately.
    Never raises: an unclosed quote or substitution runs to the end of the text.
    """
    commands, subs, pending = [], [], []
    # "skip" marks the next word as a redirection target (`> file`, `2>&1`): kept apart from arguments
    state = {"cur": {"words": [], "heredocs": [], "redirects": []}, "word": [], "in_word": False, "skip": False}

    def end_word():
        if state["in_word"]:
            target = "redirects" if state["skip"] else "words"
            state["cur"][target].append("".join(state["word"]))
            state["skip"] = False
        state["word"], state["in_word"] = [], False

    def end_command():
        end_word()
        state["skip"] = False
        if state["cur"]["words"] or state["cur"]["heredocs"]:
            commands.append(state["cur"])
        state["cur"] = {"words": [], "heredocs": [], "redirects": []}

    def add(chunk):
        state["word"].append(chunk)
        state["in_word"] = True

    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            if text.startswith("\\\n", i):
                i += 2
            elif text.startswith("\\\r\n", i):
                i += 3
            else:
                if i + 1 < n:
                    add(text[i + 1])
                i += 2
            continue
        if c == "'":
            j = text.find("'", i + 1)
            j = n if j < 0 else j
            add(text[i + 1:j])
            i = j + 1
            continue
        if c == '"':
            i += 1
            chunk = []
            while i < n and text[i] != '"':
                ch = text[i]
                if ch == "\\" and i + 1 < n and text[i + 1] in '"\\$`\n':
                    if text[i + 1] != "\n":
                        chunk.append(text[i + 1])
                    i += 2
                    continue
                if text.startswith("$(", i):
                    j = _close_paren(text, i + 1)
                    subs.append(text[i + 2:j])
                    chunk.append("$")
                    i = j + 1
                    continue
                if ch == "`":
                    j = text.find("`", i + 1)
                    j = n if j < 0 else j
                    subs.append(text[i + 1:j])
                    chunk.append("$")
                    i = j + 1
                    continue
                chunk.append(ch)
                i += 1
            add("".join(chunk))
            i += 1
            continue
        if text.startswith("$(", i):
            j = _close_paren(text, i + 1)
            subs.append(text[i + 2:j])
            add("$")
            i = j + 1
            continue
        if text.startswith("${", i):
            j = text.find("}", i + 2)
            j = n if j < 0 else j
            add(text[i:j + 1])
            i = j + 1
            continue
        if c == "`":
            j = text.find("`", i + 1)
            j = n if j < 0 else j
            subs.append(text[i + 1:j])
            add("$")
            i = j + 1
            continue
        if c == "#" and not state["in_word"]:
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("<<", i) and not text.startswith("<<<", i):
            m = HEREDOC.match(text, i)
            if m:
                end_word()
                pending.append((m.group(3), m.group(1) == "-", state["cur"]))
                i = m.end()
                continue
        if c == "\n":
            end_command()
            i += 1
            while pending:
                delim, strip_tabs, owner = pending.pop(0)
                body, i = _read_heredoc(text, i, delim, strip_tabs)
                owner["heredocs"].append(body)
            continue
        if c in " \t\r":
            end_word()
            i += 1
            continue
        if c in ";|(){}" or (c == "&" and text[i - 1:i] not in ("<", ">") and text[i + 1:i + 2] != ">"):
            end_command()
            i += 1
            continue
        if c in "<>":
            pending_word = "".join(state["word"])
            if state["in_word"] and (pending_word.isdigit() or pending_word == "&"):
                state["word"], state["in_word"] = [], False  # a file descriptor: `2>`, `&>`
            else:
                end_word()
            state["skip"] = True
            i += 1
            continue
        add(c)
        i += 1
    end_command()
    return commands, subs


# ---------------------------------------------------------------- matching

def command_name(word):
    base = re.split(r"[\\/]", word)[-1].lower()
    return base[:-4] if base.endswith(".exe") else base


def skip_options(words, i, value_options):
    """Index of the first word at or after i that is neither an option nor an option's value."""
    while i < len(words):
        w = words[i]
        if w == "--":
            return i + 1
        if not w.startswith("-") or w == "-":
            return i
        i += 2 if w in value_options else 1
    return i


def strip_wrappers(words):
    """Drop leading VAR=value assignments and wrappers such as sudo, env, nohup, xargs, timeout."""
    i = 0
    while i < len(words):
        if ASSIGNMENT.match(words[i]):
            i += 1
            continue
        name = command_name(words[i])
        if name not in WRAPPER_VALUE_OPTIONS:
            break
        i = skip_options(words, i + 1, WRAPPER_VALUE_OPTIONS[name])
        if name == "timeout" and i < len(words):
            i += 1  # the duration
    return words[i:]


def _ssh_destination(args):
    """Index of the destination word in ssh's arguments, or None."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            return i + 1 if i + 1 < len(args) else None
        if a.startswith("-") and len(a) > 1:
            letters = a[1:]
            for k, ch in enumerate(letters):
                if ch in SSH_VALUE_LETTERS:
                    if k == len(letters) - 1:
                        i += 1  # the option's value is the next word
                    break
            i += 1
            continue
        return i
    return None


def _script_hit(word, args):
    script = command_name(word)
    if script == "setup_kiosk.sh":
        return "setup_kiosk.sh"
    if script == "build_vector_basemap.sh" and "--restart-tiles" in args:
        return "build_vector_basemap.sh --restart-tiles"
    return None


def _exec_hit(rest, depth):
    """`docker exec [options] CONTAINER COMMAND...`: check the command run inside the container."""
    k = skip_options(rest, 0, EXEC_VALUE)
    inner = rest[k + 1:]
    hit = _check(inner, [], depth + 1) if inner else None
    return "docker exec: " + hit if hit else None


def _check(words, heredocs, depth, redirects=()):
    words = strip_wrappers(words)
    if not words:
        return None
    name, args = command_name(words[0]), words[1:]

    if name in ("cat", "tee") and heredocs and any(t.endswith(".sh") for t in list(redirects) + args):
        # `cat > /tmp/swap.sh <<'SH' ... SH` then scp + ssh: how tile and OSRM swaps were run in
        # 2026-08/09. The script body is checked here because once it is a file it cannot be seen.
        for body in heredocs:
            hit = analyse(body, depth + 1)
            if hit:
                return "shell script written by heredoc: " + hit
        return None

    if name == "ssh":
        dest = _ssh_destination(args)
        remote = args[dest + 1:] if dest is not None else []
        # ssh joins its arguments with spaces and the kiosk shell re-parses them, so the joined text
        # is what runs. A quoted multi-word argument is also checked alone: `ssh host bash -c "x y"`
        # loses those quotes on the way, but a question costs less than a missed restart.
        for script in [" ".join(remote)] + [w for w in remote if " " in w] + heredocs:
            hit = analyse(script, depth + 1)
            if hit:
                return "ssh: " + hit
        return None

    if name in SHELLS or name == "su":
        for k, a in enumerate(args):
            if a in ("-c", "--command") or (name in SHELLS and re.fullmatch(r"-[a-z]*c[a-z]*", a)):
                return analyse(args[k + 1], depth + 1) if k + 1 < len(args) else None
        for body in heredocs:
            hit = analyse(body, depth + 1)
            if hit:
                return hit
        if any(a == "-n" or re.fullmatch(r"-[a-z]*n[a-z]*", a) for a in args[:skip_options(args, 0, set())]):
            return None  # `bash -n script` only checks the script's syntax
        k = skip_options(args, 0, set())
        return _script_hit(args[k], args[k + 1:]) if name in SHELLS and k < len(args) else None

    if name in ("source", "."):
        return _script_hit(args[0], args[1:]) if args else None

    hit = _script_hit(words[0], args)
    if hit:
        return hit

    if name == "systemctl":
        k = skip_options(args, 0, SYSTEMCTL_VALUE)
        if k < len(args) and args[k].lower() in SYSTEMCTL_VERBS:
            return "systemctl " + args[k].lower()
        return None

    if name == "service":
        if len(args) >= 2 and args[1].lower() in SERVICE_VERBS:
            return "service %s %s" % (args[0], args[1].lower())
        return None

    if name in ("docker", "podman", "docker-compose"):
        if name == "docker-compose":
            sub, rest = "compose", args
        else:
            k = skip_options(args, 0, DOCKER_GLOBAL_VALUE)
            if k >= len(args):
                return None
            sub, rest = args[k].lower(), args[k + 1:]
        if sub == "compose":
            k = skip_options(rest, 0, COMPOSE_VALUE)
            if k >= len(rest):
                return None
            verb = rest[k].lower()
            if verb in COMPOSE_VERBS:
                return "docker compose " + verb
            return _exec_hit(rest[k + 1:], depth) if verb == "exec" else None
        if sub == "container":
            verb = rest[0].lower() if rest else ""
            if verb in DOCKER_VERBS:
                return "docker container " + verb
            return _exec_hit(rest[1:], depth) if verb == "exec" else None
        if sub in DOCKER_VERBS:
            return "docker " + sub
        return _exec_hit(rest, depth) if sub == "exec" else None

    if name in KILL_COMMANDS:
        if name == "kill" and args and all(a in ("-l", "-L", "--list", "--table") for a in args):
            return None  # a signal listing; a bare `kill` may take its PIDs from xargs
        targets = [a for a in args if not a.startswith("-")]
        if name == "kill" and targets and all(t.startswith("%") for t in targets):
            return None  # `kill %1` stops a background job of the same shell, not a service
        return name

    if name in POWER_COMMANDS:
        return None if name == "shutdown" and "-c" in args else name

    if name in ("init", "telinit") and args and args[0] in ("0", "6"):
        return "%s %s" % (name, args[0])
    return None


def analyse(text, depth=0):
    """Short description of the first restart-class command in shell text, or None."""
    if depth > 8 or not text or not TRIGGER.search(text):
        return None
    commands, subs = split_commands(text)
    for sub in subs:
        hit = analyse(sub, depth + 1)
        if hit:
            return hit
    for command in commands:
        hit = _check(command["words"], command["heredocs"], depth, command["redirects"])
        if hit:
            return hit
    return None


# ---------------------------------------------------------------- hook entry point

def decide(payload):
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input.get("command"), str):
        texts = [tool_input["command"]]
    else:
        texts = [v for v in tool_input.values() if isinstance(v, str)]
    for text in texts:
        hit = analyse(text)
        if hit:
            return hit, text
    return None, None


def _log(payload, hit, text):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                "decision": "deny",
                "session": payload.get("session_id"),
                "tool": payload.get("tool_name"),
                "hit": hit,
                "command": (text or "")[:1000],
            }) + "\n")
    except OSError:
        pass


def _deny(reason):
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": "deny",
                                      "permissionDecisionReason": reason}}, sys.stdout)


def main():
    if "--self-test" in sys.argv[1:]:
        return _self_test()
    raw, payload = "", {}
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        payload = json.loads(raw or "{}")
        hit, text = decide(payload)
    except Exception as exc:
        # Fail closed only where a restart is possible, so a broken guard cannot block all Bash.
        if TRIGGER.search(raw):
            _deny("Kiosk restart guard could not check this command (%s: %s). Tell the operator; do not "
                  "work around it." % (type(exc).__name__, exc))
        return 0
    if hit:
        _log(payload, hit, text)
        _deny(REASON.format(hit=hit))
    return 0


# ---------------------------------------------------------------- self-test

CASES = [
    # (should ask, command) -- the first two are the restarts in kiosk-remote-ops/SKILL.md:59 and :77
    (True, r'ssh tcfire@100.95.146.94 "sudo systemctl restart cfr-agent"'),
    (True, r'ssh tcfire@100.95.146.94 "kill -TERM \$(systemctl show cfr-agent -p MainPID --value); sleep 15; systemctl is-active cfr-agent"'),
    (True, 'ssh -o BatchMode=yes tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && docker compose up -d --build api"'),
    (True, "ssh -o BatchMode=yes -o ConnectTimeout=15 kiosk 'docker restart cfr_tiles'"),
    (True, "docker compose -f docker-compose.yml restart tiles"),
    (True, "ssh kiosk 'bash -s' <<'EOF'\ncd /home/tcfire\nsudo systemctl stop cfr-agent\nEOF"),
    (True, 'ssh kiosk "pkill -f audio_listener"'),
    (True, 'ssh -tt kiosk "sudo -n reboot"'),
    (True, 'ssh kiosk "bash /home/tcfire/CFR-EVO-APP/setup_kiosk.sh"'),
    (True, "bash backend/scripts/build_vector_basemap.sh --restart-tiles"),
    (True, 'ssh kiosk "docker exec cfr_api kill 1"'),
    (True, "sudo -u tcfire XDG_RUNTIME_DIR=/run/user/1000 systemctl --user restart pipewire"),
    (True, 'ssh kiosk "pgrep -f cfr_dispatch | xargs kill"'),
    (True, "ssh -p 22 -i ~/.ssh/id_ed25519 kiosk docker-compose down"),
    (True, 'ssh kiosk bash -lc "docker --context default stop cfr_osrm"'),
    # 2026-09-05 11:42, the restart that lost the structure-fire capture (punch list #70), as sent
    (True, "ssh -o ConnectTimeout=15 tcfire@100.95.146.94 'cd /home/tcfire/CFR-EVO-APP && git pull -q && "
           "git log --oneline -1 && OLD=$(systemctl show cfr-agent -p MainPID --value); kill -TERM \"$OLD\"; sleep 15'"),
    (False, 'ssh tcfire@100.95.146.94 "tail -n 50 /home/tcfire/CFR-EVO-APP/backend/dispatch.log"'),
    (False, 'ssh tcfire@100.95.146.94 "bash /home/tcfire/CFR-EVO-APP/tools/kiosk_capture_state.sh"'),
    (False, 'ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull && cd frontend && npm run build"'),
    (False, 'git commit -m "docs: sudo systemctl restart cfr-agent, then docker compose down"'),
    (False, 'grep -rn "shutdown" backend/cfr_dispatch/'),
    (False, 'ssh kiosk "systemctl status cfr-agent; journalctl -u cfr-agent -n 50; systemctl daemon-reload"'),
    (False, 'ssh kiosk "docker compose logs --tail 100 api && docker compose build api"'),
    (False, "ssh kiosk \"docker exec cfr_postgres psql -U cfr_user -c 'SELECT 1'\""),
    (False, "python - <<'EOF'\n# don't kill anything here\nprint('reboot', 'docker restart')\nEOF"),
    (False, "cat setup_kiosk.sh | grep restart"),
    (False, 'echo "kill -9 1234" && kill -l'),
    (False, "docker ps --format '{{.Names}}' 2>&1 | head"),
    (False, "echo \"it's unbalanced"),
    (False, 'echo "##### bash -n setup_kiosk.sh" && bash -n setup_kiosk.sh && echo "syntax ok"'),
    (False, 'ssh kiosk \'docker exec -d cfr_mosquitto sh -c "mosquitto_sub -t cfr/dispatches > /tmp/cap.txt 2>&1 & sleep 12; kill %1 2>/dev/null"\''),
    (True, 'ssh kiosk "sudo systemctl restart cfr-agent >/dev/null 2>&1 && systemctl is-active cfr-agent"'),
    (True, r'ssh kiosk " for c in \$(docker ps -q --filter ancestor=klokantech/gdal); do docker kill \$c >/dev/null 2>&1; done"'),
    (True, 'ssh kiosk "if ! systemctl is-active -q cfr-agent; then sudo systemctl restart cfr-agent; fi"'),
    (True, "cat > /tmp/swap_ortho.sh <<'SH'\n#!/bin/bash\nset -e\ndocker stop cfr_tiles >/dev/null && echo stopped\nSH\n"
           "scp /tmp/swap_ortho.sh kiosk:/tmp/ && ssh kiosk 'nohup bash /tmp/swap_ortho.sh >/tmp/swap.log 2>&1 &'"),
    (False, "cat > /tmp/notes.md <<'EOF'\nthe runbook says docker stop cfr_tiles first\nEOF"),
]


def _self_test():
    failed = 0
    for expect, command in CASES:
        hit = analyse(command)
        ok = bool(hit) == expect
        failed += not ok
        print("%s %-4s %-40.40s %r" % ("ok  " if ok else "FAIL", "deny" if hit else "pass", hit or "", command[:80]))
    print("%d/%d cases as expected" % (len(CASES) - failed, len(CASES)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
