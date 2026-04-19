# 结果审计报告

阻塞 **39**　可疑 **122**　提示 **0**

## 阻塞

| 题号 | 类别 | 说明 |
| :-- | :-- | :-- |
| B2002 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称2025年8月公告、列举的7个产品及具体数据（价格、企业等）无法验证，表格信息与references中提及的2024年11月医保目录调整时间不符，且多个references内容相互矛盾，整体缺乏可靠的数据支撑。 |
| B2003 | num_mismatch | content has 124.82亿元 (≈12482000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 30.88% |
| B2003 | num_mismatch | content has 52.13亿元 (≈5213000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 21.72% |
| B2003 | num_mismatch | content has 9.53亿元 (≈953000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 66.88% |
| B2009 | narrative_too_weak | LLM judged 0/3: 存在严重幻觉：声称2025年Q3收入4.64亿元，但references中2025年前三季度累计仅14.62亿元的数据自相矛盾；references多处提及2024年数据和中报数据，未能清晰确认2025年Q3具体数字，答案缺乏可靠依据。 |
| B2016 | narrative_too_weak | LLM judged 1/3: 内容大量虚构数据（如具体研发费用占比、管线进展等），与提供的references完全不符，存在严重幻觉；虽涉及政策背景但缺乏真实的2025年Q3财务数据和研报引用支撑。 |
| B2017 | narrative_too_weak | LLM judged 1/3: 内容为套话和虚构数据，未能从实际研报中筛选出具体的'强烈推荐'中药公司名单，Q3净利润数据与references中的2024年Q3数据混淆，缺乏真实的数据支撑和具体对比分析。 |
| B2018 | narrative_too_weak | LLM judged 1/3: 内容大量虚构数据（如2025H1毛利率59.48%、Q3毛利率等），引用文档与问题不符（多为原料药/创新药行业报告），未能提供以岭药业2024-2025年Q3具体毛利率数据，属于幻觉回答。 |
| B2020 | narrative_too_weak | LLM judged 1/3: 虽然提供了达仁堂的Q3现金流数据，但缺乏2025年研报的真实检索证据，对比企业选择不当（同仁堂、云南白药、片仔癀均未证实有海外拓展提及），数据来源不透明，存在虚构成分。 |
| B2021 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：迪安诊断和金域医学的具体Q3 2025财务数据（如资产负债率）未实际查询，仅凭推测编造；引用的研报内容与references中的实际文档内容不符，答案套用行业模板而非基于真实个股研报。 |
| B2023 | narrative_too_weak | LLM judged 0/3: 内容完全虚构，表格数据无法验证，引用的研报内容与实际不符，存在严重幻觉。 |
| B2025 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称提供2025年Q3具体排名数据和收入数据，但references中完全没有这些数据；表格中的排名、收入数字、增速数据均无来源支撑，属于编造；仅有的真实信息是市场规模和政策支持，不符合题目要求的具体排名和市场份额评价。 |
| B2026 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称提供了具体的2025年Q3销售费用率数据（华润三九、同仁堂等），但references中的文档均为2025年2月-8月的研报，不可能包含Q3（7-9月）的实际财务数据；表格数据无法溯源，与提供的参考文献内容不符。 |
| B2027 | narrative_too_weak | LLM judged 1/3: 虽然承认了错误并展示了修正态度，但核心问题未解决：声称'来自真实研报'却无法提供原始出处，列举的公司名单与references中的医药股名单完全不匹配（资产重组vs投资分析），判断依据仍然缺失，实质上是在用'去重'掩盖数据来源不明的问题。 |
| B2029 | narrative_too_weak | LLM judged 1/3: 虽然识别出天士力获FDA认证，但未能从提供的研报中检索到2025年Q3海外业务收入数据，仅承认数据缺失，未能完成题目要求的核心查询任务。 |
| B2030 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称已获得数据但实际未提供真实的Q3净利润率变化数据，仅有昆药集团一家企业的片段数据，缺乏集采中标企业的系统对比分析，研报观点提取不完整，答案主要为政策梳理而非问题所需的财务数据分析。 |
| B2031 | narrative_too_weak | LLM judged 0/3: 内容完全是幻觉：声称提供了2025年Q3存货周转率数据和具体数值，但参考文献仅涉及2025年上半年数据，不存在Q3数据；表格中的数字无法在任何参考文献中验证，属于虚构数据。 |
| B2032 | narrative_too_weak | LLM judged 1/3: 助手坦诚承认无法找到所需数据，但仅提供了总销售费用排名而非电商推广费占比，且引用文献均为2024-2025H1数据，不含Q3电商推广费细分数据，属于无法切题回答。 |
| B2033 | narrative_too_weak | LLM judged 1/3: 内容混淆了Q1预告与Q3实际数据的对比逻辑，未能准确完成题目要求的'预告净利润与Q3实际净利润对比'，数据来源不清且存在幻觉成分（声称获取数据但缺乏具体预告数据），最后结论模糊且不符合题意。 |
| B2035 | narrative_too_weak | LLM judged 0/3: 助手因token超限无法处理，未能识别五家龙头公司、查询财务数据或提取分析依据，仅返回错误信息；references虽列举多家公司但缺乏具体的2022-2025Q3营业收入数据和龙头地位分析依据。 |
| B2040 | narrative_too_weak | LLM judged 1/3: 严重幻觉：声称分析2025年Q3数据，但参考文献仅涉及2024年Q3和研发管线信息，不存在2025年实际财务数据；具体数据（如白云山616.06亿元、行业均值等）无法溯源验证，属于虚构内容。 |
| B2041 | narrative_too_weak | LLM judged 1/3: 数据存在严重问题：①缺少2022年Q3数据（题目要求2022-2025年）；②提供的2025Q3数据与参考文献内容不符（参考文献仅涉及2025年上半年，无Q3数据）；③非经常性损益数据无法验证；④原因说明缺乏具体研报支撑，存在编造嫌疑。 |
| B2043 | narrative_too_weak | LLM judged 0/3: 严重幻觉：声称有2025年Q3数据和50家中药公司详细财务数据，但提供的参考文献仅涉及医疗器械、化学制药等，根本不包含所需的中药公司2025年Q3财务数据，且无法验证表格中的具体数字来源。 |
| B2045 | narrative_too_weak | LLM judged 0/3: 严重幻觉：content声称统计了16家和5家公司的具体数据，但references中仅为通用财务预测报告摘要，不含2025Q3具体公司名单、资产负债率分布数据或个股ROE数据，无法验证任何数据真实性。 |
| B2047 | num_mismatch | content has 14.1万 (≈141000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 68.98% |
| B2048 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称找到符合条件的公司（康惠制药等），但提供的研报references完全不涉及这些公司，仅包含康缘药业、片仔癀、健民集团等，无法验证数据真实性；缺少实际研报支撑的风险预警分析，属于编造数据的答非所问。 |
| B2050 | narrative_too_weak | LLM judged 1/3: 虽然列出了三家公司及投资金额，但缺乏具体的公司总数、占比数据，且研报引用仅为华润三九相关文档摘要，未能提取康弘药业和云南白药的研报说明，答案不完整且数据支撑不足。 |
| B2056 | narrative_too_weak | LLM judged 0/3: 严重答非所问：题目要求分析2025Q3各公司成本构成，但content混淆了康弘药业和康缘药业两家不同公司，表格数据无法验证且缺乏真实来源，引用的研报全部关于康缘药业而非康弘药业，存在明显幻觉和逻辑混乱。 |
| B2057 | narrative_too_weak | LLM judged 0/3: 严重幻觉：表格数据完全虚构（如新天药业未分配利润56545万元、比值34.95等），references中未提及任何2025年Q3财报数据或具体公司分红分析，仅为医药行业通用介绍，无法支撑表格内容，答非所问。 |
| B2060 | narrative_too_weak | LLM judged 1/3: 助手诚实说明无2025年Q3数据，但仅基于2024年Q3历史数据分析，未能获取题目所需的2025年Q3具体财务数据和个股研报，无法完成题目要求的同比分析和核心原因剖析，属于偏题。 |
| B2061 | narrative_too_weak | LLM judged 0/3: 答非所问且有幻觉：助手未能回答问题，反而声称数据库不存在康芝药业，但references中未提及康芝药业，无法确认其真实存在性；同时提供的references全是其他公司（康缘、昆药、健民等），无法用于解答原问题。 |
| B2062 | narrative_too_weak | LLM judged 1/3: 内容完全是关于江中药业、体外诊断等其他企业的研报，与奇正藏药资产负债率分析无关，属于严重答非所问且存在幻觉（虚构了具体数据和分析）。 |
| B2063 | narrative_too_weak | LLM judged 1/3: 数据存在严重矛盾（Q3毛利率同比提升25.98个百分点而非10个百分点），驱动因素分析缺乏具体数据支撑，引用的研报内容与题目要求的利润表细节分析不符，属于套话式回答。 |
| B2064 | narrative_too_weak | LLM judged 1/3: content分析的是康美药业数据，但references全部为其他企业（龙牡健民、同仁堂、康缘药业等），缺乏康美药业的销售模式、客户结构等研报支撑，无法验证论述的充分性。 |
| B2070 | narrative_too_weak | LLM judged 0/3: 答非所问且存在严重问题：助手查询到的数据显示销售费用率下降而非上升，与题目前提矛盾；references中完全没有陇神戎发的相关资料，仅有济川药业、昆药集团等其他公司数据，无法进行题目要求的分析。 |
| B2071 | narrative_too_weak | LLM judged 1/3: 答案存在严重数据矛盾（净资产收益率下降幅度说法不一致），缺乏资产负债表具体数据支撑，行业分析仅为套话，未能结合提供的研报深度分析毛利率下滑的具体产品结构变化。 |
| B2072 | narrative_too_weak | LLM judged 1/3: 内容指出题目前提条件（货币资金占比30%）与实际数据（8.10%）存在重大差异，后续分析基于错误前提展开；引用的研报仅为行业周报汇总说明，未提供新天药业具体的战略投资、项目布局等支撑信息，属于套话分析。 |
| B2075 | narrative_too_weak | LLM judged 1/3: 助手未能获取贵州百灵2025Q3的具体财务数据，仅列举数据缺失清单；引用的研报内容为2024年数据且混杂了桂林三金等其他公司信息，无法针对题目中的净利润100%增长现象进行实质分析。 |
| B2076 | narrative_too_weak | LLM judged 1/3: 内容存在严重幻觉：声称提供了详细分析但实际未基于真实数据，引用的具体数字（如应收账款6.80亿→8.75亿、存货10.89亿→6.60亿等）在提供的references中完全找不到，且未能结合现金流量表具体项目和行业研报进行实质性分析。 |

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
| B2019 | ref_path_missing | paper_path not found: './resources/2025年中国中药市场行业研究报告/2025年/2025年_7.md' |
| B2019 | ref_path_missing | paper_path not found: './resources/2025年中国中药市场行业研究报告/2025年/2025年_8.md' |
| B2019 | ref_path_missing | paper_path not found: './resources/中药行业深度报告链主企业带动云南省中药材产业链高质量发展/目录/目录/目录_1.md' |
| B2019 | ref_path_missing | paper_path not found: './resources/2025年中国中药市场行业研究报告/.abstract.md' |
| B2019 | ref_path_missing | paper_path not found: './resources/2025年中国中药市场行业研究报告/2025年中国中药市场行业研究报告_3caf49ed.md' |
| B2019 | ref_path_missing | paper_path not found: './resources/2025年中国中药市场行业研究报告/2025年/2025年_1.md' |
| B2019 | ref_path_missing | paper_path not found: './resources/中国智慧中医行业发展报告/二智慧中医产业发展环境分析/二智慧中医产业发展环境分析_3.md' |
| B2019 | ref_path_missing | paper_path not found: './resources/中药行业深度报告链主企业带动云南省中药材产业链高质量发展/目录/目录/目录_2.md' |
| B2019 | ref_path_missing | paper_path not found: './resources/2025年中国中药行业市场研究报告/.abstract.md' |
| B2019 | ref_path_missing | paper_path not found: './resources/医药生物行业周报原发性头痛用中成药市场待开发关注NDA新品/原发性头痛用中成药市场待开发关注新品NDA医药生物/紧张型头痛为我国最常见的原发性头痛其次为偏头痛_1/紧张型头痛为我国最常见的原发性头痛其次为偏头痛_1_3.md' |
| B2019 | ref_path_missing | paper_path not found: 'viking://user/default/memories/.abstract.md' |
| B2019 | ref_path_missing | paper_path not found: 'viking://user/default/memories/preferences/.abstract.md' |
| B2019 | ref_path_missing | paper_path not found: 'viking://session/.abstract.md' |
| B2019 | ref_path_missing | paper_path not found: 'viking://user/default/memories/entities/.abstract.md' |
| B2019 | ref_path_missing | paper_path not found: 'viking://user/default/memories/events/.overview.md' |
| B2026 | num_mismatch | content has 4910.0亿 (≈491000000000.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 13.00% |
| B2026 | num_mismatch | content has 3.58万 (≈35800.00 元); closest SQL value (incl. pairwise ± combos, 元/万/亿 scales) is off by 4.07% |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业跟踪周报AI医疗仍被显著低估关注华大智造晶泰控股-P等/控股等-P/增持维持/医疗仍被显著低估关注华大智造晶泰控股等_1_AI-P/医疗仍被显著低估关注华大智造晶泰控股等_1_AI-P/医疗仍被显著低估关注华大智造晶泰控股等_1_AI-P_5.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业报告基因测序仪行业格局迎巨变国产替代有望提速/2_一周观点本周医药板块上涨106行业迎反转机会/21_本周医药生物上涨106体外诊断板块涨幅最大/21_本周医药生物上涨106体外诊断板块涨幅最大_2.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业周报中报业绩边际改善创新药及配套产业链表现亮眼/2025年8月31日/2025年8月31日_1.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业周报业绩边际回暖并购重组提速持续看好2025年科研服务板块机会/研服务板块机会/研服务板块机会/研服务板块机会_3.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药行业周报AI医疗主题投资持续发酵/医疗主题投资持续发酵AI/医疗主题投资持续发酵AI/医疗主题投资持续发酵AI_4.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业周报医药数智化转型方案发布加快中医药产业升级步伐/医药生物行业周报医药数智化转型方案发布加快中医药产业升级步伐_1.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业周报医疗AI持续火热建议关注三大应用方向/1医药行业周观点/1医药行业周观点_2.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业周报AI破局医药板块/AI破局医药板块/AI破局医药板块/AI破局医药板块_1.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物周报24年第17周ASCO摘要标题整理25Q1公募基金医药持仓分析/图表目录/投资策略.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物周报25年第18周2024年及2025一季度A股生物医药行业财报总结/图表目录/板块估值情况.md' |
| B2026 | ref_path_missing | paper_path not found: 'viking://user/default/memories/entities/.overview.md' |
| B2026 | ref_path_missing | paper_path not found: 'viking://user/default/memories/preferences/.overview.md' |
| B2026 | ref_path_missing | paper_path not found: 'viking://user/default/memories/.abstract.md' |
| B2026 | ref_path_missing | paper_path not found: 'viking://user/default/memories/events/.overview.md' |
| B2026 | ref_path_missing | paper_path not found: 'viking://session/.overview.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业报告AI医疗高景气度有望持续创新药利好政策持续加码/图表目录_aee973ee.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业周报AI赋能开启医疗新篇章商业化落地加速/赋能开启医疗新篇章商业化落地加速AI医药生物/.abstract.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业报告工信部等七部门印发关于推动脑机接口产业创新发展的实施意见相关行业确定性提高/创新发展的实施意见相关行业确定性提高/创新发展的实施意见相关行业确定性提高/.overview.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业周报25年第9周海外器械龙头2024年年报业绩概览继续推荐创新药械/风险提示/风险提示_17.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业周报看好Q2板块复苏重点关注创新药AI医疗消费医疗/2025年04月27日/2025年04月27日_1.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业周报医疗AI持续火热建议关注三大应用方向/1医药行业周观点/1医药行业周观点_3.md' |
| B2026 | ref_path_missing | paper_path not found: './resources/医药生物行业周报AI赋能开启医疗新篇章商业化落地加速/医药生物行业周报AI赋能开启医疗新篇章商业化落地加速/医药生物行业周报AI赋能开启医疗新篇章商业化落地加速_2.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业双周报2025年第1期总第124期关于全面深化药品医疗器械监管改革促进_805ace8f_1/4_投资建议/4_投资建议_25.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业双周报2025年第1期总第124期关于全面深化药品医疗器械监管改革促进_805ace8f_2/4_投资建议/4_投资建议_25.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业跟踪周报医保丙类目录及商保积极变化创新药板块弹性大/弹性大/增持维持/本周及年初至今各医药股收益情况_1/本周及年初至今各医药股收益情况_1/本周及年初至今各医药股收益情况_1_8.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业周报8月第2周关注减肥药潜在BD机会/医药生物_关注减肥药潜在BD机会/医药生物_关注减肥药潜在BD机会_4.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业双周报2025年第1期总第124期关于全面深化药品医疗器械监管改革促进_805ace8f_2/4_投资建议/4_投资建议_27.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业双周报2025年第1期总第124期关于全面深化药品医疗器械监管改革促进_805ace8f_1/4_投资建议/4_投资建议_27.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/首次覆盖报告片仔癀做深做精安宫牛黄丸开辟第二增长曲线/KEYINDEXTBL/KEYINDEXTBL_17.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业周报10月第3周创新药出海BD热度不减/二_行业要闻及重点公司公告/23_公司公告/23_公司公告_5.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业双周报2025年第1期总第124期关于全面深化药品医疗器械监管改革促进_805ace8f/4_投资建议/4_投资建议_25.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业周报看好Q2板块复苏重点关注创新药AI医疗消费医疗/2025年04月27日/2025年04月27日_11.md' |
| B2029 | ref_path_missing | paper_path not found: 'viking://user/default/memories/entities/.overview.md' |
| B2029 | ref_path_missing | paper_path not found: 'viking://user/default/memories/.abstract.md' |
| B2029 | ref_path_missing | paper_path not found: 'viking://user/default/memories/preferences/.overview.md' |
| B2029 | ref_path_missing | paper_path not found: 'viking://session/.overview.md' |
| B2029 | ref_path_missing | paper_path not found: 'viking://user/default/memories/events/.abstract.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业跟踪周报国内创新药与MNC的BD交易活跃建议关注三生制药新诺威恒瑞医药等/关注三生制药新诺威恒瑞医药等/增持维持/本周及年初至今各医药股收益情况_1/本周及年初至今各医药股收益情况_1_8.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/2025年中国中药市场行业研究报告/2025年/2025年_19.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药行业周报中国创新药BD能力显著提升后续潜力值得继续期待/3风险提示/3风险提示_4.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药行业周报国产新药授权节奏前移建议关注临床早期资产/3风险提示/3风险提示_3.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业周报创新药行业进入快速成长期关注未来6-12个月投资机会_2/创新药行业进入快速成长期关注未来个月投资机会_16-12/中国创新药资产迎来出海浪潮交易总金额持续刷新纪录_12BD/.abstract.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业周报创新药行业进入快速成长期关注未来6-12个月投资机会_2/创新药行业进入快速成长期关注未来个月投资机会_16-12/中国创新药资产迎来出海浪潮交易总金额持续刷新纪录_12BD/中国创新药资产迎来出海浪潮交易总金额持续刷新纪录_12BD_4.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业周报创新药行业进入快速成长期关注未来6-12个月投资机会_1/创新药行业进入快速成长期关注未来个月投资机会_16-12/中国创新药资产迎来出海浪潮交易总金额持续刷新纪录_12BD/.abstract.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/2026年医药行业投资策略聚焦创新出海与确定性/目录/年创新风格极致之年复盘1_2025/年是创新风格极致之年基本面市场与基金持股11_2025/年是创新风格极致之年基本面市场与基金持股11_2025_9.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/医药生物行业周报重视Pharma估值重塑的机会/重视估值重塑的机会Pharma医药生物/优化集采叠加创新驱动迎接制药板块商业化新周期_1/集采优化基调明确全链条支持创新全力推进_11/集采优化基调明确全链条支持创新全力推进_11_4.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/2026年医药行业投资策略聚焦创新出海与确定性/目录/聚焦创新交易与商业化共振共创创新药大年3_BD/我国海外授权交易的回顾与展望特点空间与潜力品种与靶点32/我国海外授权交易的回顾与展望特点空间与潜力品种与靶点32_3.md' |
| B2029 | ref_path_missing | paper_path not found: 'viking://session/.abstract.md' |
| B2029 | ref_path_missing | paper_path not found: 'viking://user/default/memories/events/.overview.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/业绩平稳运行研发管线进入收获期/业绩平稳运行研发管线进入收获期证券研究报告/公司点评报告/天士力600535/天士力600535_3.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/普佑克新适应症获批有望打造第二成长曲线/普佑克新适应症获批有望打造第二成长曲线证券研究报告/公司点评报告/天士力600535/天士力600535_3.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/P134获批临床看好公司研发管线进展/买入/原评级买入/板块评级强于大市/板块评级强于大市_2.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/公司信息更新报告2025H1利润端稳健增长优化研发布局提升竞争力/公司信息更新报告2025H1利润端稳健增长优化研发布局提升竞争力/公司信息更新报告2025H1利润端稳健增长优化研发布局提升竞争力_1.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/华润融合顺利推进创新研发价值重估/华润融合顺利推进创新研发价值重估证券研究报告/公司点评报告/天士力600535/天士力600535_3.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/公司信息更新报告2025H1利润端稳健增长优化研发布局提升竞争力/公司信息更新报告2025H1利润端稳健增长优化研发布局提升竞争力/公司信息更新报告2025H1利润端稳健增长优化研发布局提升竞争力_2.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/公司信息更新报告管线创新稳步推进中药研发龙头地位持续巩固/公司信息更新报告管线创新稳步推进中药研发龙头地位持续巩固/公司信息更新报告管线创新稳步推进中药研发龙头地位持续巩固_1.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/中药现代化领军企业华润入主厚积薄发/中药现代化领军企业华润入主厚积薄发/买入首次/三十年征程造就现代中药国际化先锋_1/化药仿创结合集采风险逐步出清_32/化药仿创结合集采风险逐步出清_32_3.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/业绩平稳运行研发管线进入收获期/业绩平稳运行研发管线进入收获期证券研究报告/公司点评报告/天士力600535/天士力600535_1.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/公司信息更新报告2025H1利润端稳健增长优化研发布局提升竞争力/公司信息更新报告2025H1利润端稳健增长优化研发布局提升竞争力/.abstract.md' |
| B2029 | ref_path_missing | paper_path not found: 'viking://user/default/memories/.overview.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/普佑克新适应症获批有望打造第二成长曲线/普佑克新适应症获批有望打造第二成长曲线证券研究报告/公司点评报告/天士力600535/天士力600535_2.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/公司信息更新报告管线创新稳步推进中药研发龙头地位持续巩固/管线创新稳步推进中药研发龙头地位持续巩固/.abstract.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/华润融合顺利推进创新研发价值重估/华润融合顺利推进创新研发价值重估证券研究报告/公司点评报告/天士力600535/天士力600535_4.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/业绩平稳运行研发管线进入收获期/业绩平稳运行研发管线进入收获期证券研究报告/公司点评报告/天士力600535/天士力600535_4.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/公司信息更新报告管线创新稳步推进中药研发龙头地位持续巩固/公司信息更新报告管线创新稳步推进中药研发龙头地位持续巩固/公司信息更新报告管线创新稳步推进中药研发龙头地位持续巩固_2.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/华润融合顺利推进创新研发价值重估/华润融合顺利推进创新研发价值重估证券研究报告/公司点评报告/天士力600535/天士力600535_1.md' |
| B2029 | ref_path_missing | paper_path not found: 'viking://user/default/memories/entities/.abstract.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/华润融合顺利推进创新研发价值重估/华润融合顺利推进创新研发价值重估证券研究报告/公司点评报告/天士力600535/.abstract.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/中药现代化领军企业华润入主厚积薄发/中药现代化领军企业华润入主厚积薄发/买入首次/三十年征程造就现代中药国际化先锋_1/三十年征程造就现代中药国际化先锋_1/三十年征程造就现代中药国际化先锋_1_5.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/中药现代化领军企业华润入主厚积薄发/中药现代化领军企业华润入主厚积薄发/买入首次/买入首次/买入首次_2.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/中药现代化领军企业华润入主厚积薄发/中药现代化领军企业华润入主厚积薄发/买入首次/三十年征程造就现代中药国际化先锋_1/三十年征程造就现代中药国际化先锋_1/.abstract.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/中药现代化领军企业华润入主厚积薄发/中药现代化领军企业华润入主厚积薄发/买入首次/三十年征程造就现代中药国际化先锋_1/复方丹参滴丸心血管治疗基本盘扎实糖网适应症开拓第二成长曲线_22/复方丹参滴丸心血管治疗基本盘扎实糖网适应症开拓第二成长曲线_22_3.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/中药现代化领军企业华润入主厚积薄发/中药现代化领军企业华润入主厚积薄发/买入首次/三十年征程造就现代中药国际化先锋_1/三十年征程造就现代中药国际化先锋_1/三十年征程造就现代中药国际化先锋_1_2.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/中药现代化领军企业华润入主厚积薄发/中药现代化领军企业华润入主厚积薄发/买入首次/三十年征程造就现代中药国际化先锋_1/芪参益气滴丸销量稳步增长二次开发迎新生_24/.abstract.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/中药现代化领军企业华润入主厚积薄发/中药现代化领军企业华润入主厚积薄发/中药现代化领军企业华润入主厚积薄发_1.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/中药现代化领军企业华润入主厚积薄发/中药现代化领军企业华润入主厚积薄发/买入首次/三十年征程造就现代中药国际化先锋_1/芪参益气滴丸销量稳步增长二次开发迎新生_24/芪参益气滴丸销量稳步增长二次开发迎新生_24_2.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/中药现代化领军企业华润入主厚积薄发/中药现代化领军企业华润入主厚积薄发/买入首次/买入首次/买入首次_3.md' |
| B2029 | ref_path_missing | paper_path not found: './resources/中药现代化领军企业华润入主厚积薄发/.abstract.md' |
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
