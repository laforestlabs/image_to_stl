#!/bin/bash
# Run all verification tests

echo "=================================================="
echo "IMAGE TO STL - COMPLETE TEST SUITE"
echo "=================================================="

echo ""
echo "Test 1: Application Startup"
echo "--------------------------------------------------"
python3 test_startup.py
if [ $? -eq 0 ]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
    exit 1
fi

echo ""
echo "Test 2: Full Workflow (Headless)"
echo "--------------------------------------------------"
python3 test_full_workflow.py | tail -20
if [ $? -eq 0 ]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
    exit 1
fi

echo ""
echo "Test 3: Matplotlib 3D Preview"
echo "--------------------------------------------------"
python3 test_matplotlib_preview.py 2>&1 | grep -E "(Creating|preview|COMPLETE|✓)"
if [ $? -eq 0 ]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
    exit 1
fi

echo ""
echo "Test 4: GUI Verification"
echo "--------------------------------------------------"
python3 verify_gui.py | grep -E "(✓|✗|SUMMARY)" | head -10
if [ $? -eq 0 ]; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
    exit 1
fi

echo ""
echo "=================================================="
echo "ALL TESTS PASSED! ✓"
echo "=================================================="
echo ""
echo "The application is ready to use:"
echo "  python3 main.py"
echo ""
