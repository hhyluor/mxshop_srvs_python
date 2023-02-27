import json

import grpc
from loguru import logger
from peewee import DoesNotExist
from google.protobuf import empty_pb2
from rocketmq.client import ConsumeStatus

from inventory_srv.proto import inventory_pb2, inventory_pb2_grpc
from inventory_srv.model.models import *
from inventory_srv.settings import settings
from common.lock.py_redis_lock import Lock


def reback_inv(msg):    # 执行到这里 说明 生产者 确认了消息(要回滚)  但是还是确保 做一次认证
    # 通过msg的body中的order_sn来确定库存的归还
    msg_body_str = msg.body.decode("utf-8")
    print(f"收到消息: {msg_body_str}")
    msg_body = json.loads(msg_body_str)
    order_sn = msg_body["orderSn"]

    # 为了防止没有扣减库存反而归还库存的情况, 这里我们要先查询有没有库存扣减记录
    with settings.DB.atomic() as txn:
        try:
            # 为什么要用事务来做: 我们查询库存扣减历史记录, 并逐个归还商品库存
            order_inv = InventoryHistory.get(InventoryHistory.order_sn==order_sn, InventoryHistory.status==1)  # 如果是已经扣减了
            inv_details = json.loads(order_inv.order_inv_detail)   # 查看此订单下的 商品 和 商品数
            for item in inv_details:            # 遍历json
                goods_id = item["goods_id"]
                num = item["num"]
                Inventory.update(stocks=Inventory.stocks+num).where(Inventory.goods==goods_id).execute()
            order_inv.status = 2
            order_inv.save()
            return ConsumeStatus.CONSUME_SUCCESS    # 返回接受成功信号  不用重复发送
        except DoesNotExist as e:
            return ConsumeStatus.CONSUME_SUCCESS    # 查询不到 说明已归还
        except Exception as e:
            txn.rollback()
            return ConsumeStatus.RECONSUME_LATER


