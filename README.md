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
- 📊 **实时显示**：处理过程中实时显示二值化和计数结果
- 💾 **结果保存**：可保存包含原始图片、二值化图片和计数结果的统计报告
- 🎨 **美观界面**：精心设计的用户界面，操作直观简单

## 🚀 快速开始

### 方法一：直接运行（需要Python环境）

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **运行程序**
   ```bash
   python main.py
   ```

### 方法二：使用打包的可执行文件（推荐）

1. **打包程序**
   ```bash
   python build.py
   ```

2. **运行可执行文件**
   - Windows: 双击 `dist/微生物菌落计数器.exe`
   - macOS/Linux: 运行 `dist/微生物菌落计数器`

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
pyinstaller>=4.0.0  # 仅打包时需要
```

### 安装开发环境

```bash
# 克隆项目
git clone <repository-url>
cd colony-counter

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

## 📦 项目打包

### 自动打包

运行打包脚本：
```bash
python build.py
```

### 手动打包

使用PyInstaller：
```bash
pyinstaller --onefile --windowed --name "微生物菌落计数器" main.py
```

### 打包选项说明

- `--onefile`: 打包成单个可执行文件
- `--windowed`: 隐藏控制台窗口（GUI应用）
- `--name`: 指定可执行文件名称

## 🏗️ 项目结构

```
colony-counter/
├── main.py              # 主程序文件
├── build.py             # 打包脚本
├── requirements.txt     # 依赖列表
├── README.md           # 项目说明
├── 使用说明.txt         # 生成的使用说明
└── dist/               # 打包输出目录
    └── 微生物菌落计数器.exe  # 可执行文件
```

## 🔧 技术实现

- **GUI框架**: Tkinter
- **图像处理**: OpenCV + NumPy
- **打包工具**: PyInstaller
- **图像显示**: PIL (Pillow)

### 核心算法

1. **图像预处理**: 高斯模糊去噪
2. **二值化**: 手动/自适应阈值分割
3. **形态学处理**: 轮廓检测和过滤
4. **几何分析**: 面积和位置过滤
5. **结果可视化**: 轮廓标记和编号

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

### 开发流程

1. Fork本项目
2. 创建特性分支: `git checkout -b feature/AmazingFeature`
3. 提交更改: `git commit -m 'Add some AmazingFeature'`
4. 推送分支: `git push origin feature/AmazingFeature`
5. 创建Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 联系方式

- 项目维护者: [您的姓名]
- 邮箱: [您的邮箱]
- 项目主页: [项目地址]

## 🙏 致谢

- OpenCV社区提供的优秀图像处理库
- Python科学计算生态系统
- 所有贡献者和用户

---

**享受使用微生物菌落计数器！** 🧫🔬
