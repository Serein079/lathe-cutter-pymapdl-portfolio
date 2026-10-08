# 复现与后续进阶操作

以下 PowerShell 命令从仓库根目录执行。`python` 路线只用于标准库验证；求解及绘图路线使用 `.\.venv\Scripts\python.exe`。先完成 README 中的环境安装。

## 阶段 A：读懂并核对基线

1. 执行 `python verify_evidence.py`，确认公开证据未改变。
2. 打开 `evidence/cases/parity/summary.json` 与 `csv/pressure_table.csv`，核对单位、E、泊松比、10 点压力表与最大位移。
3. 阅读 `src/baseline.py`，标记几何输入、网格、四个 SYMM 面、局部坐标和压力、求解、结果导出六个步骤。
4. 运行 `.\.venv\Scripts\python.exe src/baseline.py`，从控制台取得本次 `results/runs/...` 路径；检查 `solve_output.txt`、`summary.json`、节点 CSV 和三张图。不同 MAPDL/网格版本可能导致差异，应先记录版本与节点数，不要求跨版本逐位相同。
5. 用自己的话解释为什么 10 点表的实际峰值低于名义 10000 psi，为什么 `NLGEOM` 不代表材料塑性。

完成产物：一份基线核对记录，包含安装版本、输入、节点数、最大值、与历史结果差异及解释。

## 阶段 B：独立检查压力与反力

```powershell
.\.venv\Scripts\python.exe force_audit.py evidence/cases/advanced_20261008_linear_verification_baseline_linear --output results/audits/linear.json
.\.venv\Scripts\python.exe force_audit.py evidence/cases/parity --output results/audits/nonlinear.json
```

逐项检查面积、三角面数、力向量及残差；线性以初始几何比较，非线性说明变形构形的假设。下一步若扩展 SOLID187，需实现二次面形函数和积分点，不应直接复用四节点面平均压力公式。

## 阶段 C：重复三档网格研究

先验证只包含三档细网格的计划：

```powershell
.\.venv\Scripts\python.exe execute_advanced.py results/campaigns/dense_review plan plans/dense_mesh.json --plan-only
.\.venv\Scripts\python.exe execute_advanced.py results/campaigns/dense_review plan plans/dense_mesh.json
.\.venv\Scripts\python.exe analyze_study.py results/campaigns/dense_review/dense_mesh/study_results.csv --x global_size_in --group element --output-dir results/analysis/dense_review
.\.venv\Scripts\python.exe probe_study.py results/campaigns/dense_review/dense_mesh/study_results.csv --output-dir results/probes/dense_review
```

比较最大位移、固定点 VM 与峰值 VM。后两次位移/固定点变化满足自定阈值后，再检查峰值是否继续增长，避免用“位移稳定”替代“强度验证”。发布证据只包含最细一档 VTU，因此已有三档研究的固定点比较应查看发布 CSV；需要重新提取三档场则执行以上新研究。

修改计划：复制 `plans/dense_mesh.json` 到 `results/custom_dense.json`，追加新网格尺寸和唯一 case 名称，再使用新 campaign。提高网格密度前检查本机资源与 Student 许可实际限制。记录每次节点数、单元数和耗时，不预设细网格一定可执行。

## 阶段 D：解决峰值解释问题

1. 查看 `docs/assets/peak_region.png` 与 `symmetry_areas.png`，确定峰值与面积 16、几何边缘的位置关系。
2. 在独立分支中记录拟修改的真实工况：对称性是否成立、安装支撑究竟约束哪些自由度、载荷实际作用位置。
3. 每次只改一个假设；给修改版本新几何文件和 SHA256、新输入摘要，避免沿用官方面积编号而不检查对应面。
4. 在距离边界若干固定物理距离的位置设定路径或多个探针，写明坐标和选择理由。先确认所有网格中位置有效，再比较应力。
5. 若采用圆角、接触支撑或子模型，必须说明它们的尺寸、来源、载荷传递方式与边界充分性；重新做网格研究。
6. 根据目标材料选择适用的失效指标，并引用实际材料数据。尚未取得可收敛应力和可靠材料数据前，不计算并宣称已验证的安全系数。

完成产物：边界敏感性矩阵、路径应力图、建模假设解释和适用范围。

## 阶段 E：参数规律与 DOE 独立验证

1. 运行 `plans/load.json`、`plans/material.json`、`plans/doe.json`，分别使用新 campaign 名称。
2. 从输出 CSV 比较 `u/P` 与 `u×E`，解释为什么当前线弹性、小变形水平下接近常数。
3. 在原 DOE 网格之外但参数范围之内选择验证点，例如 P=9000 psi、E=9×10⁶ psi，建立单独计划并实际求解。
4. 在计算之前保存拟合预测值；计算之后输出预测/FEA 对照和相对误差。不要把九个训练点上的拟合误差当成泛化精度。
5. 若要优化，先写出目标、设计变量、材料/位移/应力约束及可靠的可收敛响应，再选择优化方法。当前数据只有参数扫描，没有完成优化。

## 阶段 F：从教学热模型到真实刀具热工况

运行 `.\.venv\Scripts\python.exe thermal_demo.py`，检查解析温度误差及温度到结构载荷的传递。随后先对热结构长方体做温度与结构网格研究，明确参考温度和安装约束。

实际刀具扩展需要另行取得或估计切削热源、热分配比例、对流、接触热阻、温度相关材料和实际支撑。记录数据来源与不确定度，统一单位，先做简单可验证模型，再移植到刀具几何。不能把长方体热结果作为刀具热应力结论。

## 阶段 G：形成可面试的个人成果

每完成一个新研究，将输入计划、版本、结果摘要、图像和解释整理为新的证据目录，并更新 README。新发布文件变化后可用 `python verify_evidence.py --skip-manifest` 做一致性检查，再用 `python build_manifest.py` 更新完整性记录，最后执行 `python verify_evidence.py`。新增研究数据需同步调整验证器的预期数量，而不是删除检查。

最终准备：三分钟讲述、五个关键截图、一次亲自复现记录、一份失败与修正说明。面试中把工具辅助代码、官方案例和实际个人判断分别说清楚。
