# 来源与贡献说明

本仓库是 ANSYS 官方 Lathe Cutter 教学案例的复现与扩展，不是 ANSYS 官方产品。

- 原始案例：[ansys/pymapdl / lathe_cutter.py](https://github.com/ansys/pymapdl/blob/main/examples/00-mapdl-examples/lathe_cutter.py)。
- 几何：[ansys/example-data / LatheCutter.anf](https://github.com/ansys/example-data/blob/master/geometry/LatheCutter.anf)。
- 官方案例来源和相关版权适用于衍生的模型流程；完整MIT声明保留于third_party/。
- Python代码扩展使用了工具辅助；个人贡献按实际参与的建模理解、运行、验证与分析说明。
- 新增内容：参数化求解、串行执行器、数据审核、固定点提取、力合量积分、网格/载荷/模量研究与独立热结构教学流程。
- 材料输入、压力和热边界属于案例假设；未验证真实切削、材料失效或工业安全性。

MIT声明覆盖本仓库源代码及可再分发的案例内容；运行MAPDL需要使用者自己的安装和许可。
