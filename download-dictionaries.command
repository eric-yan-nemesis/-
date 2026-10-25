#!/bin/bash
cd "$(dirname "$0")" || exit 1
DICT_PYTHON=""
for candidate in .venv/bin/python python3.14 python3.13 python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    DICT_PYTHON="$candidate"
    break
  fi
done
if [ -z "$DICT_PYTHON" ]; then
  echo "请先从 https://www.python.org/downloads/macos/ 安装 Python 3.12 或更新版本。"
  read -r -p "按回车关闭窗口。"
  exit 1
fi
echo "项目已附带可离线使用的个人词典，正常使用无需执行本工具。"
echo "本工具用于可选重建：Octanove 提供等级，Wordset 提供原始英文释义和用例。"
echo "没有缓存时会下载约 17 MB 的固定版本 Wordset 资料；不会下载 ECDICT。"
"$DICT_PYTHON" tools/build_personal_dictionary.py "$@"
DICT_RESULT=$?
echo
if [ "$DICT_RESULT" -eq 0 ]; then
  echo "个人词典已重建。默认文件为 data/lexiscope_dictionary.json。"
  echo "重新启动网站后，可在“我的词典”中查词和下载 JSON。"
else
  echo "未能全部完成，请查看上面的错误说明。"
fi
read -r -p "按回车关闭窗口。"
exit "$DICT_RESULT"
