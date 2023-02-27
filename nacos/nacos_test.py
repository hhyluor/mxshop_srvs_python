import time

import nacos
import json


def test_cb(args):
    print("配置文件产生变化")
    print(args)


if __name__ == '__main__':
    # Both HTTP/HTTPS protocols are supported, if not set protocol prefix default is HTTP, and HTTPS with no ssl check(verify=False)
    # "192.168.3.4:8848" or "https://192.168.3.4:443" or "http://192.168.3.4:8848,192.168.3.5:8848" or "https://192.168.3.4:443,https://192.168.3.5:443"
    SERVER_ADDRESSES = "192.168.16.196:8848"
    NAMESPACE = "45def8e2-2d16-4438-aee8-6284726e808a"  # 这里是 namespace的id

    # # no auth mode
    # client = nacos.NacosClient(SERVER_ADDRESSES, namespace=NAMESPACE)
    # auth mode
    client = nacos.NacosClient(SERVER_ADDRESSES, namespace=NAMESPACE, username="nacos",
                               password="nacos")  # , ak="{ak}", sk="{sk}

    # get config
    data_id = "user-srv.json"
    group = "dev"
    print(client.get_config(data_id, group))
    print(type(client.get_config(data_id, group)))  # 返回的是字符串

    json_data = json.loads(client.get_config(data_id, group))
    print(json_data)
    print(type(json_data))
    print('==========================================')

    client.add_config_watchers(data_id, group, [test_cb])
    time.sleep(3000)
