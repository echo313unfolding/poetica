#!/usr/bin/env bash
# Grade 5 Robotics — Full Curriculum Demo
# Runs the complete pipeline from teacher syllabus to student lesson.
#
# Usage:
#   bash demos/grade5_robotics/run_demo.sh
#
# Must be run from the poetica package root directory.

set -euo pipefail

DEMO_DIR="demos/grade5_robotics"
PYTHON="${PYTHON:-python3}"
POETICA="$PYTHON -c 'from poetica.cli import main; main()' --"
ERRORS=0

run_step() {
    local step="$1"
    shift
    echo ""
    echo "========================================================================"
    echo "  $step"
    echo "========================================================================"
    echo ""
    echo "  \$ poetica $*"
    echo ""

    # Build the Python command
    local args=""
    for arg in "$@"; do
        args="$args '$arg',"
    done

    if $PYTHON -c "
import sys
sys.argv = ['poetica', $args]
from poetica.cli import main
main()
" 2>&1; then
        echo ""
        echo "  --> OK"
    else
        echo ""
        echo "  --> FAILED (exit $?)"
        ERRORS=$((ERRORS + 1))
    fi
}

echo "============================================================"
echo "  POETICA GRADE 5 ROBOTICS — FULL CURRICULUM DEMO"
echo "============================================================"
echo ""
echo "  This demo shows the complete pipeline:"
echo "  syllabus -> curriculum -> lesson -> visual -> evidence"
echo ""

# Step 1: Inspect syllabus
run_step "STEP 1: Inspect the teacher syllabus" \
    syllabus inspect "$DEMO_DIR/syllabus.txt"

# Step 2: Draft curriculum (output already exists, regenerate)
run_step "STEP 2: Draft curriculum YAML" \
    syllabus draft "$DEMO_DIR/syllabus.txt" \
    --subject Robotics --grade-band 5 --domain robotics

# Step 3: Inspect generated curriculum
run_step "STEP 3: Inspect the generated curriculum" \
    curriculum inspect "$DEMO_DIR/generated_curriculum.yaml"

# Step 4: Show concept map
run_step "STEP 4: Concept map" \
    curriculum map "$DEMO_DIR/generated_curriculum.yaml"

# Step 5: Generate lesson
run_step "STEP 5: Lesson for input_condition_action" \
    curriculum lesson "$DEMO_DIR/generated_curriculum.yaml" \
    input_condition_action --format lesson --domain robotics

# Step 6: Evidence schema
run_step "STEP 6: Evidence schema" \
    curriculum evidence "$DEMO_DIR/generated_curriculum.yaml" \
    input_condition_action --format json

# Step 7a: Align poem with domain provenance
run_step "STEP 7a: Align obstacle_stop.poem (domain provenance)" \
    align "$DEMO_DIR/obstacle_stop.poem" --domain robotics --format lesson

# Step 7b: Play in visual world
run_step "STEP 7b: Play in robot_grid world" \
    play "$DEMO_DIR/obstacle_stop.poem" --domain robotics --world robot_grid

# Step 7c: Compile to Python
run_step "STEP 7c: Compile to Python" \
    compile "$DEMO_DIR/obstacle_stop.poem" --domain robotics --type sonnet --level 2

echo ""
echo "============================================================"
if [ $ERRORS -eq 0 ]; then
    echo "  DEMO COMPLETE: all steps passed"
else
    echo "  DEMO COMPLETE: $ERRORS step(s) failed"
fi
echo "============================================================"

exit $ERRORS
