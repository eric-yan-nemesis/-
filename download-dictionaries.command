#!/bin/bash
cd "$(dirname "$0")" || exit 1
DICT_PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    DICT_PYTHON="$candidate"
    break
  fi
done
if [ -z "$DICT_PYTHON" ]; then
  echo "请先从 https://www.python.org/downloads/macos/ 安装 Python 3.9 或更新版本。"
  read -r -p "按回车关闭窗口。"
  exit 1
fi
"$DICT_PYTHON" tools/download_dictionaries.py "$@"
DICT_RESULT=$?
echo
if [ "$DICT_RESULT" -eq 0 ]; then
  echo "下载完成。请在上方显示的输出目录中打开 C1C2_英汉词汇.csv 和 请先阅读.txt。"
else
  echo "未能全部完成，请查看上面的错误说明。"
fi
read -r -p "按回车关闭窗口。"
exit "$DICT_RESULT"
