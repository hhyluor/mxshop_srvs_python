from concurrent.futures import ThreadPoolExecutor
import time
import threading
import sys

from rocketmq.client import Message, SendStatus, TransactionMQProducer, TransactionStatus

PY_VERSION = sys.version_info[0]


def test_producer_send_sync(producer):
    msg = Message('test')
    msg.set_keys('send_sync')
    msg.set_tags('XXX')
    msg.set_body('XXXX')
    ret = producer.send_sync(msg)
    assert ret.status == SendStatus.OK


def test_producer_send_sync_multi_thread(producer):
    executor = ThreadPoolExecutor(max_workers=5)
    futures = []
    for _ in range(5):
        futures.append(executor.submit(test_producer_send_sync, producer))

    for future in futures:
        _ret = future.result()


def test_producer_send_oneway(producer):
    msg = Message('test')
    msg.set_keys('send_oneway')
    msg.set_tags('XXX')
    msg.set_body('XXXX')
    producer.send_oneway(msg)


def test_producer_send_orderly_with_sharding_key(orderly_producer):
    msg = Message('test')
    msg.set_keys('sharding_message')
    msg.set_tags('sharding')
    msg.set_body('sharding message')
    msg.set_property('property', 'test')
    ret = orderly_producer.send_orderly_with_sharding_key(msg, 'order1')
    assert ret.status == SendStatus.OK


def test_transaction_producer():
    stop_event = threading.Event()
    msg_body = 'XXXX'

    def on_local_execute(msg, user_args):
        print("执行本地事务逻辑")
        return TransactionStatus.UNKNOWN

    def on_check(msg):
        stop_event.set()
        print(f"事务消息回查: {msg.body.decode('utf-8')}")
        assert msg.body.decode('utf-8') == msg_body
        return TransactionStatus.COMMIT

    producer = TransactionMQProducer('transactionTestGroup' + str(PY_VERSION), on_check)
    producer.set_name_server_address('127.0.0.1:9876')
    producer.start()
    msg = Message('test')
    msg.set_keys('transaction')
    msg.set_tags('XXX')
    msg.set_body(msg_body)
    producer.send_message_in_transaction(msg, on_local_execute)
    while not stop_event.is_set():
        time.sleep(2)
    producer.shutdown()


if __name__ == '__main__':
    test_transaction_producer()