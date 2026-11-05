# n-Beta / NBA Probability Lab

Python 离线评级与蒙特卡洛管道，原生 HTML/CSS/D3 六视图静态看板。无需 Node 构建或后端服务。

## 本地运行

需要 Python 3.12+。

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pipeline.build_daily --sims 100000
python -m http.server 8765 --bind 127.0.0.1
```

打开 http://127.0.0.1:8765 。已有 `data/` 产物时可直接启动静态服务。不要双击 HTML 使用 `file://`，浏览器会限制 JSON 加载。

小样本开发构建：`python -m pipeline.build_daily --sims 1000`。模拟次数必须为正；默认 100,000。随机种子固定在 `pipeline/config.py`。

`--live` 只尝试覆盖 ESPN 伤病信息，失败回退种子，来源写入 `run.json`。它不会更新赛程、比赛比分、球员价值或盘口；请使用经过验证的源更新 `data/seed/` 后重新构建。未来球队、球员与赛程通过 CSV 输入；可选 `market_spread` 列仅接受独立观测的主队市场让分（负数为主队让分），不使用原 seed `spread` 作为市场。

## 现有功能

- Rankings：联盟/分区、搜索、列排序、评级区间、80% 胜场区间、PNG 三栏分享卡。
- Win distributions：全队先验与后验 PMF、区间与季前参考线、分区和高低于先验总胜场筛选。
- Ratings：全联盟评级轨迹、单队 90% 置信带、先验/后验/伤病折损明细。
- Games：逐日赛程、完赛结果、模型胜率、让分与有来源的市场差、可调整主场和伤病的 Student-t 沙盒。
- Teams：六指标、五图、比赛结果、剩余赛程与阵容伤病表，支持 `#team/OKC` 深链接。
- Model & audit：模型解释、参数、当前快照逐场赛前预测评分、实算校准曲线、CSV 导出。
- 深浅主题、键盘焦点、加载失败/空结果状态、窄屏滚动表格。

## 数据与模型边界

现有种子的六份 CSV 已定位到公开参考仓库，1,200 场赛程与 107 场已完赛比分已与 ESPN 全量核对。球员统计大部分落后于球队赛果；先验及球员价值的生成和历史可用时间仍未验证。详见 `docs/SEED_VERIFICATION.md`。NBA 初始安排每队 80 场，另外两场待 NBA Cup 结果确定；当前模拟只覆盖 80 场，不是完整 82 场预测。

- `as_of` 是构建时间，`data_through` 是最后一场已完赛日期，不能把重建视为数据刷新。
- 真实 lineup stints 尚未提供，清洗是比分代理 + tanh 截断，非逐回合观测清洗。
- 球员 O/D 拆分是位置先验，不是实测 RAPM/BPM 分解。
- 伤病恢复使用球队层面的假设 Weibull 时间尺度，尚未逐球员拟合复出日期。
- 回测仅是当前种子快照的 prequential 评分。先验来源可能包含未来信息，不能称为独立样本外成绩。无硬编码多季成绩或虚构交叉验证提升。
- 缺失市场线导出为 `null`，不生成虚构 Vegas 让分。盘口差不等于投注期望收益。
- 季后赛按附加赛与七战四胜模拟，常规赛同战绩随机打破平局，未实现官方完整 tiebreaker。
- `docs/MODEL.md` 描述当前实际模型；本文件与 `docs/ACCEPTANCE.md` 记录交付的实际状态。

## 验证

```sh
python -m unittest discover -s tests -v
python -m pipeline.build_daily --sims 100000
node --check assets/app.js
```

浏览器端到端检查：

```sh
pip install -r requirements-dev.txt
python -m playwright install chromium
python -m http.server 8765 --bind 127.0.0.1
# 另一个已激活虚拟环境的终端：
python tests/browser_check.py
```

也可先启动本地服务再运行 `python tests/browser_check.py`。浏览器依赖仅用于开发；不参与部署。构建会在写出文件前校验赛程胜负、评级零均值、晋级漏斗和种子/胜场概率总和。

## GitHub 仓库与 CI

公开仓库：https://github.com/leoq77777/nBeta 。本次仅发布已经验收的生产快照版本，范围见 `docs/RELEASE_SCOPE.md`。

`.github/workflows/checks.yml` 在 push、pull request 或手动触发时运行生产单元测试、JavaScript 语法检查和完整离线构建。构建不会刷新比赛比分，也不会自动发布网站。GitHub Pages 部署作为后续独立步骤配置。

## 目录

- `pipeline/`：配置、数据加载、评级、模拟、构建与数据校验。
- `data/seed/`：输入快照；`data/*.json`、`*.csv`：导出契约。
- `index.html`、`assets/`：静态站点，所有运行资源本地提供。
- `tests/`：模型回归与真实浏览器验收。
- `docs/`：实施口径与验收报告。

## 数据核验与实际公式

- `python -m pipeline.verify_seed`：核对外部原始记录、缓存证据并生成差异报告。加 `--refresh` 可更新缓存。
- `docs/SEED_VERIFICATION.md`：来源、字段级结果、统计时点差异与未解决事项。
- `docs/MODEL.md`：与代码逐项对应的公式、近似条件，以及尚未实现的动态环境参数方案。


数据来源与第三方文件说明见 `THIRD_PARTY_NOTICES.md`。
