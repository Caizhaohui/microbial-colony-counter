#!/usr/bin/env python3
"""
微生物菌落计数器打包脚本

使用PyInstaller将Python项目打包成可执行文件

使用方法:
1. 确保已安装所有依赖: pip install -r requirements.txt
2. 运行此脚本: python build.py
3. 可执行文件将在dist目录中生成
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def install_dependencies():
    """安装项目依赖"""
    print("📦 安装项目依赖...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ 依赖安装完成")
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False
    return True

def build_executable():
    """使用PyInstaller打包可执行文件"""
    print("🔨 开始打包可执行文件...")

    # 确定PyInstaller命令
    if platform.system() == "Windows":
        pyinstaller_cmd = "pyinstaller"
    else:
        pyinstaller_cmd = "pyinstaller"

    # PyInstaller参数
    # --onefile: 打包成单个可执行文件
    # --windowed: Windows下隐藏控制台窗口
    # --name: 可执行文件名称
    # --icon: 图标文件（如果有的话）
    # --add-data: 添加额外数据文件

    cmd = [
        pyinstaller_cmd,
        "--onefile",  # 打包成单个文件
        "--windowed",  # 隐藏控制台窗口（GUI应用）
        "--name", "微生物菌落计数器",  # 可执行文件名称
        "--clean",  # 清理临时文件
        "main.py"
    ]

    try:
        print(f"执行命令: {' '.join(cmd)}")
        subprocess.check_call(cmd)
        print("✅ 打包完成！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 打包失败: {e}")
        return False
    except FileNotFoundError:
        print("❌ 未找到PyInstaller，请确保已正确安装")
        return False

def create_shortcut_info():
    """创建快捷方式和使用说明"""
    print("📝 创建使用说明...")

    readme_content = """# 微生物菌落计数器

一个用于自动计数微生物培养皿中菌落的图像处理工具。

## 功能特点

- 🖼️ 支持多种图片格式（JPG、PNG、BMP、TIFF）
- 🔍 自动菌落检测和计数
- ⚙️ 可调节的参数设置（模糊、阈值、面积过滤等）
- 🎯 支持手动选择统计区域（矩形/圆形）
- 🧫 自动检测培养皿圆形区域
- 💾 保存统计结果图片
- 📊 实时显示计数结果

## 使用方法

1. 启动程序后，点击"选择图片"按钮选择培养皿图片
2. 根据需要调整参数设置：
   - 高斯模糊核大小
   - 二值化方法（手动/自适应）
   - 菌落面积范围
   - 边缘距离过滤
3. 可选择"选择区域"手动指定统计范围
4. 点击"处理图片"开始分析
5. 查看结果并可保存统计图片

## 系统要求

- Windows 7/8/10/11
- macOS 10.12+
- Linux (Ubuntu 16.04+)

## 技术支持

如有问题请联系开发者。

---
由PyInstaller打包生成
"""

    try:
        with open("使用说明.txt", "w", encoding="utf-8") as f:
            f.write(readme_content)
        print("✅ 使用说明文件创建完成")
    except Exception as e:
        print(f"❌ 创建使用说明失败: {e}")

def main():
    """主函数"""
    print("🚀 微生物菌落计数器打包工具")
    print("=" * 50)

    # 检查Python版本
    print(f"Python版本: {sys.version}")
    print(f"操作系统: {platform.system()} {platform.release()}")

    # 检查是否存在主文件
    if not os.path.exists("main.py"):
        print("❌ 未找到main.py文件")
        return

    if not os.path.exists("requirements.txt"):
        print("❌ 未找到requirements.txt文件")
        return

    print()

    # 安装依赖
    if not install_dependencies():
        return

    print()

    # 打包可执行文件
    if not build_executable():
        return

    print()

    # 创建使用说明
    create_shortcut_info()

    print()
    print("🎉 打包完成！")
    print("📁 可执行文件位于: dist/微生物菌落计数器.exe" if platform.system() == "Windows" else "dist/微生物菌落计数器")
    print("📖 使用说明文件: 使用说明.txt")
    print()
    print("💡 提示:")
    print("   - 可执行文件可以直接分发给其他人使用")
    print("   - 无需安装Python或其他依赖")
    print("   - 首次运行可能需要一些时间来加载")

if __name__ == "__main__":
    main()
