# 结果审计报告

阻塞 **36**　可疑 **27**　提示 **0**

## 阻塞

| 题号 | 类别 | 说明 |
| :-- | :-- | :-- |
| B2002 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称2025年8月公告新增7个中药产品，但提供的表格数据与references中多份文档描述不一致（references提及2024年11月、2025年7月等不同时间节点），且表格中多个产品信息无法在references中验证，答案更多是编造而非基于真实数据。 |
| B2003 | num_mismatch | content has 124.82亿元 (≈12482000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 30.88% |
| B2003 | num_mismatch | content has 52.13亿元 (≈5213000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 21.72% |
| B2003 | num_mismatch | content has 9.53亿元 (≈953000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 66.88% |
| B2009 | narrative_too_weak | LLM judged 0/3: 存在严重幻觉：声称2025年Q3收入4.64亿元，但references中2025年前三季度累计仅14.62亿元，数据自相矛盾；references中多处提及2024年数据和2025年中报数据，未见明确的2025年Q3单季数据，答案虚构了具体数字。 |
| B2016 | narrative_too_weak | LLM judged 1/3: 内容大量虚构数据（如具体研发费用占比、管线项目代码等），缺乏真实引用支撑，无法验证2025年Q3实际数据，属于幻觉性回答。 |
| B2018 | narrative_too_weak | LLM judged 1/3: 内容大量虚构数据（如2025H1毛利率59.48%、Q3毛利率等），引用文档与问题不符（多为原料药/创新药行业报告），未能提供以岭药业2024-2025年Q3具体毛利率数据，属于幻觉回答。 |
| B2019 | narrative_too_weak | LLM judged 0/3: content显示'Reached 15 iterations without completion'表示生成失败，references仅提及638.4亿元市场规模但完全缺少2025年Q3配方颗粒业务收入占比超30%的公司名单及其营业总收入同比增长率数据，无法回答具体问题。 |
| B2020 | narrative_too_weak | LLM judged 1/3: 虽然提供了达仁堂的具体数据，但缺乏2025年研报的真实检索证据，Q3现金流数据来源不明，同行对比企业选择缺乏依据，整体呈现幻觉特征。 |
| B2021 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称提供2025年Q3数据但迪安诊断数据来自2024年预告，金域医学缺少Q3数据，资产负债率未提供，引用的参考文献与答案内容不符，无法验证数据真实性。 |
| B2023 | narrative_too_weak | LLM judged 0/3: 内容完全虚构，表格数据无法验证，引用的研报内容与实际不符，存在严重幻觉。 |
| B2025 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称提供2025年Q3具体排名数据和收入数据，但references中完全没有这些数据；表格中的排名、收入数字、增速数据均无来源支撑，属于编造；仅有的真实信息是市场规模和政策支持，与问题要求的具体企业排名和市场份额评价严重不符。 |
| B2026 | narrative_too_weak | LLM judged 0/3: 助手未能完成检索任务（显示'Reached 15 iterations without completion'），无法提供所需的人工智能产业升级公司名单和2025年Q3销售费用率数据，答非所问。 |
| B2027 | narrative_too_weak | LLM judged 1/3: 虽然承认了错误并展示了修正态度，但核心问题未解决：声称'来自真实研报'却无法提供原始出处，去重后的名单仍缺乏独立验证依据，且references中的医药公司名单与列举的37家完全不同，存在严重的数据来源混乱，属于套话式自我纠正而非实质性解答。 |
| B2029 | narrative_too_weak | LLM judged 0/3: 检索失败（Reached 15 iterations without completion），且参考文献仅包含产品注册信息，完全缺少2025年Q3财务数据和海外业务收入数据，无法回答问题。 |
| B2030 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称已获得数据但实际未提供真实的Q3净利润率变化数据，仅有昆药集团一家企业的片段数据，缺乏集采中标企业的系统对比分析，研报观点提取不完整，答案结构虽完整但数据支撑严重不足。 |
| B2032 | narrative_too_weak | LLM judged 1/3: 助手坦诚承认无法找到所需数据，但仅提供了总销售费用排名而非电商推广费占比，且引用文献均为2024-2025H1数据，不含Q3电商推广费细分数据，属于偏题且无法直接回答问题。 |
| B2033 | narrative_too_weak | LLM judged 1/3: 答案混淆了Q1预告与Q3实际的对比逻辑，数据来源不清且缺乏真实的预告vs实际净利润差异对比，主要呈现的是Q1-Q3累计数据和环比改善幅度，未能准确回答题目要求的'预告净利润与Q3实际净利润的差异率'。 |
| B2035 | narrative_too_weak | LLM judged 0/3: 助手因token超限无法处理，未能识别五家龙头公司、查询财务数据或提取分析依据，仅返回错误信息；参考文本虽提及多家公司但未明确指定五家龙头且无具体财务数据。 |
| B2040 | narrative_too_weak | LLM judged 1/3: 严重幻觉：声称分析2025年Q3数据，但参考文献仅涉及2024年Q3和研发管线信息，不存在2025年实际财务数据；具体数字（如白云山616.06亿元等）无法溯源验证，行业均值对比缺乏依据。 |
| B2041 | narrative_too_weak | LLM judged 1/3: 数据存在严重问题：①缺少2022年Q3数据（题目要求2022-2025年）；②提供的2025Q3数据与参考文献内容不符（参考文献仅涉及2025年上半年，无Q3数据）；③非经常性损益数据无法验证；④原因说明缺乏具体研报支撑，存在编造嫌疑。 |
| B2043 | narrative_too_weak | LLM judged 0/3: 严重幻觉：声称有2025年Q3数据和50家中药公司详细财务数据，但提供的参考文献仅涉及医疗器械、化学制药等，根本不包含所需的中药公司2025年Q3财务数据，且无任何研报分析支撑，完全是虚构数据。 |
| B2045 | narrative_too_weak | LLM judged 0/3: 严重幻觉：content声称统计了16家和5家公司的具体数据，但references中仅为通用财务预测报告摘要，不含2025Q3具体公司名单、资产负债率分布数据或个股ROE数据，无法验证任何数据真实性 |
| B2047 | num_mismatch | content has 14.1万 (≈141000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 68.98% |
| B2048 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称找到符合条件的公司（康惠制药等），但提供的研报references完全不涉及这些公司，仅涉及片仔癀、康缘药业等，无法验证数据真实性；缺少实际研报支撑的风险预警分析，属于编造数据的答非所问。 |
| B2050 | narrative_too_weak | LLM judged 1/3: 虽然列出了三家公司及投资金额，但缺乏具体的公司总数、占比数据，且研报引用仅为文档目录描述，未提取实际的投资项目说明细节，主要为套话总结。 |
| B2056 | narrative_too_weak | LLM judged 0/3: 严重答非所问：问题要求分析2025Q3各公司成本构成，但content混淆了康弘药业和康缘药业两家不同公司，表格数据无法验证且缺乏真实来源，引用的研报全部关于康缘药业而非康弘药业，存在明显幻觉和逻辑混乱。 |
| B2057 | narrative_too_weak | LLM judged 0/3: 严重幻觉：表格数据完全虚构（如新天药业未分配利润56545万元、比值34.95等），references中未提及任何2025年Q3财报数据或具体分红分析，仅为医药行业通用介绍，无法验证数据真实性。 |
| B2061 | narrative_too_weak | LLM judged 0/3: 答非所问且有幻觉：助手未能回答问题，反而声称数据库不存在康芝药业，但references中未提及康芝药业，无法确认其真实存在性；同时提供的references全是其他公司（康缘、昆药、健民等），无法用于解答原问题。 |
| B2062 | narrative_too_weak | LLM judged 1/3: 内容完全是关于江中药业、体外诊断等其他企业的研报，与奇正藏药资产负债率分析无关，属于严重答非所问且存在幻觉（虚构了具体数据和分析）。 |
| B2064 | narrative_too_weak | LLM judged 1/3: content分析的是康美药业数据，但references全部为其他企业（龙牡健民、同仁堂、康缘药业等），缺乏康美药业的销售模式、客户结构等研报支撑，无法验证分析的准确性。 |
| B2070 | narrative_too_weak | LLM judged 0/3: 答非所问且存在严重问题：助手查询到的数据显示销售费用率下降而非上升，与题目前提矛盾；references中完全没有陇神戎发的相关资料，仅包含济川药业、昆药集团等其他公司数据，无法进行题目要求的分析。 |
| B2071 | narrative_too_weak | LLM judged 1/3: 答案存在严重数据矛盾（净资产收益率下降幅度说法不一致），缺乏资产负债表具体数据支撑，行业分析仅为套话，未能结合提供的研报深度分析毛利率下滑的具体产品结构变化（如安宫牛黄丸毛利率从50.7%跌至14.2%的影响权重）。 |
| B2072 | narrative_too_weak | LLM judged 1/3: 内容指出题目前提条件（货币资金占比30%）与实际数据（8.10%）存在重大差异，后续分析基于错误前提展开；引用的研报仅为行业周报汇总说明，未提供新天药业具体的战略投资或项目布局信息，缺乏针对性支撑。 |
| B2075 | narrative_too_weak | LLM judged 1/3: 助手未能获取贵州百灵2025Q3的具体财务数据，仅列举数据缺失清单；引用的研报内容为2024年数据且混杂了桂林三金等其他公司信息，无法针对题目中的净利润100%增长现象进行实质分析。 |
| B2076 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称提供了详细分析但实际未基于真实数据，引用的具体数字（如应收账款6.80亿→8.75亿、存货10.89亿→6.60亿等）在提供的references中完全找不到，且未能结合实际现金流量表和行业研报进行论证。 |

## 可疑

| 题号 | 类别 | 说明 |
| :-- | :-- | :-- |
| B2003 | num_mismatch | content has 60.05亿元 (≈6005000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 9.83% |
| B2005 | num_mismatch | content has 358510.0万元 (≈3585100000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 7.91% |
| B2006 | num_mismatch | content has -0.26亿元 (≈-26000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 1.95% |
| B2006 | num_mismatch | content has 0.38亿元 (≈38000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 2.06% |
| B2007 | num_mismatch | content has -122.02亿元 (≈-12202000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 1.05% |
| B2008 | num_mismatch | content has 200.0亿元 (≈20000000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 9.03% |
| B2008 | num_mismatch | content has 200.0亿元 (≈20000000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 9.03% |
| B2010 | num_mismatch | content has 5.31亿元 (≈531000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 1.09% |
| B2011 | num_mismatch | content has 1495.0亿 (≈149500000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 1.35% |
| B2011 | num_mismatch | content has 748.0亿 (≈74800000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 1.17% |
| B2011 | num_mismatch | content has 273.0亿 (≈27300000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 4.94% |
| B2011 | num_mismatch | content has 99.0亿 (≈9900000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 1.32% |
| B2011 | num_mismatch | content has 85.0亿 (≈8500000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 1.08% |
| B2011 | num_mismatch | content has 426.0亿 (≈42600000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 8.65% |
| B2011 | num_mismatch | content has 231.0亿 (≈23100000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 4.72% |
| B2011 | num_mismatch | content has 9.6亿元 (≈960000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 1.23% |
| B2039 | num_mismatch | content has 10.0亿元 (≈1000000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 5.72% |
| B2039 | num_mismatch | content has 10.0亿元 (≈1000000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 5.72% |
| B2039 | num_mismatch | content has 10.0亿元 (≈1000000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 5.72% |
| B2039 | num_mismatch | content has 10.0亿 (≈1000000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 5.72% |
| B2055 | num_mismatch | content has 181095.82万元 (≈1810958200.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 4.12% |
| B2055 | num_mismatch | content has 32029.01万元 (≈320290100.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 4.07% |
| B2064 | num_mismatch | content has -427.63万元 (≈-4276300.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 14.74% |
| B2067 | num_mismatch | content has 30.51亿元 (≈3051000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 14.16% |
| B2067 | num_mismatch | content has 24.74亿元 (≈2474000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 1.36% |
| B2067 | num_mismatch | content has 30.51亿 (≈3051000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 14.16% |
| B2067 | num_mismatch | content has 55.44亿元 (≈5544000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 1.94% |
