#!/usr/bin/env python3
"""
使用虚拟环境 + Nuitka + UPX 优化打包微生物菌落计数器

此脚本实现了用户提出的优化方案：
1. 创建独立的虚拟环境
2. 使用Nuitka编译替代PyInstaller打包
3. 使用UPX压缩进一步减小文件大小
"""

import os
import sys
import subprocess
import platform
import shutil
import urllib.request
import zipfile

def create_virtual_environment():
    """创建干净的虚拟环境"""
    print("🔧 创建虚拟环境...")
    
    # 如果虚拟环境已存在，先删除
    if os.path.exists("venv"):
        print("🗑️ 清理旧的虚拟环境...")
        try:
            shutil.rmtree("venv")
        except Exception as e:
            print(f"⚠️ 删除旧虚拟环境时出错: {e}")
    
    try:
        subprocess.check_call([sys.executable, "-m", "venv", "venv"])
        print("✅ 虚拟环境创建完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 虚拟环境创建失败: {e}")
        return False

def install_minimal_dependencies():
    """在虚拟环境中只安装必要依赖"""
    print("📦 安装必要依赖...")
    
    # 根据操作系统确定虚拟环境中的Python路径
    if platform.system() == "Windows":
        python_path = os.path.join("venv", "Scripts", "python.exe")
    else:
        python_path = os.path.join("venv", "bin", "python")
    
    try:
        # 升级pip
        subprocess.check_call([python_path, "-m", "pip", "install", "--upgrade", "pip"])
        
        # 只安装运行必需的依赖
        subprocess.check_call([python_path, "-m", "pip", "install", "opencv-python", "numpy", "Pillow"])
        
        # 安装Nuitka用于编译
        subprocess.check_call([python_path, "-m", "pip", "install", "nuitka"])
        print("✅ 必要依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False

def download_and_setup_upx():
    """下载并设置UPX"""
    print("📥 设置UPX压缩工具...")
    
    # 检查系统架构
    system = platform.system()
    
    try:
        if system == "Windows":
            # 检查是否已经存在UPX
            upx_exe = os.path.join(".", "upx.exe")  # 在当前目录查找
            if os.path.exists(upx_exe):
                print("✅ UPX已存在")
                return True
                
            # 下载UPX for Windows
            print("正在下载UPX for Windows...")
            upx_url = "https://github.com/upx/upx/releases/download/v4.2.4/upx-4.2.4-win64.zip"
            upx_zip_path = "upx.zip"
            urllib.request.urlretrieve(upx_url, upx_zip_path)
            
            # 解压
            with zipfile.ZipFile(upx_zip_path, 'r') as zip_ref:
                zip_ref.extractall(".")
            
            # 找到解压后的目录并将upx.exe复制到当前目录
            for item in os.listdir("."):
                if item.startswith("upx-") and os.path.isdir(item):
                    extracted_dir = item
                    upx_exe_src = os.path.join(extracted_dir, "upx.exe")
                    upx_exe_dst = "upx.exe"
                    if os.path.exists(upx_exe_src):
                        shutil.copy2(upx_exe_src, upx_exe_dst)
                        # 删除解压的目录
                        shutil.rmtree(extracted_dir)
                    break
            
            # 清理下载的zip文件
            if os.path.exists(upx_zip_path):
                os.remove(upx_zip_path)
            
        elif system in ["Linux", "Darwin"]:  # Linux or macOS
            # 对于Linux/macOS，建议用户自行安装UPX
            print("💡 对于Linux/macOS系统，请手动安装UPX:")
            print("   Ubuntu/Debian: sudo apt-get install upx")
            print("   CentOS/RHEL: sudo yum install upx")
            print("   macOS: brew install upx")
            return shutil.which("upx") is not None
        
        if os.path.exists("upx.exe") or (system != "Windows" and shutil.which("upx")):
            print("✅ UPX设置完成")
            return True
        else:
            print("⚠️ UPX设置失败")
            return False
    except Exception as e:
        print(f"❌ UPX设置失败: {e}")
        print("💡 提示: 没有UPX也能正常打包，但文件会稍大一些")
        return False

def build_with_nuitka():
    """使用Nuitka编译打包"""
    print("🔨 使用Nuitka编译打包...")
    
    # 根据操作系统确定虚拟环境中的Python路径
    if platform.system() == "Windows":
        python_path = os.path.join("venv", "Scripts", "python.exe")
    else:
        python_path = os.path.join("venv", "bin", "python")
    
    # 清理之前的构建输出
    if os.path.exists("dist_optimized"):
        try:
            shutil.rmtree("dist_optimized")
        except Exception as e:
            print(f"⚠️ 清理旧输出目录时出错: {e}")
    
    # 构建Nuitka命令
    cmd = [
        python_path, "-m", "nuitka",
        "--standalone",                     # 独立模式
        "--windows-console-mode=disable",   # 禁用控制台窗口 (新选项)
        "--enable-plugin=tk-inter",         # 启用tkinter插件
        "--output-dir=dist_optimized",      # 输出目录
        "--onefile",                        # 单文件模式
        "--remove-output",                  # 构建完成后删除构建目录
    ]
    
    # 添加主程序文件
    cmd.append("main.py")
    
    try:
        print(f"执行命令: {' '.join(cmd)}")
        # 使用环境变量来自动同意Nuitka下载编译器
        env = os.environ.copy()
        env["NUITKA_DOWNLOADS_ENABLED"] = "1"
        subprocess.check_call(cmd, env=env)
        
        # 如果UPX存在，对生成的exe文件进行压缩
        if platform.system() == "Windows" and os.path.exists("upx.exe"):
            print("📦 使用UPX压缩生成的可执行文件...")
            exe_files = []
            for root, dirs, files in os.walk("dist_optimized"):
                for file in files:
                    if file.endswith(".exe"):
                        exe_files.append(os.path.join(root, file))
            
            for exe_file in exe_files:
                try:
                    upx_cmd = ["upx.exe", "-9", exe_file]
                    print(f"执行命令: {' '.join(upx_cmd)}")
                    subprocess.check_call(upx_cmd)
                except subprocess.CalledProcessError as e:
                    print(f"⚠️ UPX压缩失败: {e}")
        
        print("✅ Nuitka编译打包完成！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Nuitka编译打包失败: {e}")
        return False
    except FileNotFoundError:
        print("❌ 未找到Nuitka，请确保已正确安装")
        return False

def compare_file_sizes():
    """比较文件大小"""
    print("📊 比较文件大小...")
    
    # 查找生成的可执行文件
    exe_files = []
    
    # 原始文件
    original_exe = "微生物菌落计数器.exe"
    if os.path.exists(original_exe):
        original_size = os.path.getsize(original_exe)
        exe_files.append(("原始版本", original_exe, original_size))
    
    # 优化后的文件 (根据不同系统查找)
    optimized_exe = None
    if platform.system() == "Windows":
        # 检查几种可能的输出文件名
        possible_names = [
            os.path.join("dist_optimized", "main.exe"),
            os.path.join("dist_optimized", "微生物菌落计数器.exe"),
            os.path.join("dist_optimized", "main.dist", "main.exe"),
        ]
        for name in possible_names:
            if os.path.exists(name):
                optimized_exe = name
                break
    
    if optimized_exe and os.path.exists(optimized_exe):
        optimized_size = os.path.getsize(optimized_exe)
        exe_files.append(("优化版本", optimized_exe, optimized_size))
    
    if len(exe_files) >= 1:
        print("\n📈 文件大小对比:")
        print("-" * 50)
        for name, path, size in exe_files:
            size_mb = size / (1024 * 1024)
            print(f"{name:8}: {path}")
            print(f"          大小: {size_mb:.2f} MB ({size:,} 字节)")
            print()
        
        # 如果两个文件都存在，计算减小的大小
        if len(exe_files) >= 2:
            reduction = exe_files[0][2] - exe_files[1][2]
            reduction_percent = (reduction / exe_files[0][2]) * 100
            print(f"✅ 优化效果: 减小了 {reduction_percent:.1f}%")
            print(f"   文件大小从 {exe_files[0][2]/(1024*1024):.2f} MB 减小到 {exe_files[1][2]/(1024*1024):.2f} MB")
            print(f"   减少了 {reduction/(1024*1024):.2f} MB")
    else:
        print("⚠️ 未找到可执行文件进行比较")

def main():
    """主函数"""
    print("🚀 微生物菌落计数器优化打包工具")
    print("=" * 50)
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"Python版本: {sys.version}")
    print()
    
    # 检查主文件是否存在
    if not os.path.exists("main.py"):
        print("❌ 错误: 未找到main.py文件")
        return
    
    print("开始执行优化打包流程:")
    print()
    
    # 1. 创建虚拟环境
    print("步骤 1/5: 创建虚拟环境")
    if not create_virtual_environment():
        print("❌ 流程中断: 虚拟环境创建失败")
        return
    
    # 2. 安装最小依赖集
    print("\n步骤 2/5: 安装必要依赖")
    if not install_minimal_dependencies():
        print("❌ 流程中断: 依赖安装失败")
        return
    
    # 3. 设置UPX
    print("\n步骤 3/5: 设置UPX压缩工具")
    download_and_setup_upx()  # 即使失败也继续，因为这是可选的
    
    # 4. 使用Nuitka编译
    print("\n步骤 4/5: 使用Nuitka编译")
    if not build_with_nuitka():
        print("❌ 流程中断: Nuitka编译失败")
        print("\n💡 解决方案建议:")
        print("   1. 检查网络连接，确保可以访问Nuitka的编译器下载服务器")
        print("   2. 手动下载并安装MinGW-w64编译器")
        print("   3. 尝试使用 --mingw64 参数指定已安装的编译器")
        print("   4. 或者使用默认的打包方式: python build.py")
        return
    
    # 5. 比较文件大小
    print("\n步骤 5/5: 比较优化效果")
    compare_file_sizes()
    
    print("\n🎉 优化打包完成！")
    print("📁 优化版可执行文件位于: dist_optimized/")
    print("\n💡 优化方案说明:")
    print("   1. 使用独立虚拟环境，只包含必要的运行依赖")
    print("   2. 使用Nuitka编译替代PyInstaller打包，提高执行效率")
    print("   3. 使用UPX压缩进一步减小可执行文件大小")
    print("   4. 移除未使用的模块和调试信息")

if __name__ == "__main__":
    main()