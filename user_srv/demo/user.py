import grpc
from loguru import logger

from user_srv.proto import user_pb2, user_pb2_grpc


class UserTest:
    def __init__(self):
        # 连接grpc服务器
        channel = grpc.insecure_channel("192.168.16.196:53373")
        self.stub = user_pb2_grpc.UserStub(channel)

    @logger.catch
    def user_list(self):
        rsp: user_pb2.UserListResonse = self.stub.GetUserList(user_pb2.PageInfo(pn=2, pSize=2))
        print(rsp.total)
        for user in rsp.data:
            print(user.mobile, user.birthDay)

    @logger.catch
    def get_user_by_id(self, id):
        rsp: user_pb2.UserInfoResponse = self.stub.GetUserById(user_pb2.IdRequest(id=id))
        print(rsp.mobile)

    @logger.catch
    def create_user(self, nick_name, password, mobile):
        rsp: user_pb2.UserInfoResponse = self.stub.CreateUser(user_pb2.CreateUserInfo(
            nickName=nick_name,
            passWord=password,
            mobile=mobile,
        ))
        print(rsp.mobile)


if __name__ == '__main__':
    logger.add("logs/user_srv_{time}.log")
    user = UserTest()
    user.user_list()
    # print('=======================')
    # user.get_user_by_id(11)
    # user.create_user("CZC", "admin123", "18787878787")
