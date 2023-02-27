import time

from rocketmq.client import TransactionMQProducer, Message, TransactionStatus


topic = "test"


def create_message():
    msg = Message(topic)
    msg.set_keys("imooc")
    msg.set_tags("bobby")
    msg.set_property("name", "micro services")
    msg.set_body("微服务开发")
    return msg


def check_callback(msg):
    # 消息回查， 做本地逻辑
    # TransactionStatus.COMMIT, TransactionStatus.ROLLBACK, TransactionStatus.UNKNOWN
    print(f"事务消息回查1: {msg.id} {msg.body.decode('utf-8')}")
    return TransactionStatus.COMMIT


def local_execute(msg, user_args):
    # TransactionStatus.COMMIT, TransactionStatus.ROLLBACK, TransactionStatus.UNKNOWN
    # 这里应该执行业务逻辑, 订单表插入
    print("执行本地事务逻辑")
    return TransactionStatus.COMMIT


def send_transaction_sync(count):
    # 发送事务消息
    producer = TransactionMQProducer("test", check_callback)     # 生产者组
    producer.set_name_server_address("192.168.57.129:9876")
    producer.start()    # 启动producer

    for n in range(count):
        msg = create_message()
        ret = producer.send_message_in_transaction(msg, local_execute)
        print(f"发送状态:{ret.status}, 消息id:{ret.msg_id}, {ret.offset}")
    print("消息发送完成")

    while True:
        time.sleep(3600)
    producer.shutdown()


if __name__ == '__main__':
    # 发送事务消息
    send_transaction_sync(1)
