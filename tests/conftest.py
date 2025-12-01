# tests/conftest.py
import os
import sys

# 找到项目根目录（Her_Server）
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 把项目根目录放到 sys.path 最前面
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
