#!/bin/bash
# Run all math benchmarks with Claude Code (100 iterations each).
# Uncomment the next batch once the current one finishes.
# Run from repo root: bash run_math_benchmarks.sh
# Monitor: tail -f outputs_claude/<benchmark>/progress.log

cd "$(dirname "$0")"

OUTDIR="outputs_claude"
CMD="skydiscover-run"
SEARCH="claude_code"
MODEL="claude-sonnet-4-6"
ITERS=100
BENCH="benchmarks/math"

# ─────────────────────────────────────────────────────────────────────────────
# BATCH 1 — circle packing + signal processing
# ─────────────────────────────────────────────────────────────────────────────

$CMD $BENCH/signal_processing/initial_program.py   $BENCH/signal_processing/evaluator   -c $BENCH/signal_processing/config.yaml   -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/signal_processing   &
$CMD $BENCH/circle_packing/initial_program.py      $BENCH/circle_packing/evaluator      -c $BENCH/circle_packing/config.yaml      -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/circle_packing      &
$CMD $BENCH/circle_packing_rect/initial_program.py $BENCH/circle_packing_rect/evaluator -c $BENCH/circle_packing_rect/config.yaml -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/circle_packing_rect &

wait
echo "Batch 1 done."

# ─────────────────────────────────────────────────────────────────────────────
# BATCH 3 — heilbronn family
# ─────────────────────────────────────────────────────────────────────────────

# $CMD $BENCH/heilbronn_triangle/initial_program.py  $BENCH/heilbronn_triangle/evaluator  -c $BENCH/heilbronn_triangle/config.yaml  -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/heilbronn_triangle  &
# $CMD $BENCH/heilbronn_convex/13/initial_program.py $BENCH/heilbronn_convex/13/evaluator -c $BENCH/heilbronn_convex/13/config.yaml -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/heilbronn_convex_13 &
# $CMD $BENCH/heilbronn_convex/14/initial_program.py $BENCH/heilbronn_convex/14/evaluator -c $BENCH/heilbronn_convex/14/config.yaml -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/heilbronn_convex_14 &

# wait
# echo "Batch 3 done."

# ─────────────────────────────────────────────────────────────────────────────
# BATCH 4 — minimizing / autocorr family
# ─────────────────────────────────────────────────────────────────────────────

# $CMD $BENCH/minimizing_max_min_dist/2/initial_program.py $BENCH/minimizing_max_min_dist/2/evaluator -c $BENCH/minimizing_max_min_dist/2/config.yaml -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/minimizing_max_min_dist_2 &
# $CMD $BENCH/minimizing_max_min_dist/3/initial_program.py $BENCH/minimizing_max_min_dist/3/evaluator -c $BENCH/minimizing_max_min_dist/3/config.yaml -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/minimizing_max_min_dist_3 &
# $CMD $BENCH/first_autocorr_ineq/initial_program.py       $BENCH/first_autocorr_ineq/evaluator       -c $BENCH/first_autocorr_ineq/config.yaml       -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/first_autocorr_ineq       &
# $CMD $BENCH/second_autocorr_ineq/initial_program.py      $BENCH/second_autocorr_ineq/evaluator      -c $BENCH/second_autocorr_ineq/config.yaml      -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/second_autocorr_ineq      &

# wait
# echo "Batch 4 done."

# ─────────────────────────────────────────────────────────────────────────────
# BATCH 5 — erdos / third autocorr
# ─────────────────────────────────────────────────────────────────────────────

# $CMD $BENCH/third_autocorr_ineq/initial_program.py $BENCH/third_autocorr_ineq/evaluator -c $BENCH/third_autocorr_ineq/config.yaml -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/third_autocorr_ineq &
# $CMD $BENCH/erdos_min_overlap/initial_program.py   $BENCH/erdos_min_overlap/evaluator   -c $BENCH/erdos_min_overlap/config.yaml   -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/erdos_min_overlap   &

# wait
# echo "Batch 5 done."

# ─────────────────────────────────────────────────────────────────────────────
# BATCH 6 — hexagon packing (last, most compute-heavy)
# ─────────────────────────────────────────────────────────────────────────────

# $CMD $BENCH/hexagon_packing/11/initial_program.py $BENCH/hexagon_packing/11/evaluator -c $BENCH/hexagon_packing/11/config.yaml -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/hexagon_packing_11 &
# $CMD $BENCH/hexagon_packing/12/initial_program.py $BENCH/hexagon_packing/12/evaluator -c $BENCH/hexagon_packing/12/config.yaml -s $SEARCH -m $MODEL -i $ITERS -o $OUTDIR/hexagon_packing_12 &

# wait
# echo "Batch 6 done."
