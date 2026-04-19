# 结果质量审计与修复 · 设计文档

**日期**：2026-04-19
**截止**：2026-04-24 16:00（提交日）
**范围**：`result_2.xlsx`（70 题）+ `result_3.xlsx`（80 题）+ `result/*.jpg`（~133 张）

## 目标

在 5 天内将两份结果文件与图表集的**机械错误归零**，**叙述质量达到"无明显幻觉"**。

不在本期目标内：答案的深度分析增强、论文追加实验图、打包 `程序.zip`。

## 非目标

- 人工逐题审核 UI 面板（用户已授权"都由我处理"，面板成本不划算）
- 重建 ETL 或重训 LLM prompt
- 追求"满分"—— 本期只兜底下限

## 输入

- `result_2.xlsx` / `result_3.xlsx`（当前版本）
- `result/*.jpg`（当前 133 张）
- `data/db/finance.db`（SQLite）
- `.openviking/viking/default/resources/*/*.md`（研报 chunk，用于 reference 原文回溯）
- `data/sample/示例数据/附件5：研报数据/`（本地有全量 PDF，Railway 没有）

## 交付物

1. `scripts/audit_results.py` — 可重复运行的审计脚本
2. `scripts/regen_charts.py --all` 的补丁（若当前实现不支持全量重跑）
3. `scripts/fix_audit_findings.py` — 基于 audit 报告的自动/半自动修复
4. `paper/audit_report.md` — 最终审计输出（仅内部复核用，不对外提交）
5. 清洁后的 `result_2.xlsx` / `result_3.xlsx` / `result/*.jpg`

## 核心流程

```
                    ┌───────────────────────┐
                    │ scripts/audit_results │
                    └───────────┬───────────┘
                                ▼
                    ┌───────────────────────┐
                    │  audit_report.md      │   分三档：
                    │  blocking/suspect/hint │   blocking / suspect / hint
                    └───────────┬───────────┘
                                ▼
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
     ┌────────────┐    ┌────────────┐    ┌───────────────┐
     │ regen      │    │ fix_audit  │    │ LLM-as-judge  │
     │ _charts    │    │ _findings  │    │ narrative     │
     └────────────┘    └────────────┘    └───────────────┘
             │                  │                  │
             └──────────────────┼──────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │ re-run audit_results  │
                    │ (expect blocking=0)   │
                    └───────────────────────┘
```

## 组件设计

### 1. `scripts/audit_results.py`

**输入**：xlsx 路径、db 路径、可选 `--task {2|3|both}`。
**输出**：`paper/audit_report.md`，Markdown 格式，按题号汇总。

**检查项**（按严重度分档）：

| 档位 | 检查 | 数据源 |
| :-- | :-- | :-- |
| blocking | content 提到的数字（正则抽取带单位的数）必须落在 SQL 结果的数值集合附近（±1%） | xlsx + SQLite |
| blocking | 图表文件存在、非 0 字节、宽高 ≥ 400×300 | filesystem |
| suspect | references.paper_path 真实存在（相对 repo 根） | filesystem |
| suspect | references.text 能在对应 OV resource 的 .md chunk 中找到 ≥5 词连续匹配 | OV resources |
| suspect | chart 标签 bbox 重叠（利用 matplotlib 测量不现实；改为：n ≥ 10 且 chart_type=bar 时给出提示） | chart metadata |
| hint | content 长度 < 30 字 | xlsx |
| hint | task-3 题无 references 但路由判为 RAG/Hybrid | xlsx |

**Block 严重度策略**：blocking 必须修复；suspect 报告后可人工决定是否忽略；hint 仅供参考。

**实现关键点**：
- 数字提取使用 `re` 匹配 `([0-9]+(?:\.[0-9]+)?)\s*(亿|万|元|%)?`；
- SQL 结果数值集合由当前 xlsx 的 `SQL查询语句` 列重新执行获取；
- reference 路径规范化：剥离 `viking://` 前缀后的相对路径；
- 输出 Markdown 章节顺序：blocking 全部、suspect 全部、hint 摘要。

### 2. `scripts/regen_charts.py --all`

现有脚本在单题模式已验证（`B2014_2.jpg` / `B2059_1.jpg` 等）；本期只需新增 `--all` 分支：遍历 xlsx 的所有 `图形格式 != 无` 行，按 `{编号}_{顺序}.jpg` 命名覆盖写。

安全保证：写临时文件后原子替换，避免脚本中断污染。

### 3. `scripts/fix_audit_findings.py`

读取 `audit_report.md`，按行动类型分派：

- `rewrite_content(row_id)` — 重调 LLM 基于当前 SQL 结果 + refs 生成新 `content`，只替换 xlsx 的回答列。
- `clean_refs(row_id)` — 删除 paper_path 不存在或 text 无法匹配的 reference 条目。
- `reanswer(row_id)` — 整行重跑（仅 blocking 项使用）。

所有修改写入新 xlsx `.audited` 副本，原文件保留为备份，确认后改名。

### 4. `llm_judge_narrative()`（嵌入在 `audit_results.py`）

- 触发条件：task-3 中 intent ∈ {multi_intent, hybrid} 的题（约 30 道）。
- Prompt：给 LLM "问题 + content + references text"，输出 0-3 分（0=偏题/幻觉、3=切题且有数据支撑），附简评。
- 分数 ≤ 1 → 记入 blocking（标记 `narrative_too_weak`）。

### 5. 最终校验

重跑 `audit_results.py`，期望 `blocking == 0`；否则迭代修复。

## 错误处理

- LLM 调用失败：重试 3 次，仍失败则该题 content 保留原样，标记 `llm_rewrite_failed` 归 suspect。
- SQL 执行失败：blocking，该题直接 reanswer。
- Chart 重生成失败：blocking，保留原图并在 audit_report 标记。

## 测试策略

- 单元测试：`tests/test_audit.py` 覆盖数字提取、reference 路径规范化、LLM 判分 stub。
- 集成测试：在小样本（3 道题的迷你 xlsx）上端到端跑一遍 audit → fix → re-audit，验证 blocking 能下降到 0。
- 回归保障：现有 14 个 pytest 文件全部通过。

## 时间预算

| 阶段 | 预估 |
| :-- | :-- |
| `audit_results.py` 开发 + 单元测试 | 1 小时 |
| `regen_charts.py --all` 补丁 | 15 分钟 |
| `fix_audit_findings.py` 开发 | 1 小时 |
| LLM-as-judge 批量调用（30 道 × ~5s） | 10 分钟 |
| 第一轮审计 + 修复 + 重审 | 1.5 小时 |
| 人工抽检 + 收尾 | 30 分钟 |
| **合计** | **~4.5 小时** |

## 风险

- **LLM 漂移**：重写 content 可能引入新幻觉。缓解：每次重写都强制 LLM 引用给定数字；重写后再次跑数字一致性检查。
- **正则抽数假阳**："3140 万元" vs "约 3140 万元"、"超 3000 万元" 等粗略表述会在数字集合中匹配不到 SQL 结果。缓解：阈值设 ±1%，单题允许 ≤1 个数字未匹配。
- **LLM-as-judge 不稳定**：同一答案两次评分可能差 1 分。缓解：评分 ≤ 1 才视为 blocking，中间分数不动。

## 决策点（已确认）

- 不做审核 UI 面板。
- 审计 report 不需要评委可见，仅内部复核用。
- 不重新训练或切换 LLM，沿用当前 156.233 / oai.whidsm 两个 endpoint 做容灾。
