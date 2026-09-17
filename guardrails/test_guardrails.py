"""
guardrails/test_guardrails.py
-----------------------------
Test set demonstrating before/after guardrail behavior.

Run: python3 guardrails/test_guardrails.py
or:  python3 -m pytest guardrails/test_guardrails.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guardrails.guardrail import GuardrailPipeline
from guardrails.output_guards import (
    RefusalConsistencyGuard, ContextGroundingGuard,
    MinimumLengthGuard, SourceCitationGuard
)

# ─── Test cases ───────────────────────────────────────────────────────────────

INPUT_TEST_CASES = [
    # (test_id, query, expect_pass, description)

    # OUT-OF-SCOPE — should be BLOCKED
    ("OUT01", "Who is the President of the United States?",
     False, "Completely out-of-scope political question"),

    ("OUT02", "What is the recipe for chocolate cake?",
     False, "Irrelevant lifestyle question"),

    ("OUT03", "Tell me about the history of ancient Rome.",
     False, "Historical question unrelated to BMU"),

    ("OUT04", "What is the latest score in the cricket match?",
     False, "Sports news — out of scope"),

    ("OUT05", "How do I fix a Python IndexError in my code?",
     False, "Programming question unrelated to BMU university policies"),

    # OVERSIZED INPUT — should be BLOCKED
    ("LEN01", "What is the attendance policy? " * 25,
     False, "Query exceeds 500 char limit"),

    ("LEN02", "A" * 600,
     False, "Raw oversized input (600 chars)"),

    ("LEN03", "Please explain " + "the fee payment calendar " * 30,
     False, "Legitimate topic but repeated to exceed length limit"),

    # INAPPROPRIATE CONTENT — should be BLOCKED
    ("CONT01", "What the fuck is the hostel policy?",
     False, "Contains profanity"),

    ("CONT02", "How do I hack into the university portal?",
     False, "Contains 'hack' — inappropriate intent"),

    # PII — should be BLOCKED
    ("PII01", "My Aadhaar is 1234 5678 9012, what is the fee waiver process?",
     False, "Contains Aadhaar-like number"),

    ("PII02", "Contact me at student@gmail.com about the hostel allocation.",
     False, "Contains email address"),

    # VALID BMU QUERIES — should PASS
    ("VALID01", "What is the minimum attendance required for exams?",
     True, "Valid BMU attendance question"),

    ("VALID02", "Who should I contact if I face ragging on campus?",
     True, "Valid anti-ragging question"),

    ("VALID03", "When is the odd semester fee payment deadline?",
     True, "Valid fee question"),

    ("VALID04", "What are the hostel rules for visitors?",
     True, "Valid hostel/handbook question"),

    ("VALID05", "What is the DAC and what disciplinary actions can it take?",
     True, "Valid DAC policy question"),
]

OUTPUT_TEST_CASES = [
    # (test_id, answer, context, context_available, expect_pass_refusal, expect_pass_length)
    ("OREF01",
     "I couldn't find enough information in the BMU knowledge base to answer that reliably.",
     "", False, True, True,
     "Correct refusal when no context"),

    ("OREF02",
     "The attendance requirement is 75%.",
     "Students must maintain 75% attendance to appear in exams.",
     True, True, True,
     "Correct answer when context available"),

    ("OHALL01",
     "The attendance requirement is 95% as per BMU rules updated in 2024.",
     "", False, False, True,
     "Hallucination — answers when no context (should fail refusal check)"),

    ("OLEN01",
     "Yes.",
     "Hostel rules are defined in the student handbook.",
     True, True, False,
     "Too short answer (3 chars — fails min length)"),

    ("OLEN02",
     "I " + "cannot answer this question. " * 200,
     "Some context here.",
     True, True, False,
     "Excessively long answer (fails max length)"),
]


# ─── Runner ──────────────────────────────────────────────────────────────────

def run_input_tests():
    pipeline = GuardrailPipeline()
    print("\n" + "="*70)
    print("INPUT GUARDRAIL TESTS")
    print("="*70)

    passed_count = failed_count = 0
    results = []

    for tid, query, expect_pass, desc in INPUT_TEST_CASES:
        result = pipeline.check_input(query)
        actual_pass = result.passed
        ok = (actual_pass == expect_pass)

        status = "✅ PASS" if ok else "❌ FAIL"
        guard_info = f"blocked by {result.blocked_by}" if not actual_pass else "allowed"
        print(f"[{tid}] {status} | {desc}")
        print(f"       Query: '{query[:60]}{'...' if len(query)>60 else ''}'")
        print(f"       Expected: {'PASS' if expect_pass else 'BLOCK'} | Got: {'PASS' if actual_pass else 'BLOCK'} ({guard_info})")
        print()

        if ok:
            passed_count += 1
        else:
            failed_count += 1

        results.append({
            "id": tid, "ok": ok, "expected": expect_pass,
            "actual": actual_pass, "guard": result.blocked_by,
            "reason": result.reason, "description": desc
        })

    print(f"Input Guard Results: {passed_count}/{passed_count+failed_count} correct")
    return results, passed_count, failed_count


def run_output_tests():
    print("\n" + "="*70)
    print("OUTPUT GUARDRAIL TESTS")
    print("="*70)

    refusal_guard = RefusalConsistencyGuard()
    length_guard  = MinimumLengthGuard()

    passed_count = failed_count = 0
    results = []

    for tid, answer, context, ctx_avail, exp_refusal, exp_length, desc in OUTPUT_TEST_CASES:
        r_refusal = refusal_guard.check(answer, ctx_avail)
        r_length  = length_guard.check(answer)

        ok_refusal = (r_refusal.passed == exp_refusal)
        ok_length  = (r_length.passed == exp_length)
        ok = ok_refusal and ok_length

        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"[{tid}] {status} | {desc}")
        print(f"       Answer: '{answer[:60]}{'...' if len(answer)>60 else ''}'")
        print(f"       Refusal check: {'✅' if ok_refusal else '❌'} | Length check: {'✅' if ok_length else '❌'}")
        print()

        if ok:
            passed_count += 1
        else:
            failed_count += 1

        results.append({
            "id": tid, "ok": ok, "description": desc,
            "refusal_ok": ok_refusal, "length_ok": ok_length
        })

    print(f"Output Guard Results: {passed_count}/{passed_count+failed_count} correct")
    return results, passed_count, failed_count


def before_after_demo():
    """Demonstrate before/after guardrail behavior clearly."""
    pipeline = GuardrailPipeline()

    print("\n" + "="*70)
    print("BEFORE / AFTER GUARDRAIL DEMONSTRATION")
    print("="*70)

    demos = [
        ("Out-of-scope",
         "Who is the Prime Minister of India?",
         "Without guardrail: Model would attempt to answer from general knowledge → hallucination risk.\n"
         "With guardrail: BLOCKED — 'Your question appears to be outside the scope of the BMU knowledge base.'"),

        ("Oversized input",
         "What is the fee structure? " * 25,
         "Without guardrail: Long prompt could confuse the LLM or enable prompt injection.\n"
         "With guardrail: BLOCKED — 'Your query is too long (X characters). Limit to 500.'"),

        ("PII leak",
         "My phone number is 9876543210, can you help with my fee waiver?",
         "Without guardrail: Personal data sent to LLM and logged — GDPR/privacy risk.\n"
         "With guardrail: BLOCKED — 'Your query appears to contain personal information (Indian phone number).'"),

        ("Valid query",
         "What is the minimum attendance required to appear in exams?",
         "Without guardrail: No difference — valid query goes through.\n"
         "With guardrail: ALLOWED — passes all 4 input guards. RAG pipeline proceeds normally."),
    ]

    for title, query, explanation in demos:
        result = pipeline.check_input(query)
        outcome = f"🚫 BLOCKED by {result.blocked_by}" if not result.passed else "✅ ALLOWED"
        print(f"\n📌 Scenario: {title}")
        print(f"   Query: '{query[:70]}{'...' if len(query)>70 else ''}'")
        print(f"   Guardrail: {outcome}")
        print(f"   {explanation}")


if __name__ == "__main__":
    before_after_demo()
    input_results, ip, if_ = run_input_tests()
    output_results, op, of = run_output_tests()

    total_p = ip + op
    total_f = if_ + of
    total   = total_p + total_f
    print("\n" + "="*70)
    print(f"TOTAL: {total_p}/{total} tests passed ({100*total_p//total}%)")
    print("="*70)

    sys.exit(0 if total_f == 0 else 1)
