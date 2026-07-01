"""
Local evaluation harness for the SHL Assessment Recommender.

Reads traces/traces.json, replays each conversation against your running
/chat endpoint, and reports:
  - Per-trace Recall@10
  - Mean Recall@10 across all traces
  - Behavior probe pass/fail for each trace

Usage:
    # Make sure your server is running:
    #   uvicorn app.main:app --reload --port 8000
    python scripts/eval.py
    python scripts/eval.py --url https://your-render-url.onrender.com
"""
import json, sys, time, argparse
import requests

# ─── Config ────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:8000", help="Base URL of your server")
parser.add_argument("--traces", default="traces/traces.json", help="Path to traces.json")
args = parser.parse_args()

BASE_URL = args.url.rstrip("/")
TRACES_PATH = args.traces


# ─── Helpers ───────────────────────────────────────────────────────────────
def recall_at_10(recommended: list, expected: list) -> float:
    if not expected:
        return 1.0
    top10 = set(n.lower().strip() for n in recommended[:10])
    rel   = set(n.lower().strip() for n in expected)
    return len(top10 & rel) / len(rel)


def chat(messages: list) -> dict:
    r = requests.post(
        f"{BASE_URL}/chat",
        json={"messages": messages},
        timeout=35,
    )
    r.raise_for_status()
    return r.json()


def health_check():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


# ─── Main eval loop ─────────────────────────────────────────────────────────
def run_eval():
    # Health check
    print(f"Checking {BASE_URL}/health ...")
    if not health_check():
        print("ERROR: /health not reachable or returned wrong status. Start your server first.")
        sys.exit(1)
    print("Server is up ✓\n")

    traces = json.load(open(TRACES_PATH))
    results = []

    for t in traces:
        fname = t["file"]
        user_messages = t["user_messages"]
        expected = t["expected_shortlist"]

        print(f"{'─'*60}")
        print(f"Trace: {fname}  ({len(user_messages)} user turns, {len(expected)} expected items)")

        messages = []        # running conversation history
        final_recs = []      # last non-empty recommendations
        rec_turn = None      # which turn we first got recommendations
        turn_count = 0
        eoc_received = False

        # Behavior probes
        probe_no_premature_rec = True   # should not recommend on turn 1 for vague query
        probe_eoc_received = False      # should eventually set end_of_conversation=true

        for i, user_text in enumerate(user_messages):
            if eoc_received:
                break

            messages.append({"role": "user", "content": user_text})
            turn_count += 1

            try:
                resp = chat(messages)
            except Exception as e:
                print(f"  Turn {i+1}: ERROR - {e}")
                break

            agent_reply = resp.get("reply", "")
            recs = resp.get("recommendations", [])
            eoc  = resp.get("end_of_conversation", False)
            rec_names = [r["name"] for r in recs]

            print(f"  Turn {i+1}: {len(recs)} recs | eoc={eoc}")
            if rec_names:
                for n in rec_names:
                    print(f"    → {n}")

            # Probe: first turn with vague query should not recommend
            if i == 0 and recs:
                # Only flag if the first user message is genuinely vague
                # (no job title, no skills, just a general statement)
                words = user_text.lower().split()
                if len(words) < 6:
                    probe_no_premature_rec = False
                    print(f"  ⚠ PROBE FAIL: recommended on turn 1 for short/vague query")

            if recs:
                final_recs = rec_names
                if rec_turn is None:
                    rec_turn = i + 1

            messages.append({"role": "assistant", "content": agent_reply})

            if eoc:
                eoc_received = True
                probe_eoc_received = True

        if not eoc_received:
            print(f"  ⚠ PROBE FAIL: end_of_conversation never became true")
        else:
            probe_eoc_received = True

        score = recall_at_10(final_recs, expected)
        results.append({
            "file": fname,
            "score": score,
            "final_recs": final_recs,
            "expected": expected,
            "probe_no_premature_rec": probe_no_premature_rec,
            "probe_eoc": probe_eoc_received,
        })

        print(f"  Recall@10 = {score:.2f}  ({len(set(r.lower() for r in final_recs) & set(e.lower() for e in expected))}/{len(expected)} hits)")
        missed = [e for e in expected if e.lower() not in {r.lower() for r in final_recs}]
        if missed:
            print(f"  Missed: {missed}")
        print()
        time.sleep(0.5)  # be polite to the API

    # ─── Summary ────────────────────────────────────────────────────────────
    print(f"{'═'*60}")
    mean_recall = sum(r["score"] for r in results) / len(results)
    probe_pass  = sum(1 for r in results if r["probe_no_premature_rec"] and r["probe_eoc"])
    print(f"Mean Recall@10:  {mean_recall:.3f}  ({mean_recall*100:.1f}%)")
    print(f"Behavior probes: {probe_pass}/{len(results)} passed")
    print()
    print(f"{'Trace':<12} {'Recall':>8}  {'Probes'}")
    for r in results:
        probes_ok = "✓" if (r["probe_no_premature_rec"] and r["probe_eoc"]) else "✗"
        print(f"  {r['file']:<10} {r['score']:>7.2f}  {probes_ok}")


if __name__ == "__main__":
    run_eval()
