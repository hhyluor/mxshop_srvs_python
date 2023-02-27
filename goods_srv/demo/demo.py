from goods_srv.model.models import *
import os

lsdir = os.listdir(r"C:\Users\16255\Desktop\Python_Microservice\python-projects\mxshop_srvs\goods_srv\proto")
print(lsdir)
dirs = [i for i in lsdir if os.path.isdir(os.path.join(r"C:\Users\16255\Desktop\Python_Microservice\python-projects\mxshop_srvs\goods_srv\proto", i))]
print(dirs)

a = ""
if a:
    print(a)