"""Validate the new engine against known grading results.

Runs the 3-grader consensus engine on a previously graded student
and compares the consensus scores against the known-good scores.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from grader.engine import init, grade_student


def load_known_result(path: Path) -> dict:
    """Load a previously saved grading result."""
    return json.loads(path.read_text(encoding="utf-8"))


def compare(known: dict, new_result) -> None:
    """Compare known scores vs new consensus scores."""
    print(f"\n{'Q':<4} {'Known':>6} {'New':>6} {'Match':>6}  Consensus Method")
    print("-" * 50)

    matches = 0
    total_qs = 0

    for qnum_str, known_q in known["questions"].items():
        known_score = known_q.get("total_score", 0)
        known_max = known_q.get("total_max", 0)

        new_q = new_result.questions.get(qnum_str)
        if new_q is None:
            print(f"Q{qnum_str:<3} {known_score:>3}/{known_max:<3} {'SKIP':>6}")
            continue

        new_score = new_q.final_score.total_score
        new_max = new_q.final_score.total_max
        method = new_q.consensus_method.value
        match = "YES" if known_score == new_score else "NO"

        if known_score == new_score:
            matches += 1
        total_qs += 1

        scores_detail = ", ".join(str(r.total_score) for r in new_q.runs)
        print(
            f"Q{qnum_str:<3} {known_score:>3}/{known_max:<3} {new_score:>3}/{new_max:<3} "
            f"{match:>5}  {method} ({scores_detail})"
        )

    print("-" * 50)
    print(
        f"Known total: {known['total_score']}/{known['total_max']}  "
        f"New total: {new_result.total_score}/{new_result.total_max}"
    )
    print(f"Question agreement: {matches}/{total_qs} ({100*matches/total_qs:.0f}%)")


def main():
    # Initialize engine
    init()

    # --- Luca Besaw G3.1 ---
    print("=" * 60)
    print("VALIDATION: Luca Besaw — G3.1 (3-run consensus)")
    print("=" * 60)

    known_path = ROOT / "grader" / "results" / "Luca_Besaw_G3.1_V2.json"
    if not known_path.exists():
        print(f"Known result not found: {known_path}")
        return

    known = load_known_result(known_path)

    responses = {
        1: "My family has two dogs, their names are Lucy and Rocket.",
        2: "What is the one place we do not take our dogs?",
        3: "They never go to restaurants with us.",
        4: "Dogs might growl or bite because they are nervous or tired.",
        5: "Restaurants are for people, not dogs.",
        6: "I would feel joyful and happy.",
        7: "I would grab some of my food lead him outside say sit shake give him the food and then say now stop.",
        8: "My local baseball field/park has a no dog rule which I think should be changed because there is a lot of room for dogs to run so I think they should change the no dog rule.",
        9: "I like to run in the backyard with my dog, play with him, and feed him treats.",
        10: "Do not forget to feed your pet and make sure you give your pet lots of love.",
        11: "Soil or dirt, whatever you want to call it is very important in our lives. Plants need soil to grow, and without plants we wouldn't have food. Animals eat the plants that grow from the soil. When leaves fall and bugs die, they rot and turn into rich, black humus. Humus goes back into the soil and helps more plants grow. Without soil, life on Earth would be very different.",
    }

    new_result = grade_student(
        test_code="G3.1",
        responses=responses,
        student_name="Luca Besaw",
        num_runs=3,
        save=False,
    )

    compare(known, new_result)


if __name__ == "__main__":
    main()
