import os
import subprocess
import sys
import shutil

def build_with_pyinstaller():
    """使用PyInstaller打包，但进行优化以减小文件大小"""
    print("🔨 使用PyInstaller优化打包...")
    
    # 清理之前的构建
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")
    
    # PyInstaller命令，添加优化选项
    cmd = [
        "pyinstaller",
        "--onefile",                     # 单文件模式
        "--windowed",                    # 无控制台窗口
        "--name", "微生物菌落计数器",          # 可执行文件名
        "--exclude-module", "tkinter.test",     # 排除不必要的模块
        "--exclude-module", "unittest",         # 排除测试模块
        "--exclude-module", "pydoc",            # 排除文档模块
        "--exclude-module", "pdb",              # 排除调试模块
        "--exclude-module", "matplotlib",       # 排除matplotlib（如果未使用）
        "--exclude-module", "scipy",            # 排除scipy（如果未使用）
        "--exclude-module", "sklearn",          # 排除sklearn（如果未使用）
        "--hidden-import", "cv2",               # 确保包含OpenCV
        "--hidden-import", "numpy",             # 确保包含numpy
        "--hidden-import", "PIL",               # 确保包含PIL
        "--hidden-import", "PIL.Image",         # 确保包含PIL.Image
        "--hidden-import", "PIL.ImageTk",       # 确保包含PIL.ImageTk
        "--hidden-import", "backend",
        "--hidden-import", "backend.core",
        "--hidden-import", "backend.core.algorithm",
        "--hidden-import", "backend.core.calibrator",
        "--hidden-import", "backend.core.batch",
        "--hidden-import", "backend.core.pointset",
        "--hidden-import", "batch_workbench",
        "--collect-all", "cv2",
        "--add-data", "backend;backend",
        "--add-data", "batch_workbench.py;.",
        "main.py"
    ]
    
    try:
        print(f"执行命令: {' '.join(cmd)}")
        subprocess.check_call(cmd)
        print("✅ PyInstaller打包完成！")
        
        # 获取生成的exe文件大小
        exe_path = os.path.join("dist", "微生物菌落计数器.exe")
        if os.path.exists(exe_path):
            size = os.path.getsize(exe_path)
            size_mb = size / (1024 * 1024)
            print(f"生成的可执行文件大小: {size_mb:.2f} MB ({size:,} 字节)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ PyInstaller打包失败: {e}")
        return False
    except FileNotFoundError:
        print("❌ 未找到PyInstaller，请确保已安装: pip install pyinstaller")
        return False

def compare_with_previous():
    """与之前的版本比较大小"""
    print("📊 比较文件大小...")
    
    # 检查当前生成的文件
    current_exe = os.path.join("dist", "微生物菌落计数器.exe")
    current_size = None
    if os.path.exists(current_exe):
        current_size = os.path.getsize(current_exe)
        print(f"当前版本: {current_size / (1024*1024):.2f} MB")
    
    # 检查之前可能存在的文件
    previous_exe = "微生物菌落计数器.exe"
    previous_size = None
    if os.path.exists(previous_exe):
        previous_size = os.path.getsize(previous_exe)
        print(f"之前版本: {previous_size / (1024*1024):.2f} MB")
        
    if previous_size is not None and current_size is not None:
        # 比较大小
        reduction = previous_size - current_size
        reduction_percent = (reduction / previous_size) * 100
        print(f"优化效果: 减小了 {reduction_percent:.1f}%")
        print(f"减少了 {reduction / (1024*1024):.2f} MB")

def main():
    print("🚀 微生物菌落计数器PyInstaller优化打包工具")
    print("=" * 50)
    
    if not os.path.exists("main.py"):
        print("❌ 未找到main.py文件")
        return
    
    if build_with_pyinstaller():
        print("\n🎉 打包完成！")
        print("📁 可执行文件位于: dist/微生物菌落计数器.exe")
        compare_with_previous()
    else:
        print("❌ 打包失败")

if __name__ == "__main__":
    main()