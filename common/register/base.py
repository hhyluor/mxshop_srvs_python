import abc


# abc.ABCMeta
class Register(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def register(self, name, id, tags, address, port, check):    # 创建 服务
        pass

    @abc.abstractmethod
    def deregister(self, service_id):   # 注销 服务
        pass

    @abc.abstractmethod
    def get_all_service(self):  # 查询 所有服务
        pass

    @abc.abstractmethod
    def filter_service(self,filter):    # 查询 指定服务
        pass
