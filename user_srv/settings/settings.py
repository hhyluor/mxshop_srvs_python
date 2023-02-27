import json

import nacos
from playhouse.pool import PooledMySQLDatabase
from playhouse.shortcuts import ReconnectMixin
from loguru import logger


# 使用peewee的连接池, 使用ReconnectMixin来防止出现连接断开查询失败
class ReconnectMysqlDatabase(PooledMySQLDatabase, ReconnectMixin):
    # python的mro
    def sequence_exists(self, seq):
        pass


def update_cfg(args):
    logger.info("配置产生变化")


NACOS = {
    "Host": "192.168.101.13",
    "Post": 8848,
    "NameSpace": "f921c1e9-c828-4315-96d4-8e4eaae479da",
    "User": "nacos",
    "Password": "nacos",
    "DataId": "user-srv.json",
    "Group": "dev",
}
client = nacos.NacosClient(f"{NACOS['Host']}:{NACOS['Post']}",
                           namespace=NACOS["NameSpace"],
                           username=NACOS["User"],
                           password=NACOS["Password"])  # , ak="{ak}", sk="{sk}
# get config
data = client.get_config(NACOS["DataId"], NACOS["Group"])
data = json.loads(data)

# consul的配置
CONSUL_HOST = data["consul"]["host"]
CONSUL_PORT = data["consul"]["port"]

# 服务相关的配置
SERVICE_NAME = data["name"]
SERVICE_TAGS = data["tags"]

DB = ReconnectMysqlDatabase(data["mysql"]["db"],
                            host=data["mysql"]["host"],
                            port=data["mysql"]["port"],
                            user=data["mysql"]["user"],
                            password=data["mysql"]["password"])
