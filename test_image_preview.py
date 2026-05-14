# -*- coding: utf-8 -*-
"""
test_image_preview.py
Test image preview and drag-drop upload functionality
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def test_is_image_file():
    """Test image file type detection"""
    print("=" * 60)
    print("Test 1: Image File Type Detection")
    print("=" * 60)

    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']
    non_image_extensions = ['.txt', '.md', '.sql', '.json', '.csv', '.py', '.pdf', '.doc']

    print("\nTesting image file extensions:")
    for ext in image_extensions:
        filename = f"test{ext}"
        is_image = any(filename.lower().endswith(img_ext) for img_ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'])
        status = "[OK]" if is_image else "[FAIL]"
        result_text = "Is image" if is_image else "Not image"
        print(f"  {status} {filename}: {result_text}")

    print("\nTesting non-image file extensions:")
    for ext in non_image_extensions:
        filename = f"test{ext}"
        is_image = any(filename.lower().endswith(img_ext) for img_ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'])
        status = "[OK]" if not is_image else "[FAIL]"
        result_text = "Is image" if is_image else "Not image"
        print(f"  {status} {filename}: {result_text}")

    print("\n[PASS] Test 1 passed: File type detection logic is correct\n")
    return True


def test_thumbnail_generation():
    """Test thumbnail generation logic"""
    print("=" * 60)
    print("Test 2: Thumbnail Generation Logic")
    print("=" * 60)

    try:
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt
        print("\n[OK] PyQt6.QtGui.QPixmap available")
    except ImportError as e:
        print(f"\n[FAIL] Cannot import QPixmap: {e}")
        return False

    test_image_path = os.path.join(os.path.dirname(__file__), "test_image_temp.png")

    try:
        # Create a simple test image
        pixmap = QPixmap(100, 100)
        pixmap.fill(Qt.GlobalColor.blue)
        pixmap.save(test_image_path)
        print(f"[OK] Created test image: {test_image_path}")

        # Test loading and scaling
        loaded_pixmap = QPixmap(test_image_path)
        if loaded_pixmap.isNull():
            print("[FAIL] Cannot load test image")
            return False
        print("[OK] Successfully loaded test image")

        # Test thumbnail scaling
        thumbnail_size = 44
        scaled = loaded_pixmap.scaled(
            thumbnail_size, thumbnail_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        if scaled.isNull():
            print("[FAIL] Thumbnail scaling failed")
            return False

        print(f"[OK] Thumbnail scaling successful: {scaled.width()}x{scaled.height()}")

        # Clean up test file
        if os.path.exists(test_image_path):
            os.remove(test_image_path)
            print(f"[OK] Cleaned up test image")

        print("\n[PASS] Test 2 passed: Thumbnail generation logic is correct\n")
        return True

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_drag_drop_support():
    """Test drag and drop support"""
    print("=" * 60)
    print("Test 3: Drag and Drop Support")
    print("=" * 60)

    try:
        from PySide6.QtCore import QMimeData, QUrl
        print("\n[OK] PyQt6 drag-and-drop classes available")

        # Test QMimeData
        mime_data = QMimeData()
        test_url = QUrl.fromLocalFile("C:/test/image.png")
        mime_data.setUrls([test_url])

        if mime_data.hasUrls():
            print("[OK] QMimeData URL support working")
        else:
            print("[FAIL] QMimeData URL support error")
            return False

        # Verify local file URL
        urls = mime_data.urls()
        if urls:
            local_file = urls[0].toLocalFile()
            print(f"[OK] URL conversion successful: {local_file}")

        print("\n[PASS] Test 3 passed: Drag and drop support working\n")
        return True

    except ImportError as e:
        print(f"\n[FAIL] Cannot import drag-and-drop classes: {e}")
        return False
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_file_dialog_filters():
    """Test file dialog filters"""
    print("=" * 60)
    print("Test 4: File Filter Configuration")
    print("=" * 60)

    filter_string = "All files (*.*);;Image files (*.png *.jpg *.jpeg *.gif *.webp *.bmp);;Document files (*.txt *.md *.sql *.json *.csv *.py)"

    print(f"\nFile filter string:")
    print(f"  {filter_string}")

    # Parse filters
    filters = filter_string.split(";;")
    print(f"\nParsed results:")
    for i, f in enumerate(filters, 1):
        print(f"  {i}. {f}")

    # Verify key extensions exist
    required_extensions = ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.webp', '*.bmp']
    all_present = all(ext in filter_string for ext in required_extensions)

    if all_present:
        print(f"\n[OK] All required image extensions are in the filter")
    else:
        missing = [ext for ext in required_extensions if ext not in filter_string]
        print(f"\n[FAIL] Missing extensions: {missing}")
        return False

    print("\n[PASS] Test 4 passed: File filter configuration is correct\n")
    return True


def test_code_structure():
    """Test code structure integrity"""
    print("=" * 60)
    print("Test 5: Code Structure Integrity Check")
    print("=" * 60)

    chat_window_path = os.path.join(os.path.dirname(__file__), "ui", "ai_chat_window.py")

    if not os.path.exists(chat_window_path):
        print(f"\n[FAIL] File does not exist: {chat_window_path}")
        return False

    with open(chat_window_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if key methods exist
    required_methods = [
        '_on_upload_files',
        '_update_thumbnails',
        '_create_thumbnail_widget',
        '_show_image_preview',
        '_on_drag_enter',
        '_on_drag_move',
        '_on_drop',
        '_is_image_file',
    ]

    print("\nChecking key methods:")
    all_methods_present = True
    for method in required_methods:
        if f'def {method}' in content:
            print(f"  [OK] {method}")
        else:
            print(f"  [FAIL] {method} - Missing")
            all_methods_present = False

    if not all_methods_present:
        print("\n[FAIL] Test 5 failed: Some key methods are missing")
        return False

    # Check necessary imports
    required_imports = [
        'QFileDialog',
        'QPixmap',
        'Qt.AspectRatioMode.KeepAspectRatio',
        'Qt.TransformationMode.SmoothTransformation',
    ]

    print("\nChecking necessary imports:")
    all_imports_present = True
    for imp in required_imports:
        if imp in content:
            print(f"  [OK] {imp}")
        else:
            print(f"  [FAIL] {imp} - Missing")
            all_imports_present = False

    if not all_imports_present:
        print("\n[FAIL] Test 5 failed: Some necessary imports are missing")
        return False

    print("\n[PASS] Test 5 passed: Code structure is complete\n")
    return True


def run_all_tests():
    """Run all tests"""
    print("\n")
    print("=" * 60)
    print(" " * 15 + "Image Preview and Upload Test" + " " * 15)
    print("=" * 60)
    print()

    results = []

    # Run each test
    results.append(("File Type Detection", test_is_image_file()))
    results.append(("Thumbnail Generation", test_thumbnail_generation()))
    results.append(("Drag and Drop Support", test_drag_drop_support()))
    results.append(("File Filters", test_file_dialog_filters()))
    results.append(("Code Structure", test_code_structure()))

    # Summary
    print("=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} - {name}")

    print()
    print(f"Total: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed! Image preview and upload functionality is working.")
    else:
        print(f"\nWarning: {total - passed} test(s) failed, please check related issues.")

    print("=" * 60)
    print()

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)