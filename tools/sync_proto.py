import os
import sys
import subprocess
import shutil

"""
    功能:
        1. 拷贝python的proto到go的对应目录之下
        2. 生成python的源码 - import .
        3. 生成go的源码
"""


class cd:
    def __init__(self, newPath):
        self.newPath = os.path.expanduser(newPath)

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.savedPath)


def replace_file(file_name):
    """
    添加 import .
    """
    new_file_name = f"{file_name}-bak"
    modify_times = 0  # 统计修改次数
    f1 = open(file_name, 'r', encoding='utf-8')  # 以“r”(只读)模式打开旧文件
    f2 = open(new_file_name, 'w', encoding='utf-8')  # 以“w”(写)模式打开或创建新文件（写模式下，文件存在则重写文件，文件不存在则创建文件）
    for lines in f1:  # 循环读
        if lines.startswith("import") and not lines.startswith("import grpc"):
            lines = f"from . {lines}"
            modify_times += 1  # 每修改一次就自增一次
        f2.write(lines)  # 将修改后的内容后的内容写入新文件
    print(f'{file_name} 文件修改的次数：', modify_times)  # 9
    f1.close()  # 关闭文件f1
    f2.close()  # 关闭文件f2(同时打开多个文件时，先打开的先关闭，后打开的后关闭)
    os.replace(new_file_name, file_name)  # 修改(替换)文件名


def proto_file_list(path):
    """
        返回这个文件夹 里的 proto文件
    """
    flist = []
    lsdir = os.listdir(path)        # 列举python proto目录的的文件名
    dirs = [i for i in lsdir if os.path.isdir(os.path.join(path, i))]   # 判断是否是 文件夹
    if dirs:
        for i in dirs:
            proto_file_list(os.path.join(path, i))                      # 递归调用
    files = [i for i in lsdir if os.path.isfile(os.path.join(path, i))] # 判断是否是 文件
    for file in files:
        if file.endswith(".proto"):     # 如果后缀名是 proto
            flist.append(file)
    return flist


def copy_from_py_to_go(src_dir, dst_dir):
    """
        src_dir 文件 复制到 dst_dir
    """
    proto_files = proto_file_list(src_dir)
    for proto_file in proto_files:
        try:
            shutil.copy(f"{src_dir}/{proto_file}", dst_dir)
        except IOError as e:
            print("Unable to copy file. %s" % e)
        except:
            print("Unexpected error:", sys.exc_info())


def generated_pyfile_list(path):
    """
        返回 生成后此文件夹中 py文件
    """
    flist = []
    lsdir = os.listdir(path)    # 列举python proto目录的的文件名
    dirs = [i for i in lsdir if os.path.isdir(os.path.join(path, i))]   # 筛选出 此文件下所有的 文件夹
    if dirs:
        for i in dirs:
            proto_file_list(os.path.join(path, i))          # 返回这个文件夹 里的 proto文件
    files = [i for i in lsdir if os.path.isfile(os.path.join(path, i))] # 判断是否是 文件
    for file in files:
        if file.endswith(".py"):        # 找到 .py文件
            flist.append(file)
    return flist


class ProtoGenerator:
    def __init__(self, python_dir, go_dir):
        self.python_dir = python_dir
        self.go_dir = go_dir

    def generate(self):
        with cd(self.python_dir["proto_file"]):
            files = proto_file_list(self.python_dir["proto_file"])
            subprocess.call(f"workon {self.python_dir['python_environment']}", shell=True)  # 启动的进程 然后执行 命令

            for file in files:
                command = f"python -m grpc_tools.protoc --python_out=. --grpc_python_out=. -I. {file}"
                subprocess.call(command, shell=True)

            # 查询生成的py文件并添加上 from .
            py_files = generated_pyfile_list(self.python_dir["proto_file"])
            for file_name in py_files:
                replace_file(file_name)

        with cd(self.go_dir["proto_file"]):
            files = proto_file_list(self.go_dir["proto_file"])
            if self.go_dir['go_environment']:
                param = f" -I {self.go_dir['go_environment']}"
            else:
                param = ""
            for file in files:
                command = fr"protoc -I {self.go_dir['proto_file']} {param} --go_out=. --go-grpc_out=. {file}"
                subprocess.call(command)


if __name__ == "__main__":
    # goods的proto生成
    python_dir = {
        "proto_file": r"C:\Users\16255\Desktop\Python_Microservice\python-projects\mxshop_srvs\goods_srv\proto",
        "python_environment": "mxshop_srv"      # python的虚拟环境
    }
    go_dir = {
         "proto_file": r"C:\Users\16255\Desktop\Python_Microservice\go-projects\mxshop-api\goods-web\proto",
         "go_environment": r"C:\Users\16255\AppData\Local\JetBrains\GoLand2022.1\protoeditor"       # 如果不需要 就 换成空字符串
    }

    # 将py目录下的文件夹拷贝到go目录下
    copy_from_py_to_go(python_dir["proto_file"], go_dir["proto_file"])

    # 生成对应的py源码和go源码
    gen = ProtoGenerator(python_dir, go_dir)
    gen.generate()
