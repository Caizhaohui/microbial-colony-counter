# 微生物菌落计数器

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)](https://opencv.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个功能强大的微生物培养皿菌落自动计数工具，具有直观的图形界面和精确的图像处理算法。

## ✨ 功能特点

- 🖼️ **多格式支持**：支持JPG、PNG、BMP、TIFF等多种图片格式
- 🔍 **智能计数**：基于OpenCV的先进图像处理算法自动检测和计数菌落
- ⚙️ **参数调节**：提供丰富的参数调整选项，适应不同类型的培养皿
- 🎯 **区域选择**：支持手动选择统计区域（矩形/圆形），可拖拽调整
- 🧫 **培养皿检测**：自动检测培养皿圆形区域，排除背景干扰
- 💧 **分水岭算法**：可选启用分水岭算法自动分离粘连菌落
- 🔵 **圆度过滤**：通过圆度参数过滤非圆形杂质，提高计数准确性
- 📊 **实时显示**：处理过程中实时显示二值化和计数结果
- 📝 **菌落详情**：可查看每个菌落的编号、坐标、面积、圆度等详细信息
- 💾 **结果保存**：可保存包含原始图片、二值化图片和计数结果的统计报告
- 🎨 **美观界面**：精心设计的用户界面，操作直观简单
- 📱 **Web App 支持**：支持通过手机浏览器远程访问，方便在实验室移动使用
- ⚡ **性能优化**：缩略图传输 + JPEG压缩 + 异步线程池，低配电脑也能流畅运行

## 🚀 快速开始

### 方法一：运行桌面版（需要Python环境）

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **运行桌面版程序**
   ```bash
   python main.py
   ```

### 方法二：运行 Web 版（推荐）

1. **安装依赖并启动**
   ```bash
   pip install -r requirements.txt
   python web_launcher.py
   ```
   或者 Windows 下双击 `run_gui.bat`

2. **操作说明**
   - 点击界面上的 "启动服务" 按钮
   - 看到 "本机访问" 和 "手机访问" 地址
   - 手机和电脑在同一局域网时，手机扫描或输入地址即可使用

### 方法三：使用打包的可执行文件

1. **打包程序**
   ```bash
   python build.py
   ```

2. **运行可执行文件**
   - Windows: 双击 `dist/微生物菌落计数器.exe`

### 方法四：优化打包（减小文件大小）

使用虚拟环境 + Nuitka + UPX 的优化方案：

```bash
python optimize_build.py
```

## 📖 使用指南

### 基本操作流程

1. **选择图片**：点击"选择图片"按钮，选择培养皿图片文件
2. **调整参数**：根据图片特点调整各项参数
3. **选择区域**（可选）：点击"选择区域"手动指定统计范围
4. **处理图片**：点击"处理图片"开始分析
5. **查看结果**：查看计数结果和统计信息
6. **保存结果**（可选）：点击"保存结果"保存统计报告

### 参数说明

#### 1. 图像预处理
- **高斯模糊核大小**：去噪参数，建议3-15之间的奇数
- **二值化方法**：
  - 手动阈值：手动设置阈值
  - 自适应阈值：自动适应图片亮度变化

#### 2. 培养皿检测
- **自动检测培养皿圆形区域**：启用后只统计培养皿内的菌落

#### 3. 菌落过滤
- **最小面积**：过滤掉过小的噪点
- **最大面积**：过滤掉过大的非菌落物体
- **边缘距离**：避免统计边缘附近的菌落

#### 4. 高级选项
- **分水岭算法**：可选启用，自动分离粘连菌落（注意：可能导致过分割）
- **圆度过滤**：设置最小圆度阈值(0~0.9)，过滤非圆形杂质

### 手动选择区域

1. 点击"选择区域"按钮
2. 选择形状（圆形/矩形）
3. 在图片上拖拽选择区域
4. 确认选择后开始处理

## 🛠️ 开发环境

### 系统要求

- **Python**: 3.7+
- **操作系统**:
  - Windows 7/8/10/11
  - macOS 10.12+
  - Linux (Ubuntu 16.04+)

### 依赖包

```
opencv-python>=4.5.0
numpy>=1.19.0
Pillow>=8.0.0
fastapi>=0.68.0
uvicorn>=0.15.0
psutil>=5.8.0
```

### 安装开发环境

```bash
# 克隆项目
git clone https://github.com/Caizhaohui/microbial-colony-counter.git
cd microbial-colony-counter

# 安装依赖
pip install -r requirements.txt
```

## 🏗️ 项目结构

```
microbial-colony-counter/
├── backend/            # Web App 后端代码 (FastAPI)
│   ├── core/           # 核心图像处理算法 (OpenCV)
│   ├── static/         # Web 前端 (HTML/CSS/JS)
│   ├── main.py         # FastAPI 应用入口
│   └── schemas.py      # API 数据模型 (Pydantic)
├── main.py             # 桌面版主程序 (Tkinter GUI)
├── web_launcher.py     # Web App GUI 启动器
├── run_gui.bat         # 一键启动脚本
├── build.py            # 打包脚本
├── requirements.txt    # 依赖列表
└── README.md           # 项目说明
```

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📋 更新日志

### v1.0.0 (2026-06-03)
- ✨ 首个正式版本发布
- 🎯 Web 版与桌面版算法完全对齐
- 💧 新增分水岭算法分离粘连菌落
- 🔵 新增圆度过滤功能
- 📝 新增菌落详情表格展示
- ⚡ 性能优化：缩略图传输、JPEG压缩、异步线程池
- 🎨 Web 前端新增高级选项面板

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 联系方式

- 项目维护者: [Zhaohui Cai]
- 邮箱: [cai_zhaohui@163.com]

---
**享受使用微生物菌落计数器！** 🧫🔬
