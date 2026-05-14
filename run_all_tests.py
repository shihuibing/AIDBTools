import sys
sys.path.insert(0, '.')

print("Importing test module...")
from test_image_preview import (
    test_is_image_file,
    test_thumbnail_generation,
    test_drag_drop_support,
    test_file_dialog_filters,
    test_code_structure
)

print("\n" + "=" * 60)
print("Running Test 1: File Type Detection")
print("=" * 60)
r1 = test_is_image_file()

print("\n" + "=" * 60)
print("Running Test 2: Thumbnail Generation")
print("=" * 60)
r2 = test_thumbnail_generation()

print("\n" + "=" * 60)
print("Running Test 3: Drag and Drop Support")
print("=" * 60)
r3 = test_drag_drop_support()

print("\n" + "=" * 60)
print("Running Test 4: File Filters")
print("=" * 60)
r4 = test_file_dialog_filters()

print("\n" + "=" * 60)
print("Running Test 5: Code Structure")
print("=" * 60)
r5 = test_code_structure()

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
results = [
    ("File Type Detection", r1),
    ("Thumbnail Generation", r2),
    ("Drag and Drop Support", r3),
    ("File Filters", r4),
    ("Code Structure", r5),
]
for name, result in results:
    status = "PASS" if result else "FAIL"
    print(f"  [{status}] {name}")

passed = sum(1 for _, r in results if r)
total = len(results)
print(f"\nTotal: {passed}/{total} tests passed")

if passed == total:
    print("\nAll tests passed!")
else:
    print(f"\n{total - passed} test(s) failed.")

sys.exit(0 if passed == total else 1)
