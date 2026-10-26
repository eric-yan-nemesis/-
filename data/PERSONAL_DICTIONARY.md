# LexiScope 个人词典：Octanove × Wordset

本地文件 `lexiscope_dictionary.json` 将 **Octanove 的 C1/C2 等级记录**与 **Wordset 的英文义项、定义和原始用例**组合。它可以随应用离线使用，不需要查询在线词典，也不需要模型 API。词典内容不包含 ECDICT、模型生成例句或上传文章中的句子。

这两个来源都没有提供这份组合词典的逐义项中文翻译。现有应用中的人工中文学习注释或可选 AI 中文解释，应保留各自来源，不能显示成 Wordset 原文。

## 组合方式

1. 保留 Octanove 原始文件，去除完全重复的行后，按原词头合并等级记录。原始词性、等级及义项备注不作改写。
2. 忽略大小写连接同词头 Wordset 记录。对源词头明确列出的斜杠拼写，例如 `scrutinize/scrutinise`，分别查找两种拼写；每条义项的 `wordset_word` 保留实际来源拼写。不同大小写、不同拼写的源内容仍可分别追溯。
3. 保留所有命中 Wordset 义项的原始 ID、词性、定义及 `example` 文本。用例存为 `examples` 数组；没有例句时保留 `[]`，没有词条时保留 `senses: []`。
4. 仅去除词条拼写、义项 ID、定义、词性和用例均相同的重复义项。不会通过同义词或猜测词干来补齐缺失词条。
5. **等级与 Wordset 义项不自动绑定。** `cefr` 数组记录等级资料，`senses` 数组记录词典义项。两者有相同词性，也不代表具体义项或文章中的语境已经核实。

例如 `brief` 的 Octanove 记录包括 C1 动词、C2 名词（备注为法律用语）；Wordset 另外包含形容词义项。不能把“brief 形容词”也标成 C1 或 C2。`cast` 的不同义项同样需要保留备注并核对。

## 本次实际覆盖

| 项目 | 数量 |
| --- | ---: |
| Octanove 原始记录 | 2,136 |
| 去重后的等级记录 | 2,108 |
| 不同原始词头 | 1,955 |
| 有 Wordset 义项的原始词头 | 1,844 |
| 有至少一条 Wordset 用例的原始词头 | 1,060 |
| 无 Wordset 用例的原始词头 | 895 |
| 保留的 Wordset 义项记录 | 4,930 |
| 有用例的义项记录 / 用例记录 | 1,838 / 1,838 |
| 有同义词的词头 | 1,461 |
| 有同义词的义项 | 3,195 |

“用例”包括短语和完整句子，不能把 1,838 条一律称为完整例句。同一原始义项可对应不同拼写，因此记录数量也不等于不同句子的数量。全部精确计数与未命中词头见 JSON 的 `coverage`。

实际来源样例：

- `alleviate`：Octanove C1 动词；Wordset 提供 `Aspirin alleviates my headaches.` 和 `Running alleviates stress.`。
- `candid`：Octanove C1 形容词；Wordset 的一个用例是 `Their candid eyes encouraged discussion.`。
- `meticulous`：Octanove C2 形容词；两条 Wordset 用例是 `meticulous research`、`a meticulous craftsman`，均为短语。
- `resilient`、`concur`：源资料有等级和定义，但该固定版本 Wordset 没有提供用例，应明确显示缺失。

## 数据结构

```json
{
  "word": "alleviate",
  "cefr": [
    {"level": "C1", "pos": "verb", "notes": "", "source": "octanove"}
  ],
  "senses": [
    {
      "id": "9d70f76524",
      "definition": "to provide physical relief, as from pain",
      "pos": "verb",
      "examples": ["Aspirin alleviates my headaches."],
      "synonyms": ["relieve"],
      "source": "wordset",
      "wordset_word": "alleviate"
    }
  ]
}
```

以上只展示 `alleviate` 的一个义项；完整词条包含全部命中义项。`source` 标识对应顶层 `sources` 的来源、固定版本和许可信息。该数据结构没有给 Wordset 单个义项添加 CEFR 标签，也不声称完成语境消歧。

