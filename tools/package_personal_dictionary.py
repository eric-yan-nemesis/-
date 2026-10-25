#!/usr/bin/env python3
"""Create a reproducible, self-contained dictionary download with source notices."""
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    'lexiscope_dictionary.json': 'lexiscope_dictionary.json',
    'lexiscope_dictionary.sha256': 'lexiscope_dictionary.sha256',
    'README.zh-CN.md': 'PERSONAL_DICTIONARY.md',
    'octanove-vocabulary-profile-c1c2-1.0.csv': 'octanove-vocabulary-profile-c1c2-1.0.csv',
    'SOURCES.md': 'SOURCES.md',
    'UPSTREAM_README.md': 'UPSTREAM_README.md',
    'CC-BY-SA-4.0.txt': 'CC-BY-SA-4.0.txt',
    'wordset/LICENSE': 'wordset/LICENSE',
    'wordset/README.md': 'wordset/README.md',
    'wordset/PRINCETON_WORDNET_LICENSE.txt': 'wordset/PRINCETON_WORDNET_LICENSE.txt',
}


def main():
    parser = argparse.ArgumentParser(description='打包个人词典与来源许可，不包含网站程序。')
    parser.add_argument('--output', type=Path, default=ROOT / 'downloads' / 'LexiScope-personal-dictionary.zip')
    args = parser.parse_args()
    source = ROOT / 'data'
    expected = (source / 'lexiscope_dictionary.sha256').read_text().split()[0]
    if hashlib.sha256((source / 'lexiscope_dictionary.json').read_bytes()).hexdigest() != expected:
        raise ValueError('个人词典校验失败，停止打包。')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, relative in FILES.items():
            info = zipfile.ZipInfo('LexiScope-personal-dictionary/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (source / relative).read_bytes(), compresslevel=9)
    print('已生成独立词典数据包：', args.output)


if __name__ == '__main__':
    main()
