/* Presentation-only localization. Data values and control values remain unchanged. */
(() => {
  'use strict';
  const phrases = [
    ['Active single-game model: Additive v1','当前单场模型：Additive v1'],['FROZEN WEIGHTS · LIVE FEATURES','冻结权重 · 实时特征'],['Dynamic normal-margin baseline plus team and player feature corrections. Total and margin produce joint score estimates. Season simulations and the legacy documentation below use the previous Student-t model.','动态正态分差基线加球队与球员特征修正，结合总分与分差生成联合比分预测。赛季模拟及下方旧版说明仍采用原 Student-t 模型。'],['Legacy snapshot prequential scorecard','旧模型快照逐场预测评分'],['Legacy matchup sandbox','旧模型对阵模拟'],['Single-game model:','单场模型：'],['Season projections:','赛季预测：'],['Projected score:','预计比分：'],['Projected total:','预计总分：'],['80% total interval','总分 80% 区间'],['Dynamic baseline','动态基线'],['Team feature correction','球队特征修正'],['Additive player correction','Additive 球员修正'],['Positive Δ Log loss means this correction worsened predictions. Active and shadow models are evaluated separately.','Δ 对数损失为正表示该修正使预测变差。当前模型与影子对照分别评估。'],
    ['Live prediction trace','实时预测追溯'],['Frozen pregame forecasts → results → stage residuals','冻结赛前预测 → 赛果 → 分阶段残差'],['Loading trace diagnostics…','正在加载追溯诊断…'],['Primary cohort: latest recorded forecast at least 24 hours before tipoff. Stage differences describe this pipeline; they are not causal effects.','正式评估：开赛至少 24 小时前最后记录的预测。阶段差异描述本管道的修正效果，不代表因果效应。'],['forecast records','条预测记录'],['evaluated games','场已评估比赛'],['results without an eligible forecast','场赛果缺少合格赛前预测'],['Collecting pregame evidence. Results appear after eligible games finish.','正在积累赛前记录，合格比赛完赛后显示结果。'],['Team strength','球队基础实力'],['Availability / recovery','可出场阵容 / 恢复'],['Game context','比赛情境'],['Prediction trace stages','预测阶段追溯'],['Positive Δ Log loss means this correction worsened predictions. The deployed model has no Additive or joint-score stage yet.','Δ 对数损失为正表示该修正使预测变差。当前线上模型尚无 Additive 或联合比分阶段。'],['Trace summary JSON','追溯汇总 JSON'],['Settled game traces JSON','已结算比赛追溯 JSON'],['Current forecast stages JSON','当前预测阶段 JSON'],['Trace data is not available for this snapshot.','当前快照暂无追溯数据。'],['Margin MAE','分差平均绝对误差'],['Version','版本'],['Stage','阶段'],
    ['Season profile','赛季档案'],['SEASON PROFILE','本赛季球员档案'],['Close player profile','关闭球员档案'],['Season to date','本赛季至今'],['Shot heat map','投篮热区图'],['Season shot heat map','本赛季投篮热区图'],['Color = field-goal percentage · opacity = shot volume · tap a zone for details.','颜色表示投篮命中率，深浅表示出手量；点击区域可查看详情。'],['Select a zone to see makes and attempts.','选择区域查看命中数和出手数。'],['Shot locations are not available for this snapshot.','当前快照暂无投篮位置数据。'],['Located attempts:','已定位出手：'],['Beyond half court:','超远出手：'],['Season box scores and play-by-play','本赛季技术统计及逐回合记录'],['TOV / game','场均失误'],['PPG','场均得分'],['RPG','场均篮板'],['APG','场均助攻'],['SPG','场均抢断'],['BPG','场均盖帽'],['MPG','场均分钟'],['GP','出场'],['TS%','真实命中率'],['FG%','投篮命中率'],['FT%','罚球命中率'],

    ['Probability is a perspective, not a promise.','概率提供视角，而非承诺。'],
    ['Snapshot research model · data provenance and coverage in Model & audit.','快照研究模型 · 数据来源及覆盖范围详见模型与审计。'],
    ['Thirty teams. A hundred thousand possible seasons.','30 支球队，十万种可能的赛季。'], ['One evolving view of the league.','从不断变化的视角观察联盟。'],
    ['THE SEASON, IN PROBABILITIES','用概率观察整个赛季'],['Beyond the record','超越战绩'],['NBA PROBABILITY LAB','NBA 概率实验室'],['EST. 2026','创立于 2026'],
    ['Player statistics are not available for this snapshot. Please try again later.','当前快照暂时没有球员统计，请稍后重试。'],['Loading player box scores…','正在加载球员技术统计…'],['SEASON BOX-SCORE PRODUCTION','本赛季技术统计表现'],['Impact players','影响力球员'],['01 / THE BOX SCORE LENS','01 / 技术统计视角'],['Production, in context.','从数据观察赛场表现。'],['Game Score summarizes box-score production; it is not a causal measure of impact on winning. It misses off-ball play, defense beyond recorded events, teammates and opponents. Small early-season samples are volatile.','比赛表现分数汇总技术统计，并非对胜负影响的因果度量。它无法完整反映无球表现、记录之外的防守以及队友和对手因素；赛季初样本较少，波动较大。'],['Minimum 3 games · Top 20 · Game Score per game ranks average production; total rewards availability. TS% = points / (2 × (FGA + 0.44 × FTA)).','至少出场 3 场 · 前 20 名 · 场均表现分数衡量平均表现，累计分数同时体现出场时间。真实命中率 = 得分 / (2 × (投篮出手 + 0.44 × 罚球出手))。'],['Box-score estimates do not capture every contribution.','技术统计无法涵盖所有贡献。'],['Metric glossary','指标释义'],['Impact player leaderboard','球员表现榜'],['Game Score / game','场均表现分数'],['Total Game Score','累计表现分数'],['Rank by','排序'],['BOX SCORES','已覆盖场次'],['SOURCE','来源'],
    ['Win distributions','胜场分布'],['Model & audit','模型与审计'],['Rankings','排名'],['Ratings','实力评分'],['Games','比赛'],['Teams','球队'],
    ['Strength, with uncertainty.','实力及其不确定性。'],['Rating is expected points above an average team on a neutral court.','实力评分是中立场地上相对于平均球队的预期净胜分。'],['Hover a rating for its 90% interval.','将鼠标悬停在评分上可查看 90% 区间。'],['Projections cover','预测覆盖'],['listed games; Prior Δ compares partial-schedule wins with unverified preseason totals.','场已列赛程；先验差值比较不完整赛程的预测胜场与未经核实的赛季前总胜场。'],
    ['Snapshot research build.','研究用数据快照。'],['The supplied seed data has unverified provenance.','所提供的初始数据来源尚未核实。'],['Results below are calculated from','以下结果根据'],['supplied completed games using chronological pregame predictions.','场已提供的完赛数据和按时间顺序生成的赛前预测计算。'],['Priors may contain information not independently audited.','先验可能包含未经独立审计的信息。'],['This is not a multi-season out-of-sample backtest.','这不是跨赛季样本外回测。'],
    ['A Kalman-style filter updates preseason ratings from score-based, soft-capped margins. Team uncertainty shrinks with observations; the league is centered at zero.','类卡尔曼滤波器根据比分计算并软限制的净胜分更新赛季前评分。随着观测增加，球队的不确定性收窄；联盟均值以零为中心。'],
    ['Active roster discounts, home court, altitude, rest and back-to-backs shift the expected margin. A variance-matched Student-t distribution converts it into a win probability.','可出场阵容折减、主场、海拔、休息及背靠背调整预期净胜分，再通过方差匹配的 Student-t 分布转换为胜率。'],
    ['Sample uncertain strength once per season, then simulate each listed game, play-in tournament and 2–2–1–1–1 playoff series. Injury recovery is an assumed team-level Weibull horizon; ties use random jitter, not official tiebreakers.','每次模拟赛季先抽样球队实力，再模拟已列比赛、附加赛和 2–2–1–1–1 季后赛系列赛。伤病恢复时间采用球队层面的 Weibull 假设；排名相同时使用随机扰动，而非官方排名规则。'],
    ['Data through','数据截至'],['games listed versus','场已列赛程，预期共'],['expected;','场；'],['games are not represented.','场未纳入。'],['Win projections and loss counts follow the supplied schedule, so a partial-schedule projection is not directly comparable with an 82-game preseason total.','胜负场预测基于所提供的赛程，因此不完整赛程的预测不能直接与 82 场赛季前预测相比。'],
    ['The offline build does not refresh scores.','离线构建不会自动刷新比分。'],['score-based proxy; raw lineup stints are not supplied.','基于比分的近似值；未提供原始阵容时段数据。'],['position priors.','位置先验。'],['only independently supplied market_spread observations; missing lines stay null.','仅使用独立提供的 market_spread 数据；缺失盘口保持为空。'],['No market performance or expected betting value is claimed.','不对市场表现或投注期望收益作出声明。'],['Current injury information is only used for future forecasts. Historical injury-adjusted priors and player-level return-date survival models require additional source data. Published intervals describe this model, not every source of uncertainty.','当前伤病信息仅用于未来预测。历史伤病调整先验和球员级复出日期生存模型需要额外数据。公布的区间描述的是本模型的不确定性，并不涵盖所有不确定因素。'],
    ['O/D values are a position-based allocation of seed player value, not measured impact estimates. Injury statuses are snapshot inputs.','进攻／防守数值是按位置分配的初始球员价值，并非实测影响力；伤病状态来自数据快照。'],
    ['Market and edge stay blank when no observed market line is supplied. A spread difference alone is not a priced +EV bet.','没有实际市场盘口时，市场及差值保持为空。仅凭让分差不能认定为正期望收益投注。'],['Change the teams and home advantage. Uses the same Student-t transform as the Python model.','可调整对阵球队和主场优势；使用与 Python 模型相同的 Student-t 转换。'],
    ['Selected team with 90% credible band · background lines show the league','所选球队及 90% 可信区间 · 背景线表示联盟其他球队'],['Top 6 and play-in are separate qualification paths','前六名与附加赛是不同的晋级路径'],['Top 6 direct · 7–10 play-in · 11–15 eliminated','前六直接晋级 · 7–10 名进入附加赛 · 11–15 名淘汰'],['Lime: rating ±90% · hollow dots: clean margin proxy (right axis)','浅绿色：评分及 90% 区间 · 空心点：净胜分近似值（右轴）'],['Game win probabilities · trailing 10-game average in lime','单场胜率 · 浅绿色表示最近 10 场平均值'],['Point size reflects sample count. Small snapshot bins have substantial sampling uncertainty.','点的大小表示样本数。快照中样本较少的分组具有较大的抽样不确定性。'],
    ['Loading model snapshot…','正在加载模型快照…'],['Loading league data…','正在加载联盟数据…'],['Snapshot unavailable','模型快照不可用'],['Retry loading','重试加载'],['DATA THROUGH','数据截至'],['score proxy; no raw stints','比分近似值；无原始阵容时段数据'],['DATA LOAD FAILED','数据加载失败'],['Skip to content','跳至内容'],['Switch color theme','切换主题颜色'],['Switch theme','切换主题'],['n-Beta home','n-Beta 首页'],['Main views','主要页面'],['Download data','下载数据'],
    ['League outlook','联盟展望'],['BAYESIAN RATINGS · 90% CREDIBLE INTERVALS','贝叶斯评分 · 90% 可信区间'],['The range of possible','可能的胜场范围'],['REGULAR SEASON · 10TH–90TH PERCENTILE','常规赛 · 第 10–90 百分位'],['Strength is a moving target','实力随时间变化'],['DYNAMIC STATE-SPACE RATINGS','动态状态空间评分'],['Every game is a distribution','每场比赛都是一个分布'],['HOME SPREAD: NEGATIVE MEANS FAVORED','主场让分：负数表示主队占优'],['Team intelligence','球队分析'],['A CLOSER LOOK','深入观察'],['Open the black box','打开模型黑箱'],['ASSUMPTIONS, INPUTS & OBSERVED PERFORMANCE','假设、输入与观测表现'],
    ['Three layers. One forecast.','三层模型，一项预测。'],['BAYESIAN STATE → MATCHUP → POSSIBLE SEASONS','贝叶斯状态 → 对阵预测 → 赛季模拟'],['Evolving team strength','球队实力演化'],['A heavy-tailed matchup','厚尾对阵模型'],['Simulate the whole path','模拟完整赛季'],['Calibration, observed','观测校准'],['X: forecast win probability · Y: realized home win rate','横轴：预测胜率 · 纵轴：实际主场胜率'],['Snapshot prequential scorecard','快照逐场预测评分'],['Core parameters','核心参数'],['Context factors','情境因素'],['Configured values · no cross-validation claim','配置值 · 不代表已交叉验证'],['Configured assumptions · historical ablation not available','配置假设 · 尚无历史消融验证'],['Data coverage & known limits','数据覆盖与已知限制'],
    ['Rating / 90% CI','评分 / 90% 可信区间'],['Active rating','当前可出场阵容评分'],['Projected wins','预测胜场'],['Playoffs / Title','季后赛 / 冠军'],['Preseason total','赛季前预测总胜场'],['Win distribution','胜场分布'],['Playoff path','季后赛路径'],['Conference seed','分区种子'],['Rating over time','历史评分'],['The road ahead','剩余赛程'],['Remaining schedule','剩余赛程'],['Roster & availability','阵容及出场情况'],['Team results','球队赛果'],['Team roster','球队阵容'],['Results','赛果'],['No next game','暂无下一场比赛'],['No remaining games.','没有剩余比赛。'],
    ['Matchup sandbox','对阵模拟'],['Home rating adjustment','主队评分调整'],['Home team','主队'],['Away team','客队'],['Neutral court','中立场地'],['Apply injury discount','应用伤病折减'],['Choose two different teams to forecast a matchup.','请选择两支不同的球队进行预测。'],['Home spread','主场让分'],['Equal rest · no B2B','双方休息相同 · 无背靠背'],['No games scheduled on this date.','该日期没有比赛。'],['Previous day','前一天'],['Next day','后一天'],['Game date','比赛日期'],
    ['MODEL / HOME','模型 / 主队'],['MARKET / HOME','市场 / 主队'],['EDGE / HOME','差值 / 主队'],['FORECAST','预测'],['FINAL','已结束'],['REMAINING','剩余'],['SEASON','赛季'],['SCORE FEED','比分更新'],['SEED SNAPSHOT','初始快照'],['View data audit','查看数据审计'],['scores checked','比分检查于'],['earlier games unresolved','场较早比赛未核实'],['listed games','场已列赛程'],['unlisted','场未列入'],['simulations','次模拟'],
    ['Mean projected wins','平均预测胜场'],['80% posterior interval · seed total dashed','80% 后验区间 · 虚线表示初始总胜场'],['80% interval','80% 区间'],['Preseason total & prior PMF','赛季前总胜场及先验概率分布'],['All projections','全部预测'],['Above preseason total','高于赛季前预测'],['Below preseason total','低于赛季前预测'],['Compare preseason total','比较赛季前预测'],['No teams match this filter.','没有球队符合筛选条件。'],['No teams match your search.','没有匹配的球队。'],['Find a team','查找球队'],['City, team or abbreviation','城市、球队或缩写'],['Export PNG','导出 PNG'],['Rendering…','正在生成…'],['Export failed · retry','导出失败 · 重试'],
    ['Team / Record','球队 / 战绩'],['Prior Δ','先验差值'],['Proj. W','预测胜场'],['Injury synergy','伤病影响'],['Posterior & prior','后验与先验'],['90% credible interval','90% 可信区间'],['90% credible band','90% 可信区间'],['Team rating history with 90% credible interval','球队评分历史及 90% 可信区间'],['projected wins probability distribution','预测胜场概率分布'],['Conference seed probabilities','分区种子概率'],['Playoff qualification and advancement probabilities','季后赛资格与晋级概率'],['Remaining games win probabilities and trailing 10-game average','剩余比赛胜率及最近 10 场平均值'],['Observed calibration of snapshot predictions','快照预测的观测校准'],['clean margin proxy','净胜分近似值'],['predicted','预测'],['observed','实际'],
    ['Sort by','排序：'],['Select team','选择球队'],['Conference','分区'],['League','联盟'],['East','东部'],['West','西部'],['Team rankings','球队排名'],['Rating decomposition','评分分解'],['Prediction audit','预测审计'],['Team','球队'],['Record','战绩'],['Rating','评分'],['Prior','先验'],['Current','当前'],['Active','可出场'],['Injury','伤病'],['Playoffs','季后赛'],['Title','冠军'],['Model','模型'],['Scope','范围'],['Log loss','对数损失'],['Brier','布里尔分数'],['Accuracy','准确率'],['Parameter','参数'],['Factor','因素'],['Value','数值'],['Unit','单位'],['Date','日期'],['Opponent','对手'],['Score','比分'],['Market','市场'],['Edge','差值'],['Clean proxy','净胜分近似值'],['Player','球员'],['Status','状态'],['Return','复出'],['Out %','缺阵概率'],['Game data:','比赛数据：'],['Injuries:','伤病：'],['Margins:','净胜分：'],['Player O/D:','球员攻防：'],['Markets:','市场：'],['Seed','种子'],['Top 6','前六'],['Play-in','附加赛'],['Round 1','首轮'],['Round 2','次轮'],['Conf. finals','分区决赛'],['Finals','总决赛'],['championship','夺冠'],['No teams','没有球队'],[' win',' 获胜'],[' wins',' 胜'],[' pts',' 分'],['NEXT','下一场'],['OVERALL','联盟排名'],
    ['Preseason prior SD','赛季前先验标准差'],['Per-game state variance','每场比赛状态方差'],['Score proxy soft cap','比分近似值软上限'],['Student-t degrees of freedom','Student-t 自由度'],['Baseline game standard deviation','比赛基准标准差'],['Injury overload penalty','伤病超负荷惩罚'],['Playoff star multiplier','季后赛球星系数'],['Home court advantage','主场优势'],['Back-to-back penalty','背靠背惩罚'],['Rest differential','休息时间差'],['Altitude bonus','高海拔加成'],['snapshot prequential','快照逐场预测'],['50% baseline','50% 基准'],
    ['Oklahoma City','俄克拉何马城'],['San Antonio','圣安东尼奥'],['Golden State','金州'],['Los Angeles','洛杉矶'],['New Orleans','新奥尔良'],['New York','纽约'],['Portland','波特兰'],['Philadelphia','费城'],['Minnesota','明尼苏达'],['Sacramento','萨克拉门托'],['Washington','华盛顿'],['Cleveland','克利夫兰'],['Milwaukee','密尔沃基'],['Indianapolis','印第安纳波利斯'],['Indiana','印第安纳'],['Brooklyn','布鲁克林'],['Charlotte','夏洛特'],['Toronto','多伦多'],['Houston','休斯敦'],['Detroit','底特律'],['Boston','波士顿'],['Denver','丹佛'],['Miami','迈阿密'],['Atlanta','亚特兰大'],['Orlando','奥兰多'],['Phoenix','菲尼克斯'],['Dallas','达拉斯'],['Memphis','孟菲斯'],['Chicago','芝加哥'],['Utah','犹他'],
    ['Trail Blazers','开拓者'],['Timberwolves','森林狼'],['Thunder','雷霆'],['Spurs','马刺'],['Rockets','火箭'],['Pistons','活塞'],['76ers','76人'],['Celtics','凯尔特人'],['Knicks','尼克斯'],['Lakers','湖人'],['Cavaliers','骑士'],['Raptors','猛龙'],['Nuggets','掘金'],['Heat','热火'],['Hawks','老鹰'],['Magic','魔术'],['Warriors','勇士'],['Pacers','步行者'],['Suns','太阳'],['Mavericks','独行侠'],['Wizards','奇才'],['Grizzlies','灰熊'],['Hornets','黄蜂'],['Pelicans','鹈鹕'],['Jazz','爵士'],['Bulls','公牛'],['Clippers','快船'],['Nets','篮网'],['Bucks','雄鹿'],['Kings','国王']
  ];
  // Prefer longer phrases so common labels cannot split full explanations.
  phrases.sort((a,b) => b[0].length - a[0].length);
  const pattern = new RegExp(phrases.map(([s]) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g');
  const dictionary = new Map(phrases);
  const originals = new WeakMap();
  let language = 'en';
  try { language = localStorage.getItem('nbeta-language') === 'zh' ? 'zh' : 'en'; } catch {}
  const button = document.createElement('button');
  button.id = 'language';
  button.type = 'button';
  button.innerHTML = '<span data-lang="zh">CN</span><span class="language-separator"> / </span><span data-lang="en">EN</span>';
  document.querySelector('.masthead').insertBefore(button, document.querySelector('#theme'));
  function translated(value) { return value.replace(pattern, match => dictionary.get(match)); }
  window.nbetaTranslate = translated;
  function applyValue(node, key, value, set) {
    let saved = originals.get(node);
    if (!saved) { saved = {}; originals.set(node, saved); }
    let entry = saved[key];
    if (!entry || (value !== entry.last && value !== entry.original)) entry = saved[key] = {original:value, last:value};
    const next = language === 'zh' ? translated(entry.original) : entry.original;
    entry.last = next;
    if (value !== next) set(next);
  }
  function applyLanguage() {
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
    applyValue(document, 'title', document.title, value => { document.title = value; });
    button.setAttribute('aria-label', language === 'zh' ? '切换为英文 / Switch to English' : '切换为中文 / Switch to Chinese');
    button.title = language === 'zh' ? '切换为英文' : 'Switch to Chinese';
    button.querySelectorAll('[data-lang]').forEach(el => el.classList.toggle('selected', el.dataset.lang === language));
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.parentElement.closest('#language, script, style, code, .formula')) continue;
      applyValue(node, 'text', node.nodeValue, value => { node.nodeValue = value; });
    }
    document.querySelectorAll('[aria-label], [title], [placeholder]').forEach(el => {
      if (el === button || button.contains(el)) return;
      for (const key of ['aria-label','title','placeholder']) if (el.hasAttribute(key)) {
        applyValue(el, key, el.getAttribute(key), value => el.setAttribute(key, value));
      }
    });
  }
  let scheduled = false;
  const observer = new MutationObserver(() => {
    if (!scheduled) { scheduled = true; requestAnimationFrame(() => { scheduled = false; applyLanguage(); }); }
  });
  observer.observe(document.body, {subtree:true, childList:true, characterData:true, attributes:true, attributeFilter:['aria-label','title','placeholder']});
  observer.observe(document.head.querySelector('title'), {subtree:true, childList:true, characterData:true});
  button.addEventListener('click', () => {
    language = language === 'en' ? 'zh' : 'en';
    try { localStorage.setItem('nbeta-language', language); } catch {}
    applyLanguage();
  });
  applyLanguage();
})();