class InventoryServicer(inventory_pb2_grpc.InventoryServicer):
    @logger.catch
    def SetInv(self, request: inventory_pb2.GoodsInvInfo, context):
        """
        设置库存 修改库存接口
        """
        force_insert = False
        invs = Inventory.select().where(Inventory.goods==request.goodsId)
        if not invs:
            inv = Inventory()
            inv.goods = request.goodsId     # 存在一个问题 就 首次创建 数据
            force_insert = True
        else:
            inv = invs[0]
        inv.goods = request.goodsId
        inv.stocks = request.num
        inv.save(force_insert=force_insert)

        return empty_pb2.Empty()

    @logger.catch
    def InvDetail(self, request: inventory_pb2.GoodsInvInfo, context):
        """
        获取某个商品的详情
        """
        try:
            inv = Inventory.get(Inventory.goods==request.goodsId)
            return inventory_pb2.GoodsInvInfo(goodsId=inv.goods, num=inv.stocks)
        except DoesNotExist as e:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("没有库存记录")
            return inventory_pb2.GoodsInvInfo()

    @logger.catch
    def Sell(self, request: inventory_pb2.SellInfo, context):
        """
        扣减库存 超卖的问题, 事务
        什么是事务: 执行多个 sql 是原子性的
        """
        inv_history = InventoryHistory(order_sn=request.orderSn)
        inv_detail = []

        with settings.DB.atomic() as txn:
            for item in request.goodsInfo:
                # 查询库存
                lock = Lock(settings.REDIS_CLIENT, f"goods_{item.goodsId}", auto_renewal=True, expire=10)
                lock.acquire()
                # logger.info(f"加锁 goods_{item.goodsId}")
                try:
                    goods_inv = Inventory.get(Inventory.goods==item.goodsId)
                except DoesNotExist as e:
                    txn.rollback()  # 事务回滚
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    lock.release()
                    return empty_pb2.Empty()

                if goods_inv.stocks < item.num:
                    # 库存不足
                    context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)    # 资源超出限制
                    # logger.info(f"资源超出限制")
                    context.set_details("库存不足")
                    txn.rollback()  # 事务回滚
                    lock.release()
                    return empty_pb2.Empty()
                else:
                    # TODO 这里可能会引起数据不一致 - 分布式锁(已解决)
                    # 添加 购买的商品 和 数量 加入列表中  目的用户 接受mq消息时 用判断订单的状态用
                    inv_detail.append({
                        "goods_id": item.goodsId,
                        "num": item.num
                    })
                    goods_inv.stocks = goods_inv.stocks - item.num
                    goods_inv.save()
                    # logger.info(f"扣减之后库存: {goods_inv.stocks}")
                lock.release()
            try:
                inv_history.order_inv_detail = json.dumps(inv_detail)
                inv_history.save()      # 存储 购买的商品
            except DoesNotExist as e:
                txn.rollback()  # 事务回滚
                context.set_code(grpc.StatusCode.NOT_FOUND)
                return empty_pb2.Empty()

        return empty_pb2.Empty()

    @logger.catch
    def Reback(self, request: inventory_pb2.SellInfo, context):
        """
        库存的归还, 有两种情况会归还:
        1. 订单超时自动归还
        2. 订单创建失败, 需要归还之前的库存
        3. 手动归还
        """
        with settings.DB.atomic() as txn:
            for item in request.goodsInfo:
                # 查询库存
                lock = Lock(settings.REDIS_CLIENT, f"goods_{item.goodsId}", auto_renewal=True, expire=10)
                lock.acquire()
                try:
                    goods_inv = Inventory.get(Inventory.goods == item.goodsId)
                except DoesNotExist as e:
                    txn.rollback()  # 事务回滚
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return empty_pb2.Empty()

                # TODO 这里可能会引起数据不一致 - 分布式锁
                goods_inv.stocks += item.num
                goods_inv.save()
                lock.release()
        return empty_pb2.Empty()

    # def TrySell(self, request, context):
    #     # 尝试扣减库存
    #     for item in request.goodsInfo:
    #         # 查询库存
    #         lock = Lock(settings.REDIS_CLIENT, f"goods_{item.goodsId}", auto_renewal=True, expire=10)
    #         lock.acquire()
    #         # logger.info(f"加锁 goods_{item.goodsId}")
    #         try:
    #             goods_inv = InventoryNew.get(Inventory.goods == item.goodsId)
    #         except DoesNotExist as e:
    #             context.set_code(grpc.StatusCode.NOT_FOUND)
    #             return empty_pb2.Empty()
    #
    #         if goods_inv.stocks < item.num:
    #             # 库存不足
    #             context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)  # 资源超出限制
    #             # logger.info(f"资源超出限制")
    #             context.set_details("库存不足")
    #             return empty_pb2.Empty()
    #         else:
    #             # TODO 这里可能会引起数据不一致 - 分布式锁
    #             goods_inv.freeze += item.num
    #             goods_inv.save()
    #             # logger.info(f"扣减之后库存: {goods_inv.stocks}")
    #         lock.release()
    #
    # def ConfirmSell(self, request, context):
    #     # 确认扣减库存
    #     for item in request.goodsInfo:
    #         # 查询库存
    #         lock = Lock(settings.REDIS_CLIENT, f"goods_{item.goodsId}", auto_renewal=True, expire=10)
    #         lock.acquire()
    #         # logger.info(f"加锁 goods_{item.goodsId}")
    #         try:
    #             goods_inv = InventoryNew.get(Inventory.goods == item.goodsId)
    #         except DoesNotExist as e:
    #             context.set_code(grpc.StatusCode.NOT_FOUND)
    #             return empty_pb2.Empty()
    #
    #         if goods_inv.stocks < item.num:
    #             # 库存不足
    #             context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)  # 资源超出限制
    #             # logger.info(f"资源超出限制")
    #             context.set_details("库存不足")
    #             return empty_pb2.Empty()
    #         else:
    #             # TODO 这里可能会引起数据不一致 - 分布式锁
    #             goods_inv.freeze -= item.num
    #             goods_inv.stocks -= item.num
    #             goods_inv.save()
    #             # logger.info(f"扣减之后库存: {goods_inv.stocks}")
    #         lock.release()
    #
    # def CancleSell(self, request, context):
    #     # 取消扣减库存
    #     for item in request.goodsInfo:
    #         # 查询库存
    #         lock = Lock(settings.REDIS_CLIENT, f"goods_{item.goodsId}", auto_renewal=True, expire=10)
    #         lock.acquire()
    #         # logger.info(f"加锁 goods_{item.goodsId}")
    #         try:
    #             goods_inv = InventoryNew.get(Inventory.goods == item.goodsId)
    #         except DoesNotExist as e:
    #             context.set_code(grpc.StatusCode.NOT_FOUND)
    #             return empty_pb2.Empty()
    #
    #         if goods_inv.stocks < item.num:
    #             # 库存不足
    #             context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)  # 资源超出限制
    #             # logger.info(f"资源超出限制")
    #             context.set_details("库存不足")
    #             return empty_pb2.Empty()
    #         else:
    #             # TODO 这里可能会引起数据不一致 - 分布式锁
    #             goods_inv.freeze -= item.num
    #             goods_inv.save()
    #             # logger.info(f"扣减之后库存: {goods_inv.stocks}")
    #         lock.release()
