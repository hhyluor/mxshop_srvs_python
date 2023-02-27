from loguru import logger

from userop_srv.proto import message_pb2, message_pb2_grpc
from userop_srv.model.models import LeavingMessages


class MessageServicer(message_pb2_grpc.MessageServicer):
    @logger.catch
    def MessageList(self, request: message_pb2.MessageRequest, context):
        # 获取分类列表
        rsp = message_pb2.MessageListResponse()     # 返回给中间件的数据
        messages = LeavingMessages.select()         # 查询 用户留言表
        if request.userId:                          # 前端有传递 userId
            messages = messages.filter(LeavingMessages.user==request.userId)    # 返回普通用户的留言数据

        rsp.total = messages.count()                    # 留言数
        for message in messages:                        # 遍历 用户留言表
            brand_rsp = message_pb2.MessageResponse()   # 创建 grpc结构体
            # 进行一系列赋值操作
            brand_rsp.id = message.id
            brand_rsp.userId = message.user
            brand_rsp.messageType = message.message_type
            brand_rsp.subject = message.subject
            brand_rsp.message = message.message
            brand_rsp.file = message.file

            rsp.data.append(brand_rsp)                  # 将留言添加的 rsp中

        return rsp

    @logger.catch
    def CreateMessage(self, request: message_pb2.MessageRequest, context):
        message = LeavingMessages()

        message.user = request.userId
        message.message_type = request.messageType
        message.subject = request.subject
        message.message = request.message
        message.file = request.file

        message.save()

        rsp = message_pb2.MessageResponse()
        rsp.id = message.id
        rsp.messageType = message.message_type
        rsp.subject = message.subject
        rsp.message = message.message
        rsp.file = message.file

        return rsp

