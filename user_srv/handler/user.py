import time
from datetime import datetime, date

import grpc
from loguru import logger
from peewee import DoesNotExist
from passlib.hash import pbkdf2_sha256
from google.protobuf import empty_pb2

from user_srv.model.models import User
from user_srv.proto import user_pb2, user_pb2_grpc


class UserServicer(user_pb2_grpc.UserServicer):
    def convert_user_to_rsp(self, user):
        """
        将user的model对象转换成message对象
        """
        user_info_rsp = user_pb2.UserInfoResponse()
        user_info_rsp.id = user.id
        user_info_rsp.mobile = user.mobile
        user_info_rsp.passWord = user.password
        user_info_rsp.role = user.role

        if user.nick_name:
            user_info_rsp.nickName = user.nick_name
        if user.birthday:
            user_info_rsp.birthDay = int(time.mktime(user.birthday.timetuple()))
        if user.gender:
            user_info_rsp.gender = user.gender

        return user_info_rsp

    @logger.catch
    def GetUserList(self, request: user_pb2.PageInfo, context):
        # 获取用户的列表
        rsp = user_pb2.UserListResonse()
        users = User.select()
        rsp.total = users.count()
        # print("用户列表")
        start = 0
        per_page_nums = 10
        if request.pSize:
            per_page_nums = request.pSize
        if request.pn:
            start = per_page_nums * (request.pn - 1)

        users = users.limit(per_page_nums).offset(start)    # limit 显示指定数量的数据  offset 偏移量

        for user in users:
            rsp.data.append(self.convert_user_to_rsp(user))

        return rsp


    @logger.catch
    def GetUserById(self, request: user_pb2.IdRequest, context):
        # 通过 id 查询用户
        try:
            user = User.get(User.id == request.id)
            return self.convert_user_to_rsp(user)

        except DoesNotExist as e:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("用户不存在")
            return user_pb2.UserInfoResponse()

    @logger.catch
    def GetUserByMobile(self, request: user_pb2.MobileRequest, context):
        # 通过 mobile 查询用户
        try:
            user = User.get(User.mobile == request.mobile)
            return self.convert_user_to_rsp(user)

        except DoesNotExist as e:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("用户不存在")
            return user_pb2.UserInfoResponse()

    @logger.catch
    def CreateUser(self, request: user_pb2.CreateUserInfo, context):
        # 新建用户, web开发 - 表单验证 没有必要
        try:
            User.get(User.mobile == request.mobile)

            context.set_code(grpc.StatusCode.ALREADY_EXISTS)
            context.set_details("用户已存在")
            return user_pb2.UserInfoResponse()
        except DoesNotExist as e:
            pass

        user = User()
        user.nick_name = request.nickName
        user.mobile = request.mobile
        user.password = pbkdf2_sha256.hash(request.passWord)
        user.save()
        return self.convert_user_to_rsp(user)

    @logger.catch
    def UpdateUser(self, request: user_pb2.UpdateUserInfo, context):
        # 更新用户
        try:
            user = User.get(User.id == request.id)

            user.nick_name = request.nickName
            user.gender = request.gender
            user.birthday = date.fromtimestamp(request.birthDay)
            user.save()
            return empty_pb2.Empty()
        except DoesNotExist:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("用户不存在")
            return user_pb2.UserInfoResponse()

    @logger.catch
    def CheckPassWord(self, request: user_pb2.PasswordCheckInfo, context):
        return user_pb2.ChenckResponse(success=pbkdf2_sha256.verify(request.password, request.encryptedPassword))
