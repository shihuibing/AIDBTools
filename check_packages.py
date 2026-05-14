import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
print(f"Python: {sys.version}")
print()

packages = [
    'openai', 'tiktoken', 'anthropic', 'httpx', 'anyio',
    'distro', 'jiter', 'sniffio', 'tqdm', 'fire',
    'python-dotenv', 'rich', 'tenacity',
    'pydantic', 'jinja2', 'prompt_toolkit'
]

for pkg in packages:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, '__version__', 'unknown')
        print(f"[OK] {pkg}: {ver}")
    except ImportError as e:
        print(f"[MISSING] {pkg}")
