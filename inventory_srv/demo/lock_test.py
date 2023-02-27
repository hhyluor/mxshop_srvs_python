from datetime import datetime
import threading
import time
from random import randint

from peewee import *
from playhouse.shortcuts import ReconnectMixin
from playhouse.pool import PooledMySQLDatabase
from inventory_srv.settings import settings


R = threading.Lock()


class ReconnectMySQLDatabase(ReconnectMixin, PooledMySQLDatabase):
    pass

db = ReconnectMySQLDatabase("mxshop_inventory_srv", host="192.168.16.196",  port=3306, user="root", password="56248123")


# 删除 物理删除和逻辑删除 - 物理删除 - 假设你把某个用户数据 - 用户购买记录, 用户的收藏记录, 用户浏览记录啊
# 通过 save 方法做了修改 如何确保只修改 update_time 值而不是修改 add_time
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
        database = db


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


def sell():
    # 多线程下的并发带来的数据不一致的问题
    goods_list = [(421, 99), (422, 20), (423, 30)]
    with settings.DB.atomic() as txn:
        # 超卖
        for goods_id, num in goods_list:
            # 查询库存
            R.acquire()     # 获取锁 负载均衡
            goods_inv = Inventory.get(Inventory.goods==goods_id)
            print(f"商品{goods_id} 售出 {num} 件")
            import time
            from random import randint
            time.sleep(randint(1, 3))
            if goods_inv.stocks < num:
                print(f"商品: {goods_id} 库存不足")
                txn.rollback()
                R.release()  # 释放锁
                break
            else:
                # 让数据库根据自己当前的值更新数据, 这个语句能不能处理并发的问题
                query = Inventory.update(stocks=Inventory.stocks-num).where(Inventory.goods==goods_id)
                ok = query.execute()
                if ok:
                    print("更新成功")
                else:
                    print("更新失败")
            R.release()     # 释放锁
            time.sleep(1)


def sell2():
    # 演示基于数据库的乐观锁机制
    goods_list = [(421, 10), (422, 20), (423, 30)]

    with db.atomic() as txn:
        # 超卖
        for goods_id, num in goods_list:
            # 查询库存
            while True:
                goods_inv = Inventory.get(Inventory.goods == goods_id)
                print(f"当前的版本号：{goods_inv.version}")
                print(f"商品{goods_id} 售出 {num}件")

                time.sleep(randint(1, 3))
                if goods_inv.stocks < num:
                    print(f"商品：{goods_id} 库存不足")
                    txn.rollback()
                    break
                else:
                    # 让数据库根据自己当前的值更新数据， 这个语句能不能处理并发的问题
                    # 我当时查询数据的时候版本号是goods_inv.version
                    query = Inventory.update(stocks=Inventory.stocks - num, version=Inventory.version + 1).where(
                        Inventory.goods == goods_id, Inventory.version == goods_inv.version)
                    ok = query.execute()
                    if ok:
                        print("更新成功")
                        break
                    else:
                        query = Inventory.select().where(Inventory.goods == goods_id)
                        print(query.version)
                        print("更新失败")


def sell3():
    # 演示基于数据库的乐观锁机制
    goods_list = [(421, 10), (422, 20), (423, 30)]
    while True:
        if text(goods_list):
            break


def text(goods_list):
    with settings.DB.atomic() as txn:
        # 超卖
        for goods_id, num in goods_list:
            # 查询库存
            goods_inv = Inventory.get(Inventory.goods == goods_id)
            print(f"当前的版本号：{goods_inv.version}")
            print(f"商品{goods_id} 售出 {num}件")

            time.sleep(randint(1, 3))
            if goods_inv.stocks < num:
                print(f"商品：{goods_id} 库存不足")
                txn.rollback()
                return True
            else:
                # 让数据库根据自己当前的值更新数据， 这个语句能不能处理并发的问题
                #我当时查询数据的时候版本号是goods_inv.version
                query = Inventory.update(stocks=Inventory.stocks - num, version=Inventory.version + 1).where(Inventory.goods == goods_id, Inventory.version==goods_inv.version)
                ok = query.execute()
                if ok:
                    print("更新成功")
                else:
                    # a = Inventory.get(Inventory.goods == goods_id)
                    a = Inventory.select().where(Inventory.goods == goods_id)[0]
                    print("更新失败")
                    return False
        return True


if __name__ == '__main__':
    import threading

    t1 = threading.Thread(target=sell2)
    t2 = threading.Thread(target=sell2)
    t1.start()
    t2.start()

    t1.join()
    t2.join()

# <__main__.ReconnectMySQLDatabase object at 0x000002160DCE7EE0>
# <__main__.ReconnectMySQLDatabase object at 0x000002160DCE7EE0>
# <__main__.ReconnectMySQLDatabase object at 0x000002160DCE7EE0>

# <inventory_srv.settings.settings.ReconnectMysqlDatabase object at 0x000001D5498128E0>
# <inventory_srv.settings.settings.ReconnectMysqlDatabase object at 0x000001D5498128E0>
# <inventory_srv.settings.settings.ReconnectMysqlDatabase object at 0x000001D5498128E0>
