# 前列腺癌＋淋巴结转移＋放疗：文献笔记网站

在线阅读：[文献笔记库](https://cindy151629.github.io/prostate-node-rt-library/)。首次云端完整联网运行和HTTPS部署验证已成功，[实际运行记录](https://github.com/Cindy151629/prostate-node-rt-library/actions/runs/34832745993)。定时工作流已启用；截至2026-09-14尚未经历schedule事件，下一次预计北京时间2026-09-21 09:17。

直接打开 `public/index.html` 即可阅读。它是内嵌全部笔记和题录的静态快照，断网也能搜索、组合筛选和查看详情；文件不会自行取得新的文献。云端更新后重新访问网站可读新版本。若已配置云端回执，页面额外读取公开运行状态；读取失败不影响笔记。

## 内容与证据边界

从用户提供的 DOCX 实际解析151个唯一条目，在不限年份的 PubMed/Europe PMC 检索中补充24篇，当前175篇均有具体中文内容笔记。数量从数据计算；不是独立试验数，也不是文献覆盖率。各篇包含研究问题、设计/人群/干预、结果、局限、来源定位和四项核验。172篇依据摘要，2篇依据取得的指定正文段落，1篇依据出版社公开节选。取得正文与完成全文精读是不同状态，均未标为人工医学复核。

七板块按临床情境整理；混合N0/N1、骨/结转移、非区域M1a、非随机RT比较及仅方案报告在笔记中限定解释。纯诊断、手术或N0预防照射不会凭命中关键词进入阅读库。候选题录独立存放，未经逐篇内容核验不自动产生中文结论。

基线检索PubMed1008、Europe PMC982个唯一记录，共享MED记录952；共有1058个检索登记记录。两库共享MEDLINE，不能据此宣称独立验证或100%收齐。当前846条普通/优先待筛及3条更正候选未计入175篇阅读笔记；35条规则排除可复核。仅DOI起始条目另由Crossref/出版社确认，所以不能简单用1058减175解释所有队列。

未接入Embase、Web of Science、知网和万方。初始目录3篇作者字段有冲突，另有摘要内部统计/人群表述疑点，网页“笔记待核验项”提供具体原因。403/429及登录页只标访问受限或未确认，不删文章。Crossref版本检查每轮12篇轮转，空关系不代表无更正/撤稿；PubMed原生更正关联与摘要每轮复查阅读库。

## 本地运行（Python 3.12以上，标准库）

在本项目目录执行：

```bash
python3 scripts/update.py --mode history
python3 scripts/update.py --mode weekly --replay
python3 -m unittest discover -s tests -v
python3 scripts/build.py
python3 -m http.server 8769 --bind 127.0.0.1 --directory public
```

访问 http://127.0.0.1:8769/ 。`--replay`重复上一次本机联网输入，必须先联网运行；原始缓存、摘要、正文和冻结输入不进入发布包。HTTPS证书错误应使用正确的Python证书环境，不能关闭TLS验证。

`auto`：每月首次运行做历史检索，其余按日期增量；`history`不限发表年份；`weekly`从各库上次持久化进度向前重叠90天（长期中断也补足窗口）。PubMed分别使用PDAT、EDAT、MDAT、CRDT，Europe PMC使用FIRST_PDATE、FIRST_IDATE、UPDATE_DATE；调用接口检查实际支持字段。每库独立失败，每页去重并核对命中总数。PubMed单分支达到10000条将明确失败，需要拆分日期查询后再运行，不会把截断当成功。

## 云端部署和定时任务

配置文件 `.github/workflows/weekly.yml` 在GitHub托管运行器上执行，电脑关机、Codex离线也可工作。默认每周一北京时间09:17（UTC 01:17）。日程非准点承诺；首次手动成功也不等于已观察到schedule事件。

首次部署：将本发布项目放入目标仓库**默认分支**，仓库 Settings → Pages → Build and deployment → Source 选择 **GitHub Actions**；允许Actions运行，并允许工作流写入仓库。Actions → **Weekly literature update** → **Run workflow**。默认分支含工作流才会接收schedule；工作流显式检出默认分支。当前不以普通push触发部署，编辑代码/笔记后手动运行。

流程：恢复data分支状态 → 测试 → 检索/元数据/去重/初筛/全文轮查/版本轮查 → 写候选 → 校验 → 原子快照 → 持久化data分支 → Pages部署 → 获取真实HTTPS页面及manifest → 比对数据哈希、HTML哈希、笔记总数 → 写发布回执。只有最后验证成功才推进最近发布；只有主来源完整且验证成功才推进最近完整成功。

主分支保存代码、查询及人工笔记。自动任务仅提交data分支，不覆盖主分支人工文件。data分支保存查询进度、当前/上一有效快照、运行记录和发布回执。网页从该分支读取公开回执，所以失败无需重新发布阅读页也能更新状态。源码、数据和中文笔记公开发布；出版社PDF、JATS正文、原始摘要和访问缓存不随包上传。

调时：同时修改工作流cron与`config/search.json`的`schedule_utc`，后者用于网页显示预计下次时间。调词：修改该JSON的`queries`，分别维护两库语法，并变更`query_version`，随后手动选择`history`核对命中变化。调窗口：`lookback_days`；调全文/版本轮查量：`fulltext_checks_per_run`和`version_checks_per_run`。

GitHub可能延迟或丢弃高负载排队任务；公开仓库连续60天无活动可能停用定时工作流。页面默认超过9天未完整成功提示过期；若从未成功，会显示未完成云端验收。恢复时在Actions重新启用工作流并手动运行。以[GitHub官方说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)为准；[NCBI接口日期/分页说明](https://www.ncbi.nlm.nih.gov/books/NBK25499/)。

## 手动维护与恢复

- 增量更新：Actions → Run workflow → `weekly`；历史补漏选`history`；常规选`auto`。
- 重新部署有效快照：选`republish`，不抓取新来源，也不刷新来源完整更新的时间。
- 更正某篇：在`data/manual/overrides.json`以稳定ID写深层字段覆盖；详细笔记在`data/manual/notes.json`。`external_mappings`和`manual_annotations`按ID保留。自动任务不写上述文件。
- 新增阅读文章：`data/manual/additions.json`加入稳定ID/PMID/DOI和种子编号，`notes.json`同时加入来源明确的完整笔记。题录自动候选不等于已完成阅读。
- 来源失败或分页不完整：记录部分成功/失败，失败来源不推进水位；其他完整来源可持久化；重跑自动补查。
- 候选损坏：拒绝切换当前快照和水位；构建/部署失败保留先前线上页面。来源进度已安全持久化但部署失败时，可用`republish`恢复发布。
- 回滚数据：从data分支已知有效提交恢复`state/current.json`及同提交的library/registry/state等文件，提交后选择`republish`。不要仅更改网页未读取的旁路JSON。
- 查看日志：网页“检索与维护”、Actions日志和90天保留的运行工件；更长期日志在data分支提交历史中。主阅读页只显示简要状态。

## 文件与验收

`data/current.json`是权威快照；`data/library.json`和`registry.json`为派生文件。`public/index.html`嵌入权威数据，`public/manifest.json`用于验证真正上线版本。`data/reports/acceptance.json`记录本地实际验收，`data/deployment-verification.json`仅在实际GET核验后生成，`data/publication-status.json`记录云端发布结果。`data/runs/`保存完整分支查询、日期、抓取量、去重差异、排除和失败信息。

已实际运行不限年份完整更新、日期增量及冻结输入重放；浏览器覆盖全部175篇详情、桌面/移动端、离线HTML、全局搜索、组合筛选与稳定链接。故障测试覆盖来源失败、部分成功、分页不完整、HTTP200登录页、元数据冲突、损坏候选、人工校正保护及禁止未核验发布冒充成功。实际部署/定时状态以发布回执和验收记录为准。
