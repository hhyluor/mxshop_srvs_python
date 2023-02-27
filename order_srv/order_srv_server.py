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

from order_srv.proto import order_pb2_grpc
from order_srv.handler.order import OrderServicer, order_timeout
from common.grpc_health.v1 import health_pb2_grpc
from common.grpc_health.v1 import health
from common.register import consul
from order_srv.settings import settings

from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry import trace
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor


def on_exit(signo, frame, service_id, consumer):
    register = consul.ConsulRegister(settings.CONSUL_HOST, settings.CONSUL_PORT)
    logger.info(f"注销 {service_id} 订单服务")
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
    resource = Resource(attributes={
        SERVICE_NAME: "mxshop-order-srv"
    })

    jaeger_exporter = JaegerExporter(
        agent_host_name="192.168.101.13",
        agent_port=6831,
    )

    provider = TracerProvider(resource=resource)
    # 这是 导出器 设置为 Jaeger  也可设置为 控制台 zipkin 等  需要看官网给的例子
    processor = BatchSpanProcessor(jaeger_exporter)
    provider.add_span_processor(processor)
    # 这是 设置 grpc 相关代码
    proto_simple = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(proto_simple)
    # 这是另一种注入方式
    # trace.get_tracer_provider().add_span_processor(
    #     SimpleSpanProcessor(ConsoleSpanExporter())
    # )
    # 设置全局默认跟踪程序提供程序
    trace.set_tracer_provider(provider)
    # 这里的代码封装了 tracer = trace.get_tracer(__name__)  所以不需要我们手动开启链路追踪
    GrpcInstrumentorServer().instrument()

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

    logger.add("logs/order_srv_{time}.log")
    # 1. 实例化server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # 2.1. 注册订单服务
    order_pb2_grpc.add_OrderServicer_to_server(OrderServicer(), server)
    # 2.2 注册健康检查  别人封装的  给 consul 调用的  检查你是否健康
    health_pb2_grpc.add_HealthServicer_to_server(health.HealthServicer(), server)
    # 3. 启动server
    server.add_insecure_port(f"{args.ip}:{port}")
    # 4. 启动rocketmq 监听超时订单消息
    consumer = PushConsumer("mxshop_order")
    consumer.set_name_server_address(f"{settings.ROCKETMQ_HOST}:{settings.ROCKETMQ_PORT}")
    consumer.subscribe("order_timeout", order_timeout)
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

    logger.info(f"启动订单服务: {args.ip}:{port}")
    server.start()

    logger.info(f"订单服务注册中: {settings.CONSUL_HOST}:{settings.CONSUL_PORT}")
    register = consul.ConsulRegister(settings.CONSUL_HOST, settings.CONSUL_PORT)    # 连接注册中心  consul
    if not register.register(name=settings.SERVICE_NAME, id=service_id, tags=settings.SERVICE_TAGS, address=args.ip, port=port):    # 注册 服务
        logger.info(f"订单服务注册失败")
        sys.exit(0)
    logger.info(f"订单服务注册成功")

    server.wait_for_termination()


if __name__ == '__main__':
    settings.client.add_config_watchers(settings.NACOS["DataId"], settings.NACOS["Group"], [settings.update_cfg])
    server()
