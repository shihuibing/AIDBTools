import sys
sys.path.insert(0, '.')
from test_image_preview import run_all_tests
success = run_all_tests()
sys.exit(0 if success else 1)
