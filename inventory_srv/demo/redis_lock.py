# 基于redis的锁  1. 大家尽量自己去完成  2. 一定要看懂源码
# 这是一个面试高频题: 连环炮
import time
from datetime import datetime
import threading
from random import randint

import uuid
import redis
from peewee import *
from playhouse.shortcuts import ReconnectMixin
from playhouse.pool import PooledMySQLDatabase
from inventory_srv.settings import settings


class ReconnectMySQLDatabase(ReconnectMixin, PooledMySQLDatabase):
    pass


DB = ReconnectMySQLDatabase("mxshop_inventory_srv", host="192.168.16.196",  port=3306, user="root", password="56248123")


class BaseModel(Model):
    add_time = DateTimeField(default=datetime.now, verbose_name="添加时间")
    update_time = DateTimeField(default=datetime.now, verbose_name="更新时间")
    is_deleted = BooleanField(default=False, verbose_name="是否删除")

    def save(self, *args, **kwargs):
        # 判断这是一个新添加的数据还是更新的数据
        if self._pk is not None:
            # 这是一个新数据
            self.update_time = datetime.now()
        return super().save(*args, **kwargs)

    @classmethod
    def delete(cls, permanently=False):   # permanently 表示是否永久删除
        if permanently:
            return super().delete()
        else:
            return super().update(is_deleted=True)

    def delete_instance(self, permanently=False, recursive=False, delete_nullable=False):
        if permanently:
            return self.delete(permanently).where(self._pk_expr()).execute()
        else:
            self.is_deleted = True
            self.save()

    @classmethod
    def select(cls, *fields):
        return super().select(*fields).where(cls.is_deleted==False)

    class Meta:
        database = settings.DB


# class Stock(BaseModel):
#     # 仓库表
#     name = CharField(verbose_name="仓库名")
#     address = CharField(verbose_name="仓库地址")


class Inventory(BaseModel):
    # 商品的库存表
    # stock = PrimaryKeyField(Stock)
    goods = IntegerField(verbose_name="商品id", unique=True)      # unique:在此列上创建唯一索引
    stocks = IntegerField(verbose_name="库存数量", default=0)
    version = IntegerField(verbose_name="版本号", default=0)       # 分布式锁的一种 乐观锁


class Lock:
    def __init__(self, name, id=None):
        self.id = str(uuid.uuid4())
        self.redis_client = redis.Redis(host="192.168.16.196")
        self.name = name

    def acquire(self):
        # if not self.redis_client.get(self.name):
        #     # 如果为空或者为None那么代表获取到锁
        #     self.redis_client.set(self.name, 1) # 如果为空 或者 为None 那么代表获取到锁
        #     return True

        # if self.redis_client.setnx(self.name, 1):                 # 如果不存在设置返回1, 否则返回0, 这是原子操作
        if self.redis_client.set(self.name, self.id, nx=True, ex=15):     # 过期时间
            # 启动一个线程然后去定时的刷新这个过期 这个操作最好也使用lua脚本来完成
            return True
        else:
            while True:
                time.sleep(1)
                if self.redis_client.set(self.name, self.id, nx=True, ex=15):
                    return True

    def release(self):
        # 先做一个判断, 先取出值来 然后判断当前的值和你自己的lock中id是否一致, 如果一致删除, 如果不一致报错
        # 这块代码不安全, 将get和delete操作原子化 - 但是redis提供了一个脚本原因 - lua - nginx
        # 使用 lua脚本取完成这个操作使得该操作原子化
        id = self.redis_client.get(self.name)
        if id == self.id:
            self.redis_client.delete(self.name)
        else:
            print("不能删除不属于自己的锁")


def sell(th_name, goods_list):
    # 多线程下的并发带来的数据不一致的问题

    with settings.DB.atomic() as txn:
        # 超卖
        # 续租过期时间 - 看门狗 - java 中有一个 redisson
        # 如何防止我设置的值被其他的线程给删除掉
        for goods_id, num in goods_list:
            # 查询库存
            lock = Lock(f"lock:goods_{goods_id}")
            lock.acquire()
            goods_inv = Inventory.get(Inventory.goods==goods_id)
            print(f"{th_name} 商品{goods_id} 售出 {num} 件, 当前剩余 {goods_inv.stocks-num}")
            time.sleep(20)
            if goods_inv.stocks < num:
                print(f"{th_name} 商品: {goods_id} 库存不足")
                txn.rollback()
                break
            else:
                # 让数据库根据自己当前的值更新数据, 这个语句能不能处理并发的问题
                query = Inventory.update(stocks=Inventory.stocks-num).where(Inventory.goods==goods_id)
                ok = query.execute()
                if ok:
                    print(f"{th_name} 更新成功")
                else:
                    print(f"{th_name} 更新失败")
            lock.release()


if __name__ == '__main__':
    # lock = Lock("bobby")
    # lock.acquire()
    # lock.release()
    goods_list = [(421, 10), (422, 20), (423, 30)]
    t1 = threading.Thread(target=sell, args=("线程一", [(421, 10), (422, 20), (423, 30)]))
    t2 = threading.Thread(target=sell, args=("线程二", [(421, 10), (422, 20), (423, 30)]))
    t1.start()
    t2.start()

    t1.join()
    t2.join()
