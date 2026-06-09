import os
import shutil

def on_config(config, **kwargs):
    """
    Hook to dynamically copy CHANGELOG.md from project root
    into the docs/ directory before the build starts.
    """
    docs_dir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.dirname(docs_dir)
    src = os.path.join(project_root, 'CHANGELOG.md')
    dst = os.path.join(docs_dir, 'changelog.md')
    
    if os.path.exists(src):
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print(f"INFO    -  [hook] Copied {src} to {dst}")
