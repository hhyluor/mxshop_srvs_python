import requests
import random

from common.register import base


class ConsulRegister(base.Register):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.url = f"http://{self.host}:{self.port}"
        self.headers = {"contentType": "application/json"}

    def register(self, name, id, tags, address, port, check=None) -> bool:
        url = self.url + "/v1/agent/service/register"
        if check is None:
            check = {
                # "HTTP": f"http://{address}:{port}/health",
                "GRPC": f"{address}:{port}",
                "GRPCUseTLS": False,                        # 不需要传证书
                "Timeout": "5s",                            # 连接超时时间
                "Interval": "5s",                           # 检测超时时间
                "DeregisterCriticalServiceAfter": "15s"     # 发生严重的错误 超过 给定的时间 就注销
            }

        rsp = requests.put(url, headers=self.headers, json={
            "Name": name,
            "ID": id,
            "Tags": tags,
            "Address": address,
            "Port": port,
            "Check": check,
        })
        if rsp.status_code == 200:
            return True
        else:
            return False

    def deregister(self, service_id):
        url = self.url + f"/v1/agent/service/deregister/{service_id}"
        rsp = requests.put(url, headers=self.headers)
        if rsp.status_code == 200:
            return True
        else:
            return False

    def get_all_service(self):
        url = self.url + "/v1/agent/services"
        return requests.get(url).json()

    def filter_service(self, filter):
        url = self.url + "/v1/agent/services"
        params = {
            "filter": filter
        }
        return requests.get(url, params=params).json()

    def get_host_port(self, filter):
        url = self.url + "/v1/agent/services"
        params = {
            "filter": filter
        }
        data = requests.get(url, params=params).json()
        if data:
            service_info = random.choice(list(data.values()))
            return service_info["Address"], service_info["Port"]
        return None, None


if __name__ == '__main__':
    temp = ConsulRegister("192.168.16.196", 8500)
    print(temp.register("user-srv",
                        "user-srv",
                        ["imooc", "CZC", "python", "srv"],
                        "192.168.16.196",
                        50051))

