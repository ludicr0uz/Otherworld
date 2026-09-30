"""What a task cost: tokens, dollars, time -- and the commit trailers that
record them, so ``git log`` shows what each change cost."""

import subprocess


def git(root, *argv):
    return subprocess.run(["git", *argv], cwd=root, capture_output=True, text=True)


def git_head(root):
    try:
        return git(root, "rev-parse", "--short", "HEAD").stdout.strip()
    except OSError:
        return ""


def token_usage(result):
    """Sum the session's tokens over every model it used (subagents included)."""
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    per_model = result.get("modelUsage") or {}
    if per_model:
        for m in per_model.values():
            usage["input"] += m.get("inputTokens") or 0
            usage["output"] += m.get("outputTokens") or 0
            usage["cache_read"] += m.get("cacheReadInputTokens") or 0
            usage["cache_write"] += m.get("cacheCreationInputTokens") or 0
    else:
        u = result.get("usage") or {}
        usage["input"] = u.get("input_tokens") or 0
        usage["output"] = u.get("output_tokens") or 0
        usage["cache_read"] = u.get("cache_read_input_tokens") or 0
        usage["cache_write"] = u.get("cache_creation_input_tokens") or 0
    usage["total"] = sum(usage.values())
    return usage


def merge_results(first, second):
    """One result for a session and its follow-up (a gate fix): costs, times
    and per-model usage add up; everything else is the follow-up's."""
    if not first:
        return second
    merged = dict(second)
    for key in ("total_cost_usd", "duration_ms", "duration_api_ms", "num_turns"):
        merged[key] = (first.get(key) or 0) + (second.get(key) or 0)
    models = {}
    for part in (first, second):
        for name, m in (part.get("modelUsage") or {}).items():
            into = models.setdefault(name, {})
            for k, v in m.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    into[k] = (into.get(k) or 0) + v
    if models:
        merged["modelUsage"] = models
    return merged


def describe_tokens(usage, cost):
    return (f"{usage['total']:,} (input {usage['input']:,}, output {usage['output']:,}, "
            f"cache read {usage['cache_read']:,}, cache write {usage['cache_write']:,}; "
            f"${cost:.2f})")


def describe_time(ms):
    mins, secs = divmod(round((ms or 0) / 1000), 60)
    hours, mins = divmod(mins, 60)
    return f"{hours}h {mins:02d}m {secs:02d}s" if hours else f"{mins}m {secs:02d}s"


def tag_commit(root, before, after, time, tokens):
    """Add Time:/Tokens: trailers to the task's last commit. Returns the new short HEAD."""
    if git(root, "branch", "-r", "--contains", "HEAD").stdout.strip():
        print("    (not recording time/tokens: the commit is already pushed)")
        return after
    count = git(root, "rev-list", "--count", f"{before}..HEAD").stdout.strip()
    scope = f" -- for all {count} commits of this task" if count and count != "1" else ""
    # --only with no paths rewrites the message alone and leaves the index out;
    # the content was already verified by the hook when the session committed.
    done = git(root, "commit", "--amend", "--only", "--no-verify", "--no-edit",
               "--trailer", f"Time: {time}{scope}",
               "--trailer", f"Tokens: {tokens}{scope}")
    if done.returncode:
        print(f"    (could not record time/tokens in the commit: {done.stderr.strip()})")
        return after
    return git_head(root)