`synonyms` 保留 Wordset 在同一个义项中列出的词，去除完全重复值和自身引用；没有则为 `[]`。近义参考不表示任何语境都能直接替换，也不意味着同义词具有相同 CEFR 等级。不同义项的同义词分别保存，不跨义项拼接。

## 固定版本与校验

数据于 2026 年 10 月 26 日按以下固定来源构建；重建结果不写入动态时间戳，可重复产生相同字节。

| 资料 | 固定版本 | SHA-256 |
| --- | --- | --- |
| Octanove 原始 CSV | `d4e45b75b38f27b30dfc5c44d8c571aec7e7092f` | `18c33a407f2f89f7b8de9671c6d45fe3ea0bce45e7d2d7dcaab48d73e0f7b380` |
| Wordset 完整来源 ZIP | `4503bfafbe4556361a296b9d368c18168dfb56c3` | `59f47028b505832aae5c8d1c8ae9663a3c037888bf470104e97dafa7064db129` |

生成文件的校验值见 `lexiscope_dictionary.sha256`。构建器同时更新该文件。Wordset ZIP 为 17,420,328 字节，展开总量 67,312,828 字节；完整 Wordset 源词头为 108,133 个，而本地个人词典只打包 Octanove 对应子集。

`downloads/LexiScope-personal-dictionary.zip` 是独立数据包，附带 JSON、校验值和来源许可，不包含网站程序。重新构建 JSON 后，可在完整项目根目录运行 `python tools/package_personal_dictionary.py` 更新该数据包。

从项目根目录重新构建：

```bash
python tools/build_personal_dictionary.py
```

首次会通过正常验证 TLS 的 HTTPS 下载固定 Wordset ZIP，默认缓存到被 Git 忽略的 `dictionaries-local/wordset-source/`。下载上限100MiB，归档展开上限250MiB，并校验固定摘要；不执行来源项目的代码。已有缓存校验失败时会停止，不会修改预期摘要来绕过检查。

复用已下载的固定版本归档：

```bash
python tools/build_personal_dictionary.py --wordset-archive /path/to/wordset.zip
```

`--output` 可指定生成 JSON 路径；对应 `.sha256` 文件会写到同目录。`--license-dir` 可指定来源声明输出目录。

## 来源、署名与再利用

- **Octanove Labs / Open Language Profiles**：[原始词表](https://github.com/openlanguageprofiles/olp-en-cefrj/blob/d4e45b75b38f27b30dfc5c44d8c571aec7e7092f/octanove-vocabulary-profile-c1c2-1.0.csv)，采用 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)。原始来源说明、上游 README 和完整许可见本目录 `SOURCES.md`、`UPSTREAM_README.md`、`CC-BY-SA-4.0.txt`。
- **Wordset, Inc. 及其贡献者**：[固定版本](https://github.com/wordset/wordset-dictionary/tree/4503bfafbe4556361a296b9d368c18168dfb56c3)，采用 CC BY-SA 4.0，继承的 **WordNet 3.0 © 2006 Princeton University** 内容同时保留其许可要求。原始声明完整保存在 `wordset/LICENSE`；原始 README 在 `wordset/README.md`；原始声明中的 Princeton 部分另存为 `wordset/PRINCETON_WORDNET_LICENSE.txt`，便于阅读。

本项目的组合、选择、结构整理、去重和拼写连接属于对来源数据的加工，记录在 JSON 的 `modifications`。组合数据按 CC BY-SA 4.0 共享，并保留底层 Princeton WordNet 许可和免责声明。JSON 顶层 `notices.wordset` 同时内嵌原始 Wordset LICENSE 全文，包含 Princeton WordNet 的版权、许可和免责声明，确保单独下载或分享 JSON 时也随副本保留。分发个人词典时，应把上述来源、许可及改动说明一并保留；不能将组合结果视为对原始数据的独占所有权。此数据许可说明不改变应用源代码或其他独立资料的权利归属。
