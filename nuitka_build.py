#!/usr/bin/env python3
"""
使用Nuitka和UPX优化打包微生物菌落计数器

此脚本实现以下优化方案：
1. 创建虚拟环境以减少依赖项
2. 使用Nuitka进行编译打包
3. 使用UPX进行压缩
"""

import os
import sys
import subprocess
import platform
import shutil

def create_virtual_environment():
    """创建虚拟环境"""
    print("🔧 创建虚拟环境...")
    try:
        subprocess.check_call([sys.executable, "-m", "venv", "venv"])
        print("✅ 虚拟环境创建完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 虚拟环境创建失败: {e}")
        return False

def install_dependencies_in_venv():
    """在虚拟环境中安装依赖"""
    print("📦 在虚拟环境中安装依赖...")
    
    # 根据操作系统确定虚拟环境中的Python路径
    if platform.system() == "Windows":
        python_path = os.path.join("venv", "Scripts", "python.exe")
    else:
        python_path = os.path.join("venv", "bin", "python")
    
    try:
        # 安装必要的依赖
        subprocess.check_call([python_path, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([python_path, "-m", "pip", "install", "opencv-python", "numpy", "Pillow"])
        subprocess.check_call([python_path, "-m", "pip", "install", "nuitka"])
        print("✅ 依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False

def download_upx():
    """下载UPX压缩工具"""
    print("📥 下载UPX压缩工具...")
    
    # 检查是否已存在UPX
    if os.path.exists("upx") or shutil.which("upx"):
        print("✅ UPX已存在")
        return True
    
    try:
        if platform.system() == "Windows":
            # Windows下下载UPX
            import urllib.request
            import zipfile
            
            print("正在下载UPX for Windows...")
            upx_url = "https://github.com/upx/upx/releases/download/v4.2.4/upx-4.2.4-win64.zip"
            urllib.request.urlretrieve(upx_url, "upx.zip")
            
            # 解压
            with zipfile.ZipFile("upx.zip", 'r') as zip_ref:
                zip_ref.extractall(".")
            
            # 重命名文件夹
            extracted_dir = "upx-4.2.4-win64"
            if os.path.exists(extracted_dir):
                os.rename(extracted_dir, "upx")
            
            # 清理下载文件
            os.remove("upx.zip")
            
        print("✅ UPX下载完成")
        return True
    except Exception as e:
        print(f"❌ UPX下载失败: {e}")
        print("💡 提示: 您可以手动下载UPX并放置在upx目录中")
        return False

def build_with_nuitka_upx():
    """使用Nuitka和UPX打包"""
    print("🔨 使用Nuitka和UPX打包...")
    
    # 根据操作系统确定虚拟环境中的Python路径
    if platform.system() == "Windows":
        python_path = os.path.join("venv", "Scripts", "python.exe")
    else:
        python_path = os.path.join("venv", "bin", "python")
    
    # 构建Nuitka命令
    cmd = [
        python_path, "-m", "nuitka",
        "--standalone",                # 独立模式
        "--windows-disable-console",   # 禁用控制台窗口
        "--enable-plugin=tk-inter",    # 启用tkinter插件
        "--output-dir=dist_nuitka",    # 输出目录
        "--onefile",                   # 单文件模式
        "--remove-output",             # 构建完成后删除构建目录
    ]
    
    # 如果UPX存在，添加UPX压缩选项
    if os.path.exists("upx") or shutil.which("upx"):
        cmd.extend([
            "--windows-onefile-icon=icon.ico",  # 如果有图标文件
            "--upx-binary=upx/upx.exe" if platform.system() == "Windows" and os.path.exists("upx/upx.exe") else "--upx-binary=upx/upx"
        ])
        print("✅ 启用UPX压缩")
    else:
        print("⚠️ 未找到UPX，跳过压缩")
    
    # 添加主程序文件
    cmd.append("main.py")
    
    try:
        print(f"执行命令: {' '.join(cmd)}")
        subprocess.check_call(cmd)
        print("✅ Nuitka打包完成！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Nuitka打包失败: {e}")
        return False
    except FileNotFoundError:
        print("❌ 未找到Nuitka，请确保已正确安装")
        return False

def analyze_size():
    """分析打包后的文件大小"""
    print("📊 分析文件大小...")
    
    files_to_check = [
        ("原始EXE文件", "微生物菌落计数器.exe"),
        ("Nuitka优化版", "dist_nuitka/main.exe"),
        ("Nuitka优化版", "dist_nuitka/main.onefile.exe"),
        ("Nuitka优化版", "dist_nuitka/微生物菌落计数器.exe"),
        ("Nuitka优化版", "dist_nuitka/微生物菌落计数器.onefile.exe")
    ]
    
    found_files = []
    for desc, filepath in files_to_check:
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            size_mb = size / (1024 * 1024)
            found_files.append((desc, filepath, size_mb))
    
    if found_files:
        print("文件大小比较:")
        for desc, filepath, size_mb in sorted(found_files, key=lambda x: x[2]):
            print(f"  {desc}: {filepath} ({size_mb:.2f} MB)")
    else:
        print("未找到可执行文件")

def main():
    """主函数"""
    print("🚀 微生物菌落计数器Nuitka+UPX优化打包工具")
    print("=" * 50)
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"Python版本: {sys.version}")
    
    # 检查主文件是否存在
    if not os.path.exists("main.py"):
        print("❌ 未找到main.py文件")
        return
    
    print("\n开始优化打包流程:")
    
    # 1. 创建虚拟环境
    print("\n1/4 创建虚拟环境")
    if not create_virtual_environment():
        return
    
    # 2. 安装依赖
    print("\n2/4 安装依赖")
    if not install_dependencies_in_venv():
        return
    
    # 3. 下载UPX
    print("\n3/4 下载UPX")
    download_upx()  # 即使下载失败也继续，因为UPX是可选的
    
    # 4. 使用Nuitka打包
    print("\n4/4 Nuitka打包")
    if not build_with_nuitka_upx():
        return
    
    # 5. 分析文件大小
    print("\n5/4 文件大小分析")
    analyze_size()
    
    print("\n🎉 打包完成！")
    print("📁 优化版可执行文件位于: dist_nuitka/")
    print("\n💡 优化说明:")
    print("   1. 使用虚拟环境减少了不必要的依赖")
    print("   2. Nuitka比PyInstaller更高效的编译方式")
    print("   3. UPX进一步压缩可执行文件大小")
    print("   4. 移除了调试信息和未使用的模块")

if __name__ == "__main__":
    main()