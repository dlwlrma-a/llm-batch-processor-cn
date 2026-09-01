#!/usr/bin/env python3
"""Bounded CSV/JSONL processor for OpenAI-compatible chat completions."""
import argparse
import csv
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

MAX_ROWS = 1000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def load_rows(path):
    path = Path(path)
    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8-sig") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    raise ValueError("input must be .csv or .jsonl")


def save_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".jsonl":
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return
    if path.suffix.lower() != ".csv":
        raise ValueError("output must be .csv or .jsonl")
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render(template, row):
    fields = set(re.findall(r"(?<!{){([A-Za-z_][A-Za-z0-9_]*)}(?!})", template))
    missing = sorted(fields - set(row))
    if missing:
        raise ValueError("missing template fields: " + ", ".join(missing))
    return template.format_map({key: "" if value is None else value for key, value in row.items()})


def chat(base_url, api_key, model, prompt, timeout=60, retries=2):
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0}).encode()
    opener = urllib.request.build_opener(NoRedirect())
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=body, method="POST", headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"})
        try:
            with opener.open(request, timeout=timeout) as response:
                payload = json.load(response)
            return payload["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
            time.sleep(2 ** attempt)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--output-field", default="ai_result")
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    parser.add_argument("--model")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument("--rpm", type=int, default=30)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-live-run", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not 1 <= args.max_rows <= MAX_ROWS:
        raise SystemExit("--max-rows must be between 1 and 1000")
    if not 1 <= args.rpm <= 600:
        raise SystemExit("--rpm must be between 1 and 600")
    rows = load_rows(args.input)
    if not rows:
        raise SystemExit("input contains no rows")
    preview = [render(args.template, row) for row in rows[:min(3, args.max_rows)]]
    if args.dry_run:
        print(json.dumps({"rows": len(rows), "will_process": min(len(rows), args.max_rows), "preview": preview}, ensure_ascii=False, indent=2))
        return 0
    if not args.confirm_live_run:
        raise SystemExit("live calls require --confirm-live-run")
    if not args.model:
        raise SystemExit("--model is required for live calls")
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit("missing API key environment variable: " + args.api_key_env)
    selected = rows[:args.max_rows]
    output_path = Path(args.output)
    previous = load_rows(output_path) if args.resume and output_path.exists() else []
    done = {str(row.get("_batch_row")) for row in previous if row.get("ai_status") == "ok"}
    results = list(previous)
    delay = 60.0 / args.rpm
    for index, row in enumerate(selected, 1):
        if str(index) in done:
            continue
        result = dict(row)
        result["_batch_row"] = index
        try:
            result[args.output_field] = chat(args.base_url, api_key, args.model, render(args.template, row))
            result["ai_status"] = "ok"
            result["ai_error"] = ""
        except Exception as exc:
            result[args.output_field] = ""
            result["ai_status"] = "error"
            result["ai_error"] = f"{type(exc).__name__}: {exc}"[:500]
        results.append(result)
        save_rows(output_path, results)
        if index < len(selected):
            time.sleep(delay)
    ok = sum(row.get("ai_status") == "ok" for row in results)
    errors = sum(row.get("ai_status") == "error" for row in results)
    print(json.dumps({"success": ok, "errors": errors, "output": str(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
