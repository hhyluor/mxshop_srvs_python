# 基于redis的锁  1. 大家尽量自己去完成  2. 一定要看懂源码
# 这是一个面试高频题: 连环炮
import time
from datetime import datetime
import threading

import redis
from peewee import *
from inventory_srv.settings import settings


from inventory_srv.demo.redis_lock_demo.py_redis_lock import Lock as PyLock


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


def sell(th_name, goods_list):
    # 多线程下的并发带来的数据不一致的问题

    with settings.DB.atomic() as txn:
        # 超卖
        # 续租过期时间 - 看门狗 - java 中有一个 redisson
        # 如何防止我设置的值被其他的线程给删除掉
        for goods_id, num in goods_list:
            # 查询库存
            redis_client = redis.Redis(host="192.168.16.196")
            lock = PyLock(redis_client, f"goods_{goods_id}", auto_renewal=True, expire=15)
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
    goods_list = [(421, 10), (422, 20), (423, 30)]
    t1 = threading.Thread(target=sell, args=("线程一", [(421, 10), (422, 20), (423, 30)]))
    t2 = threading.Thread(target=sell, args=("线程二", [(421, 10), (422, 20), (423, 30)]))
    t1.start()
    t2.start()

    t1.join()
    t2.join()
