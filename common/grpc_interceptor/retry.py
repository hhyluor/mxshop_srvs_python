from grpc import StatusCode, RpcError, UnaryUnaryClientInterceptor, UnaryStreamClientInterceptor
import time
import random


class RetryInterceptor(UnaryUnaryClientInterceptor, UnaryStreamClientInterceptor):      # 一元调用  继承 UnaryUnaryClientInterceptor 和 UnaryStreamClientInterceptor

    def __init__(self, max_retries=3, retry_codes=None, retry_timeout_ms=100, retry_jitter_ms=20):
        if retry_codes is None:                                                     # 如果没有指定 错误重试类型
            retry_codes = [StatusCode.UNAVAILABLE, StatusCode.DEADLINE_EXCEEDED]    # 该服务不可用    超时
        self.max_retries = max_retries                                              # 重试次数
        self.retry_codes = retry_codes                                              # 什么情况下重试
        self.retry_timeout_ms = retry_timeout_ms                                    # 多久算超时
        self.retry_jitter_ms = retry_jitter_ms                                      # 容错  比 ms 小 的 一个时间单位

        if self.retry_jitter_ms > self.retry_timeout_ms:        # 如果
            raise ValueError('retry_jitter_ms cannot be greater than retry_timeout_ms')

    def _next_retry_timeout_seconds(self):
        ms_timeout = self.retry_timeout_ms + (random.randint(-1, 1) * self.retry_jitter_ms)
        s_timeout = ms_timeout / 1000
        return s_timeout

    def intercept_unary_unary(self, continuation, client_call_details, request):
        retry_count = 0
        while True:
            try:
                response = continuation(client_call_details, request)
                return response
            except RpcError as e:
                if e.code() not in self.retry_codes:                # 如果不是 我们选择的错误中的一种 则 报错
                    raise e
                if retry_count >= self.max_retries:                 # 如果超出重试次数 则报错
                    raise e
                retry_count += 1                                    # 次数 +1
                time.sleep(self._next_retry_timeout_seconds())      # 等待的时间

    def intercept_unary_stream(self, continuation, client_call_details, request):

        def intercept(continuation, client_call_details, request):

            def iterator_wrapper(gen):

                retry_count = 0
                has_started = False
                while True:     # 循环执行
                    try:
                        val = next(gen)                         # 执行 gen 函数 也就是 continuation(client_call_details, request)  也就是返回 response
                        has_started = True                      # has_started 设置为 True
                        yield val                               # yield 和 return 类似  但是是可迭代的 (正常流程 会执行到这里 return出去)
                    except RpcError as e:                       # 如果 是 grpc 的 错误
                        if has_started:                         # 如果 执行到  yield val 这里
                            raise e                             # 提交报错
                        if e.code() not in self.retry_codes:    # 如果不是 我们选择的错误中的一种 则 报错
                            raise e                             # 提交报错
                        if retry_count >= self.max_retries:     # 如果超出重试次数 则报错
                            raise e                             # 提交报错

                        retry_count += 1
                        timeout = self._next_retry_timeout_seconds()        # 时长
                        time.sleep(timeout)                                 # 等待 timeout 秒

                        gen = continuation(client_call_details, request)    # 再次执行 continuation(client_call_details, request)
                    except StopIteration:
                        return

            return iterator_wrapper(continuation(client_call_details, request))     # 返回 这个函数的调用结果

        return intercept(continuation, client_call_details, request)                # 返回 这个函数的调用结果