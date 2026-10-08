# 上传到自己的 GitHub

## 1. 创建空仓库

登录 GitHub，创建仓库，推荐名称 `lathe-cutter-pymapdl-portfolio`。需要求职展示时可选 Public。描述建议：

> PyMAPDL lathe-cutter reproduction and verification: mesh studies, parameter sweeps, force audit, and thermal–structural teaching demo.

创建时不勾选自动生成 README、.gitignore 或许可证，以便直接推送本地已整理的文件。不要把整个历史工作文件夹上传；使用本 GitHub 包的顶层内容。

## 2. 本地验证与提交

解压上传包，进入有 README.md 的仓库根目录。若该目录已经有 `.git`，可跳过 `git init`：

```powershell
git init -b main
python verify_evidence.py
python -m unittest discover -s tests -v
git status --short
git add .
git diff --cached --check
git commit -m "Add reproducible PyMAPDL portfolio and verified results"
```

如果 Git 提示缺少提交身份，请用自己的姓名和邮箱设置本仓库身份，再重新提交：

```powershell
$authorName = Read-Host '输入提交姓名'
$authorEmail = Read-Host '输入 GitHub 提交邮箱或个人 noreply 邮箱'
git config user.name $authorName
git config user.email $authorEmail
git commit -m "Add reproducible PyMAPDL portfolio and verified results"
```

`.gitignore` 已排除虚拟环境、运行输出、原生 DB/RST、缓存及常见环境配置。提交前检查暂存清单，确认没有个人配置或 ANSYS 安装文件。原始几何和第三方许可需要保留。

## 3. 连接并推送

在新仓库页面复制 HTTPS 仓库地址：

```powershell
$repoUrl = Read-Host '粘贴新建仓库的 HTTPS 地址'
git remote add origin $repoUrl
git push -u origin main
```

按 Git 的凭据管理流程登录，不要把密码或 token 写入脚本、README 或聊天。如果已有 origin，先用 `git remote -v` 检查；确认需要更换时再执行 `git remote set-url origin $repoUrl`。如果远端不是空仓库，先检查其已有内容，不使用强制推送覆盖。

## 4. 检查展示效果

1. 打开仓库主页，确认 README 中三张图和文档链接正常。
2. 在 Actions 查看离线检查；这只校验公开数据和脚本，不运行 ANSYS。
3. 下载 PDF，核对 27 页项目报告。HTML 相册需要下载仓库后本地打开。
4. 在 About 添加主题：`pymapdl`、`ansys`、`finite-element-analysis`、`python`、`mesh-convergence`、`engineering-portfolio`。
5. 将仓库固定到个人主页。简历链接指向仓库首页，同时准备演示工作网格、细网格研究、反力核对和峰值边界区域。

## 5. 后续更新

仅修改仓库首页 `README.md` 时，可以直接在 GitHub 网页编辑并提交，无需重新生成哈希清单。README 不属于冻结的计算证据；脚本、计算数据、图片和其他文档仍受完整性校验保护。

每次修改脚本或公开证据，完成检查后更新文件清单再提交：

```powershell
python verify_evidence.py --skip-manifest
python build_manifest.py
python verify_evidence.py
python -m unittest discover -s tests -v
git add .
git diff --cached --check
git commit -m "Describe the actual completed change"
git push
```

新计算输出默认留在 `results/`。挑选有解释价值的成果加入新证据目录，再更新 README、数量检查与来源记录。不要仅凭新云图替换原结论，先检查输入、数据和收敛性。
