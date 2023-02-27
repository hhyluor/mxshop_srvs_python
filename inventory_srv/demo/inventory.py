import json
import time

import grpc
from loguru import logger
import consul
from google.protobuf import empty_pb2

from inventory_srv.proto import inventory_pb2, inventory_pb2_grpc
from inventory_srv.settings import settings


class InventoryTest:
    def __init__(self):
        # 连接grpc服务器
        c = consul.Consul("192.168.16.196", port=8500)
        services = c.agent.services()
        ip = ""
        port = ""

        for key, value in services.items():
            if value["Service"] == settings.SERVICE_NAME:
                ip = value["Address"]
                port = value["Port"]
                break
        if not ip:
            raise Exception()
        channel = grpc.insecure_channel(f"{ip}:{port}")
        self.stub = inventory_pb2_grpc.InventoryStub(channel)

    @logger.catch
    def set_inv(self):
        rsp: empty_pb2.Empty = self.stub.SetInv(
            inventory_pb2.GoodsInvInfo(goodsId=10, num=100)
        )

    @logger.catch
    def get_inv(self):
        rsp = self.stub.InvDetail(
            inventory_pb2.GoodsInvInfo(goodsId=10)
        )
        print(rsp.num)

    @logger.catch
    def sell(self):
        goods_list = [(421, 10), (422, 90)]
        request = inventory_pb2.SellInfo()
        for goodsId, num in goods_list:
            request.goodsInfo.append(inventory_pb2.GoodsInvInfo(goodsId=goodsId, num=num))
        rsp = self.stub.Sell(request)
        print(rsp)

    @logger.catch
    def reback(self):
        goods_list = [(421, 3), (422, 7)]
        request = inventory_pb2.SellInfo()
        for goodsId, num in goods_list:
            request.goodsInfo.append(inventory_pb2.GoodsInvInfo(goodsId=goodsId, num=num))
        rsp = self.stub.Reback(request)
        print(rsp)


if __name__ == '__main__':
    # inventory = InventoryTest()
    #
    # # inventory.set_inv()
    #
    # # inventory.get_inv()
    #
    # inventory.sell()
    #
    # # inventory.reback()

    import threading

    t1 = threading.Thread(target=InventoryTest().sell)
    t2 = threading.Thread(target=InventoryTest().sell)
    t1.start()
    t2.start()

    t1.join()
    t2.join()