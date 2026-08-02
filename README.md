# 微生物菌落计数器

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)](https://opencv.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Release-v1.1.1-orange.svg)](https://github.com/Caizhaohui/microbial-colony-counter/releases)

一个功能强大的微生物培养皿菌落自动计数工具，支持桌面 GUI、Web 局域网访问，以及 **批次标定学习**（参考盘真值 → 批量计数）。

**仓库**: [https://github.com/Caizhaohui/microbial-colony-counter](https://github.com/Caizhaohui/microbial-colony-counter)

## ✨ 功能特点

- 🖼️ **多格式支持**：JPG、PNG、BMP、TIFF 等
- 🔍 **智能计数**：基于 OpenCV 的图像处理自动检测与计数
- ⚙️ **参数调节**：模糊、阈值、面积、边缘距离等，适应不同培养皿
- 🎯 **区域选择**：手动矩形/圆形 ROI，可拖拽调整
- 🧫 **培养皿检测**：自动检测圆形培养皿区域
- 💧 **分水岭算法**：可选分离粘连菌落
- 🔵 **圆度过滤**：过滤非圆形杂质
- 📊 **实时显示**：二值化与标注结果实时预览
- 📝 **菌落详情**：编号、坐标、面积、圆度
- 💾 **结果保存**：统计报告图片
- 📱 **Web App**：手机浏览器局域网访问
- ⚡ **性能优化**：缩略图传输 + JPEG 压缩 + 异步线程池
- 📦 **批次标定（v1.1.1）**：参考盘学习本批次参数，批量处理其余平板

## 🚀 快速开始

### 方法一：桌面版

```bash
pip install -r requirements.txt
python main.py
```

工具栏 **「📦 批次标定」** 可打开批次学习工作台（见下文）。

### 方法二：Web 版

```bash
pip install -r requirements.txt
python web_launcher.py
```

Windows 也可双击 `run_gui.bat` / `start_web_app.bat`。

1. 点击「启动服务」
2. 使用本机或手机访问显示的地址（同一局域网）

### 方法三：打包可执行文件

```bash
python build.py
# 或优化打包
python optimize_build.py
```

输出位于 `dist/`。

## 📦 批次标定（电脑端）

同一次实验要数 **多块平板** 时，先用一块参考盘提供真值，软件搜索本批次最优参数，再批量计数其余平板。

### 三种策略

| 策略 | 操作 | 适用场景 |
|------|------|----------|
| **1. 部分点选 + 总数** | 左键点 ≥5 个典型菌落，并填写整盘人工总数 N | 推荐：有位置信息，又不必点完全部 |
| **2. 全量点选** | 在图上点完所有菌落（N = 点数） | 真值最可靠，适合参考盘精标 |
| **3. 图片 + 菌落数** | 不点选，只填写人工总数 N | 最快；无位置约束，拍照条件需尽量一致 |

### 操作步骤

1. 运行 `python main.py`，点击 **「📦 批次标定」**
2. **加载参考盘** 图片，选择策略并完成真值采集
3. 点击 **「开始学习 / 标定」**，查看拟合误差与参数 θ*
4. **添加其余平板** → **批量计数** → 导出 CSV / 保存参数 JSON
5. 可选：**应用到主窗口参数**，继续用原有单图自动计数

**点选操作**：左键加点 · 右键删除最近点 · Ctrl+Z 撤销 · 可导出点 JSON / 标注图

> 标定按 **批次** 有效；更换菌种、培养基或拍照条件后请重新标定。  
> 详细设计见 [`开发计划-批次标定.md`](开发计划-批次标定.md)。

### 相关模块

- `backend/core/calibrator.py` — 三策略参数搜索
- `backend/core/batch.py` — 批量应用参数
- `backend/core/pointset.py` — 点集与标注绘制
- `batch_workbench.py` — 桌面工作台 UI

### 命令行冒烟测试

```bash
python backend/test_calibrator.py
```

## 📖 使用指南（单图自动计数）

1. **选择图片** → 按需调整参数  
2. **选择区域**（可选）→ **处理图片**  
3. 查看结果 → **保存结果**（可选）

### 参数说明

| 类别 | 参数 | 说明 |
|------|------|------|
| 预处理 | 高斯模糊核 | 去噪，建议 3–15 奇数 |
| 二值化 | 手动 / 自适应 | 自适应更适合光照不均 |
| 培养皿 | 自动检测圆 | 只统计皿内菌落 |
| 过滤 | 最小/最大面积、边缘距离 | 去噪点与边缘伪影 |
| 高级 | 分水岭、最小圆度 | 粘连分离与形状过滤 |

## 🛠️ 开发环境

- **Python** 3.7+
- **系统**：Windows 7+ / macOS 10.12+ / Linux

```text
opencv-python>=4.5.0
numpy>=1.19.0
Pillow>=8.0.0
fastapi>=0.68.0
uvicorn>=0.15.0
psutil>=5.8.0
```

```bash
git clone https://github.com/Caizhaohui/microbial-colony-counter.git
cd microbial-colony-counter
pip install -r requirements.txt
```

Web 后端额外依赖见 `backend/requirements.txt`。

## 🏗️ 项目结构

```text
microbial-colony-counter/
├── backend/
│   ├── core/
│   │   ├── algorithm.py      # 核心计数算法
│   │   ├── calibrator.py     # 批次参数标定
│   │   ├── batch.py          # 批量计数
│   │   └── pointset.py       # 点集工具
│   ├── static/index.html     # Web 前端
│   ├── main.py               # FastAPI 入口
│   ├── schemas.py
│   └── test_*.py
├── main.py                   # 桌面版主程序
├── batch_workbench.py        # 批次标定工作台
├── web_launcher.py           # Web 启动器
├── build.py / optimize_build.py
├── 开发计划-批次标定.md
├── requirements.txt
└── README.md
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。

## 📋 更新日志

### v1.1.1 (2026-08-02)

- ✨ **电脑端批次标定工作台**：部分点选 / 全量点选 / 仅填总数
- ✨ 批量计数、CSV 导出、参数 JSON 存档
- ✨ 标定参数一键应用到主窗口
- 🧩 新增 `calibrator` / `batch` / `pointset` 核心模块
- 📄 新增开发计划文档，完善 README

### v1.0.0 (2026-06-03)

- ✨ 首个正式版本
- 🎯 Web 与桌面算法对齐
- 💧 分水岭分离粘连菌落
- 🔵 圆度过滤、菌落详情
- ⚡ 缩略图传输、JPEG 压缩、异步线程池
- 🎨 Web 高级选项面板

## 📄 许可证

[MIT License](LICENSE)

## 📞 联系方式

- 维护者：Zhaohui Cai
- 邮箱：cai_zhaohui@163.com

---

**享受使用微生物菌落计数器！** 🧫🔬
