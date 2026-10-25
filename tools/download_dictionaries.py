#!/usr/bin/env python3
"""Download pinned reference files and build a private local bilingual study CSV."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ECDICT_BASE = 'https://raw.githubusercontent.com/skywind3000/ECDICT/ab22ad36302cafc6349a050e2b60894855208055/'
PROFILE_BASE = 'https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/d4e45b75b38f27b30dfc5c44d8c571aec7e7092f/'
PROFILE_NAME = 'octanove-vocabulary-profile-c1c2-1.0.csv'
SOURCES = [
    ('ecdict/ecdict.csv', ECDICT_BASE + 'ecdict.csv', 'd1ecbdf9ee2b920afb6f430ca6b6bb9f559588cf0dff86e04bd255f9390843cc'),
    ('ecdict/LICENSE', ECDICT_BASE + 'LICENSE', 'f8552dd246f61a4e064569eae6194a01c6b3d63b03bf27c6ca863593c549ed0f'),
    ('ecdict/README.md', ECDICT_BASE + 'README.md', '0c3f95fc7e15f7eccf65feedb58ba3ebace1fe7b7cbdd1af60c9ace4cef9094b'),
    ('octanove/' + PROFILE_NAME, PROFILE_BASE + PROFILE_NAME, '18c33a407f2f89f7b8de9671c6d45fe3ea0bce45e7d2d7dcaab48d73e0f7b380'),
    ('octanove/UPSTREAM_README.md', PROFILE_BASE + 'README.md', '8b69f7366fa3c7be328cb9ba02ceb7b3725697f36125bb75b85131d664b5e359'),
    ('octanove/CC-BY-SA-4.0.txt', 'https://raw.githubusercontent.com/spdx/license-list-data/31ba1a50e5397e00a304dbadc76531740e89ee48/text/CC-BY-SA-4.0.txt', 'cde7883b9050a1104f4ac19a1572aafd6e5d7323b68351aaf51fbf4beba54966'),
]
MAX_BYTES = 100 * 1024 * 1024
NOTICE = '''本目录是本机下载的学习资料，请勿提交 GitHub。

等级来源：Octanove Labs / Open Language Profiles，C1/C2 v1.0，CC BY-SA 4.0。
https://creativecommons.org/licenses/by-sa/4.0/
中文和英文释义来源：ECDICT，仓库级 MIT 许可，保留 ecdict/LICENSE 与 README。
ECDICT 上游说明其数据合并自多个来源；本工具未逐条审计释义权利，不将它视为商业词典的完整版权授权。

加工方式：去除完全重复的等级记录，按词头（忽略大小写）连接释义，并将转义换行还原为换行。
这仅是同词头资料合并，尚未核实 CEFR 词性/义项与释义的对应关系，不能把任意义项都断言为 C1/C2。
资料不是 Cambridge English Vocabulary Profile；没有凭词频、考试标签或词形推测 CEFR。
例句字段保留空白，不编造例句。未收录的词并不代表低于 C1。
等级资料的改编继续遵守 CC BY-SA 4.0；不同来源的释义保留各自来源及权利说明。

C1C2_英汉词汇.csv 是 UTF-8 BOM 编码，可以用 Excel、Numbers 或文本编辑器打开。
下载完成并不代表 LexiScope 已自动接入此词库；此版本仅负责下载与生成本地学习表。
'''


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def install_temp(temp, destination):
    """Create without replacing any existing user file, including a race."""
    try:
        os.link(temp, destination)
    except FileExistsError:
        if sha256(temp) != sha256(destination):
            raise ValueError('已有文件与下载/生成内容不同，为保护你的文件已停止：' + str(destination))
    finally:
        temp.unlink(missing_ok=True)


def obtain(destination, url, expected, local_source=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256(destination) != expected:
            raise ValueError('已有文件校验不匹配，不会覆盖。请换一个空目录或自行备份：' + str(destination))
        print('复用已校验文件：' + destination.name, flush=True)
        return
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.download-', delete=False) as temp:
        temporary = Path(temp.name)
        try:
            if local_source:
                if sha256(local_source) != expected:
                    raise ValueError('指定的本地来源不是所需固定版本：' + str(local_source))
                with local_source.open('rb') as source:
                    shutil.copyfileobj(source, temp)
            else:
                print('正在下载：' + destination.name, flush=True)
                request = urllib.request.Request(url, headers={'User-Agent': 'LexiScope-Dictionary-Downloader/1.0'})
                total = 0
                with urllib.request.urlopen(request, timeout=45) as response:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise ValueError('下载超过 100 MiB 限制，已停止。')
                        temp.write(chunk)
            temp.flush()
            os.fsync(temp.fileno())
            if sha256(temporary) != expected:
                raise ValueError('下载内容校验失败，不能使用：' + destination.name)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    install_temp(temporary, destination)


def save_generated(destination, data):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.generated-', delete=False) as temp:
        temp.write(data)
        temporary = Path(temp.name)
    install_temp(temporary, destination)


def build_study_csv(output):
    with (output / 'octanove' / PROFILE_NAME).open(encoding='utf-8-sig', newline='') as handle:
        raw = list(csv.DictReader(handle))
    profiles = []
    seen = set()
    for entry in raw:
        if entry['CEFR'] not in {'C1', 'C2'}:
            raise ValueError('等级来源含意外的非 C1/C2 数据，已停止。')
        key = tuple(entry[k] for k in ('headword', 'pos', 'CEFR', 'notes'))
        if key not in seen:
            profiles.append(entry)
            seen.add(key)
    wanted = {entry['headword'].lower() for entry in profiles}
    found = {}
    source_count = 0
    csv.field_size_limit(10 * 1024 * 1024)
    with (output / 'ecdict' / 'ecdict.csv').open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not {'word', 'definition', 'translation'}.issubset(reader.fieldnames or []):
            raise ValueError('ECDICT 格式不符合预期。')
        for entry in reader:
            source_count += 1
            word = entry['word'].lower()
            if word in wanted and word not in found:
                found[word] = entry
    text = io.StringIO(newline='')
    fields = ['headword', 'pos', 'CEFR', 'cefr_notes', 'chinese', 'definition', 'example', 'level_source', 'glossary_source', 'uncertainty']
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    chinese_count = english_count = 0
    for profile in profiles:
        gloss = found.get(profile['headword'].lower(), {})
        chinese = gloss.get('translation', '').replace('\\n', '\n')
        english = gloss.get('definition', '').replace('\\n', '\n')
        chinese_count += bool(chinese.strip())
        english_count += bool(english.strip())
        writer.writerow({
            'headword': profile['headword'], 'pos': profile['pos'], 'CEFR': profile['CEFR'],
            'cefr_notes': profile['notes'], 'chinese': chinese, 'definition': english, 'example': '',
            'level_source': PROFILE_BASE + PROFILE_NAME,
            'glossary_source': ECDICT_BASE + 'ecdict.csv' if gloss else '',
            'uncertainty': '等级来自开放词表；释义仅按词头连接，词性及义项对应未经核实。' if gloss else '缺少匹配释义；等级词性及义项仍需核对。',
        })
    destination = output / 'C1C2_英汉词汇.csv'
    save_generated(destination, text.getvalue().encode('utf-8-sig'))
    counts = {'ecdict_entries': source_count, 'profile_raw_rows': len(raw), 'profile_distinct_rows': len(profiles),
              'unique_headwords': len(wanted), 'matched_headwords': len(found), 'rows_with_chinese': chinese_count,
              'rows_with_english': english_count, 'examples_generated': 0}
    manifest = {
        'format_version': 1, 'counts': counts,
        'transforms': ['exact profile row deduplication', 'case-insensitive headword-only join', 'restore escaped newlines'],
        'sense_alignment_verified': False, 'source_records': [
            {'file': name, 'url': url, 'sha256': digest, 'bytes': (output / name).stat().st_size}
            for name, url, digest in SOURCES],
        'generated_csv_sha256': sha256(destination),
        'attribution': {'cefr': 'Octanove Labs / Open Language Profiles; CC BY-SA 4.0',
                        'definitions': 'ECDICT; repository MIT license, mixed upstream sources not individually audited'},
    }
    save_generated(output / 'manifest.json', (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode())
    save_generated(output / '请先阅读.txt', NOTICE.encode('utf-8'))
    return counts


def main():
    parser = argparse.ArgumentParser(description='下载开放词库并生成本机 C1/C2 英汉学习表。')
    parser.add_argument('--output', type=Path, default=ROOT / 'dictionaries-local', help='本地输出目录')
    parser.add_argument('--ecdict-file', type=Path, help='复用已下载且校验匹配的 ECDICT CSV')
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    print('预计首次下载约 63 MiB；不需要 API 密钥。', flush=True)
    for name, url, digest in SOURCES:
        local = args.ecdict_file if name == 'ecdict/ecdict.csv' else None
        bundled = ROOT / 'data' / Path(name).name
        if not local and bundled.is_file() and sha256(bundled) == digest:
            local = bundled
        obtain(output / name, url, digest, local)
    counts = build_study_csv(output)
    print('完成：' + str(output / 'C1C2_英汉词汇.csv'))
    print('去重等级记录：{profile_distinct_rows}；不同词头：{unique_headwords}；含中文释义的记录：{rows_with_chinese}。'.format(**counts))
    print('重要：仅按词头合并，等级与释义的词义对应未核实；完整来源和许可见“请先阅读.txt”。')
    print('文件留在本机；尚未自动导入 LexiScope 网站。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, csv.Error) as error:
        print('下载或生成失败：' + str(error), file=sys.stderr)
        print('已有文件不会被覆盖；网络恢复后可以重新运行，已校验文件会复用。', file=sys.stderr)
        sys.exit(1)
