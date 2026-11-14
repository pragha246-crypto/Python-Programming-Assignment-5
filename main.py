"""Run the complete Assignment 5 workflow and a lightweight profiler."""
import cProfile
import pstats
from io import StringIO
from complaint_system import run_pipeline, OUTPUT_DIR

def main():
    profiler = cProfile.Profile()
    profiler.enable()
    result = run_pipeline()
    profiler.disable()
    stream = StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(15)
    (OUTPUT_DIR / "profile_summary.txt").write_text(stream.getvalue(), encoding="utf-8")
    print("Assignment 5 pipeline completed.")
    print(f"Accepted: {result['accepted']} | Rejected: {result['rejected']}")
    print(f"Charts: {', '.join(result['charts'])}")
    print(f"Summary agreement: first-k={result['summary_evaluation']['baseline_mean_agreement']}, "
          f"frequency={result['summary_evaluation']['frequency_mean_agreement']}")

if __name__ == "__main__":
    main()
