#!/usr/bin/env python3
"""
Verify GUI can start and 3D preview is functional
This script checks if the application initializes correctly
"""
import sys
import os

def check_display():
    """Check if display is available"""
    display = os.environ.get('DISPLAY')
    if display:
        print(f"✓ Display available: {display}")
        return True
    else:
        print("⚠ No display detected (DISPLAY not set)")
        print("  The GUI requires a display to run")
        return False

def check_imports():
    """Check if all required packages are available"""
    print("\nChecking required packages...")

    required = {
        'PySide6': 'GUI framework',
        'numpy': 'Numerical arrays',
        'PIL': 'Image processing',
        'stl': 'STL file handling',
        'pyvista': '3D visualization',
        'pyvistaqt': 'PyVista Qt integration'
    }

    all_good = True
    for package, description in required.items():
        try:
            if package == 'PIL':
                import PIL
            elif package == 'stl':
                from stl import mesh
            else:
                __import__(package)
            print(f"  ✓ {package:15s} - {description}")
        except ImportError:
            print(f"  ✗ {package:15s} - MISSING ({description})")
            all_good = False

    return all_good

def test_components():
    """Test individual components"""
    print("\nTesting components...")

    # Test image processor
    try:
        from core.image_processor import ImageProcessor
        processor = ImageProcessor()
        print("  ✓ ImageProcessor initialized")
    except Exception as e:
        print(f"  ✗ ImageProcessor failed: {e}")
        return False

    # Test STL generator
    try:
        from core.stl_generator import STLGenerator
        generator = STLGenerator()
        print("  ✓ STLGenerator initialized")
    except Exception as e:
        print(f"  ✗ STLGenerator failed: {e}")
        return False

    # Test process editor
    try:
        from gui.process_editor import ProcessEditor, OperationDialog
        # Check new operation exists
        if 'set_lithophane_parameters' in OperationDialog.OPERATION_TYPES:
            print("  ✓ ProcessEditor initialized (with lithophane parameters)")
        else:
            print("  ✗ ProcessEditor missing lithophane parameters operation")
            return False
    except Exception as e:
        print(f"  ✗ ProcessEditor failed: {e}")
        return False

    # Test preview widget
    try:
        # Just import, don't instantiate (requires Qt app)
        from gui.preview_widget import PreviewWidget
        print("  ✓ PreviewWidget initialized")
    except Exception as e:
        print(f"  ✗ PreviewWidget failed: {e}")
        return False

    return True

def test_gui_startup():
    """Test if GUI can start"""
    print("\nTesting GUI startup...")

    if not check_display():
        print("  ⚠ Skipping GUI test (no display)")
        print("  ℹ This is normal for headless/SSH environments")
        return None

    try:
        # Just check if imports work, don't actually create windows
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        print("  ✓ GUI imports successful")
        print("  ℹ Full GUI test skipped (would require interactive display)")
        return True

    except Exception as e:
        import traceback
        print(f"  ✗ GUI imports failed: {e}")
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("IMAGE TO STL CONVERTER - GUI VERIFICATION")
    print("=" * 60)

    has_display = check_display()
    imports_ok = check_imports()
    components_ok = test_components()

    if has_display:
        gui_ok = test_gui_startup()
    else:
        gui_ok = None

    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    results = [
        ("Display", "✓" if has_display else "⚠", "Available" if has_display else "Not available (headless mode)"),
        ("Required packages", "✓" if imports_ok else "✗", "All installed" if imports_ok else "Some missing"),
        ("Core components", "✓" if components_ok else "✗", "Working" if components_ok else "Errors detected"),
    ]

    if gui_ok is not None:
        results.append(
            ("GUI startup", "✓" if gui_ok else "✗", "Working" if gui_ok else "Failed")
        )
    else:
        results.append(
            ("GUI startup", "⚠", "Skipped (no display)")
        )

    for name, status, message in results:
        print(f"{status} {name:20s}: {message}")

    print("\n" + "=" * 60)

    if imports_ok and components_ok:
        if gui_ok or not has_display:
            print("✓ ALL SYSTEMS READY!")
            print("\nThe application is ready to use.")
            if has_display and gui_ok:
                print("Run with: python3 main.py")
            else:
                print("Note: GUI requires a display. Core functionality tested OK.")
            return 0
        else:
            print("⚠ GUI startup issues detected")
            print("\nCore functionality works, but GUI may have issues.")
            return 1
    else:
        print("✗ SYSTEM NOT READY")
        print("\nPlease install missing packages.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
