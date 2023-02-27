import os
import signal
import socket
import sys
import argparse
import uuid
from concurrent import futures
# import logging
from functools import partial

BASE_DIR = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, BASE_DIR)

import grpc
from loguru import logger
from rocketmq.client import PushConsumer

from inventory_srv.proto import inventory_pb2_grpc
from inventory_srv.handler.inventory import InventoryServicer, reback_inv
from common.grpc_health.v1 import health_pb2_grpc
from common.grpc_health.v1 import health
from common.register import consul
from inventory_srv.settings import settings


def on_exit(signo, frame, service_id, consumer):
    register = consul.ConsulRegister(settings.CONSUL_HOST, settings.CONSUL_PORT)
    logger.info(f"注销 {service_id} 库存服务")
    register.deregister(service_id)
    logger.info(f"注销rocketmq")
    consumer.shutdown()
    logger.info(f"注销成功")
    sys.exit(0)


def get_free_tcp_port():
    # 自动获取端口号
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.bind(("", 0))
    _, port = tcp.getsockname()
    tcp.close()
    return port


def server():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip',
                        nargs="?",
                        type=str,
                        default="192.168.16.196",
                        help="binding ip"
                        )

    parser.add_argument('--port',
                        nargs="?",
                        type=int,
                        default=0,
                        help="the listening port"
                        )

    args = parser.parse_args()

    if args.port == 0:
        port = get_free_tcp_port()
    else:
        port = args.port

    logger.add("logs/inventory_srv_{time}.log")
    # 1. 实例化server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # 2.1. 注册库存服务
    inventory_pb2_grpc.add_InventoryServicer_to_server(InventoryServicer(), server)
    # 2.2 注册健康检查  别人封装的  给 consul 调用的  检查你是否健康
    health_pb2_grpc.add_HealthServicer_to_server(health.HealthServicer(), server)
    # 3. 启动server
    server.add_insecure_port(f"{args.ip}:{port}")
    # 4. 启动rocketmq  启动之后还得监听rocketmq的对应的topic进行库存归还
    consumer = PushConsumer("mxshop_inventory")
    consumer.set_name_server_address(f"{settings.ROCKETMQ_HOST}:{settings.ROCKETMQ_PORT}")
    consumer.subscribe("order_reback", reback_inv)
    consumer.start()

    service_id = str(uuid.uuid1())  # 使用主机ID, 序列号, 和当前时间来生成UUID

    # 主进程退出信号监听
    """
        windows下支持的信号是有限的:
            SIGINT  ctrl+C 中断命令
            SIGTERM kill 发出的软件终止
    """
    signal.signal(signal.SIGINT, partial(on_exit, service_id=service_id, consumer=consumer))
    signal.signal(signal.SIGTERM, partial(on_exit, service_id=service_id, consumer=consumer))

    logger.info(f"启动库存服务: {args.ip}:{port}")
    server.start()

    logger.info(f"库存服务注册中: {settings.CONSUL_HOST}:{settings.CONSUL_PORT}")
    register = consul.ConsulRegister(settings.CONSUL_HOST, settings.CONSUL_PORT)    # 连接注册中心  consul
    if not register.register(name=settings.SERVICE_NAME, id=service_id, tags=settings.SERVICE_TAGS, address=args.ip, port=port):    # 注册 服务
        logger.info(f"库存服务注册失败")
        sys.exit(0)
    logger.info(f"库存服务注册成功")

    server.wait_for_termination()


if __name__ == '__main__':
    settings.client.add_config_watchers(settings.NACOS["DataId"], settings.NACOS["Group"], [settings.update_cfg])
    server()
