import threading
import weakref
from base64 import b64encode
from logging import getLogger
from os import urandom
from typing import Union

from redis import StrictRedis


__version__ = '3.7.0'

logger_for_acquire = getLogger(f"{__name__}.acquire")
logger_for_refresh_thread = getLogger(f"{__name__}.refresh.thread")
logger_for_refresh_start = getLogger(f"{__name__}.refresh.start")
logger_for_refresh_shutdown = getLogger(f"{__name__}.refresh.shutdown")
logger_for_refresh_exit = getLogger(f"{__name__}.refresh.exit")
logger_for_release = getLogger(f"{__name__}.release")


"""
if redis.call("get", KEYS[1]) ~= ARGV[1] then           如果 KEYS[1]的 values 值 不等于 所希望的values
    return 1
else
    redis.call("del", KEYS[2])                          删除 KEY值
    redis.call("lpush", KEYS[2], 1)                     将一个或多个值插入到列表头部
    redis.call("pexpire", KEYS[2], ARGV[2])             PEXPIRE 命令和 EXPIRE 命令的作用类似，但是它以毫秒为单位设置 key 的生存时间，而不像 EXPIRE 命令那样，以秒为单位
    redis.call("del", KEYS[1])                          删除 KEY值
    return 0
end
"""
UNLOCK_SCRIPT = b"""
    if redis.call("get", KEYS[1]) ~= ARGV[1] then
        return 1
    else
        redis.call("del", KEYS[2])
        redis.call("lpush", KEYS[2], 1)
        redis.call("pexpire", KEYS[2], ARGV[2])
        redis.call("del", KEYS[1])
        return 0
    end
"""

# Covers both cases when key doesn't exist and doesn't equal to lock's id
"""
if redis.call("get", KEYS[1]) ~= ARGV[1] then           如果 KEYS[1]的 values 值 不等于 所希望的values
    return 1
elseif redis.call("ttl", KEYS[1]) < 0 then              秒为单位返回 key 的剩余过期时间
    return 2
else
    redis.call("expire", KEYS[1], ARGV[2])              为 key 设置过期时间
    return 0
end
"""
EXTEND_SCRIPT = b"""
    if redis.call("get", KEYS[1]) ~= ARGV[1] then
        return 1
    elseif redis.call("ttl", KEYS[1]) < 0 then
        return 2
    else
        redis.call("expire", KEYS[1], ARGV[2])
        return 0
    end
"""

"""
redis.call('del', KEYS[2])                      删除 key
redis.call('lpush', KEYS[2], 1)                 将一个或多个值插入到列表头部
redis.call('pexpire', KEYS[2], ARGV[2])         PEXPIRE 命令和 EXPIRE 命令的作用类似，但是它以毫秒为单位设置 key 的生存时间，而不像 EXPIRE 命令那样，以秒为单位
return redis.call('del', KEYS[1])               删除 key
"""
RESET_SCRIPT = b"""
    redis.call('del', KEYS[2])
    redis.call('lpush', KEYS[2], 1)
    redis.call('pexpire', KEYS[2], ARGV[2])
    return redis.call('del', KEYS[1])
"""

"""
获取 所有 redis 的 key
遍历 lock 的 所有的 值 得到 value的值
signal = 'lock-signal:' .. string.sub(lock, 6)  返回前 6个字符
redis.call('del', signal)                       删除 key
redis.call('lpush', signal, 1)                  将一个或多个值插入到列表头部
redis.call('expire', signal, 1)                 为 key 设置过期时间
redis.call('del', lock)                         删除 key
"""
RESET_ALL_SCRIPT = b"""
    local locks = redis.call('keys', 'lock:*')
    local signal
    for _, lock in pairs(locks) do
        signal = 'lock-signal:' .. string.sub(lock, 6)
        redis.call('del', signal)
        redis.call('lpush', signal, 1)
        redis.call('expire', signal, 1)
        redis.call('del', lock)
    end
    return #locks
"""


class AlreadyAcquired(RuntimeError):
    pass


class NotAcquired(RuntimeError):
    pass


class AlreadyStarted(RuntimeError):
    pass


class TimeoutNotUsable(RuntimeError):
    pass


class InvalidTimeout(RuntimeError):
    pass


class TimeoutTooLarge(RuntimeError):
    pass


class NotExpirable(RuntimeError):
    pass


class Lock(object):
    """
    A Lock context manager implemented via redis SETNX/BLPOP.
    """

    unlock_script = None
    extend_script = None
    reset_script = None         # 过期重置脚本
    reset_all_script = None     # 重置所有脚本

    _lock_renewal_interval: float
    _lock_renewal_thread: Union[threading.Thread, None]

    def __init__(self, redis_client, name, expire=None, id=None, auto_renewal=False, strict=True, signal_expire=1000):
        """
        :param redis_client:
            An instance of :class:`~StrictRedis`.
        :param name:
            The name (redis key) the lock should have.
        :param expire:
            The lock expiry time in seconds. If left at the default (None)
            the lock will not expire.
        :param id:
            The ID (redis value) the lock should have. A random value is
            generated when left at the default.
            Note that if you specify this then the lock is marked as "held". Acquires
            won't be possible.
        :param auto_renewal:
            If set to ``True``, Lock will automatically renew the lock so that it
            doesn't expire for as long as the lock is held (acquire() called
            or running in a context manager).
            Implementation note: Renewal will happen using a daemon thread with
            an interval of ``expire*2/3``. If wishing to use a different renewal
            time, subclass Lock, call ``super().__init__()`` then set
            ``self._lock_renewal_interval`` to your desired interval.
        :param strict:
            If set ``True`` then the ``redis_client`` needs to be an instance of ``redis.StrictRedis``.
        :param signal_expire:
            Advanced option to override signal list expiration in milliseconds. Increase it for very slow clients. Default: ``1000``.
        """
        # strict 是否为 True 并且 redis_client 不是 redis的实例
        if strict and not isinstance(redis_client, StrictRedis):
            # 报错
            raise ValueError("redis_client must be instance of StrictRedis. Use strict=False if you know what you're doing.")
        # 如果 设置了过期更新 但是 没有 设置 过期时间
        if auto_renewal and expire is None:
            # 报错
            raise ValueError("Expire may not be None when auto_renewal is set")

        # 将redis实例 变成 类变量
        self._client = redis_client

        # 如果 填写了过期时间
        if expire:
            # 转换一下 变为 int类型
            expire = int(expire)
            # 如果 是小于 0的  则报错
            if expire < 0:
                raise ValueError("A negative expire is not acceptable.")
        else:
            expire = None
        # 将过期时间 变为 类变量
        self._expire = expire

        # 信号过期时间
        self._signal_expire = signal_expire
        # 如果 id 未被指定  将加密成一个随机的字符
        if id is None:
            self._id = b64encode(urandom(18)).decode('ascii')
        # 如果 设置了值 判断是否是2进制  解码成 ascii编码
        elif isinstance(id, bytes):
            try:
                self._id = id.decode('ascii')
            except UnicodeDecodeError:
                self._id = b64encode(id).decode('ascii')
        # 如果是str  就直接赋值
        elif isinstance(id, str):
            self._id = id
        else:
            raise TypeError(f"Incorrect type for `id`. Must be bytes/str not {type(id)}.")

        # key的名字
        self._name = 'lock:' + name
        # 信号的名字
        self._signal = 'lock-signal:' + name
        # 如果设置了 过期更新  获取 过期时间的 2/3 的时间   用来更新用
        self._lock_renewal_interval = float(expire) * 2 / 3 if auto_renewal else None
        # 线程的记时器  用来 更新 key的过期时间
        self._lock_renewal_thread = None

        self.register_scripts(redis_client)

    @classmethod
    def register_scripts(cls, redis_client):
        """
        获取全局变量 reset_all_script
        如果 还未被赋值
        注册脚本 进去 分别为:
        reset_all_script    重置所有脚本
        unlock_script       解锁脚本
        extend_script       用来 重置过期时间的脚本
        reset_script        删除key脚本
        """
        global reset_all_script
        if reset_all_script is None:
            reset_all_script = redis_client.register_script(RESET_ALL_SCRIPT)
            cls.unlock_script = redis_client.register_script(UNLOCK_SCRIPT)
            cls.extend_script = redis_client.register_script(EXTEND_SCRIPT)
            cls.reset_script = redis_client.register_script(RESET_SCRIPT)
            cls.reset_all_script = redis_client.register_script(RESET_ALL_SCRIPT)

    @property
    def _held(self):
        """
        :return: 判断 redis 的 key的value 值 是否 等于 id
        """
        return self.id == self.get_owner_id()

    def reset(self):
        """
        Forcibly deletes the lock. Use this with care.
        """
        self.reset_script(client=self._client, keys=(self._name, self._signal), args=(self.id, self._signal_expire))

    @property
    def id(self):
        return self._id

    def get_owner_id(self):
        """
        :return: 返回解密后 value值
        """
        # 获取 redis 的 value值
        owner_id = self._client.get(self._name)
        # 判断是否是 二进制
        if isinstance(owner_id, bytes):
            # 如果是二进制 以 ascii编码进行解码
            owner_id = owner_id.decode('ascii', 'replace')      # replace 报错
        return owner_id

    def acquire(self, blocking=True, timeout=None):
        """
        :param blocking:
            Boolean value specifying whether lock should be blocking or not.
        :param timeout:
            An integer value specifying the maximum number of seconds to block.
        """
        logger_for_acquire.debug("Acquiring Lock(%r) ...", self._name)

        if self._held:  # 如果redis 已存在key 的时候 返回错误
            raise AlreadyAcquired("已经从这个Lock实例获取")

        if not blocking and timeout is not None:
            raise TimeoutNotUsable("如果 blocking=False 则不能使用Timeout不能为 None")

        if timeout:         # 如果填写超时时间
            timeout = int(timeout)
            if timeout < 0:
                raise InvalidTimeout(f"Timeout ({timeout}) 不能小于等于0")
            # 如果 超时更新时间  和  没有 2/3 超时更新时间  和 超时时间 大于 超时更新时间
            if self._expire and not self._lock_renewal_interval and timeout > self._expire:
                raise TimeoutTooLarge(f"Timeout ({timeout}) 不能大于 expire ({self._expire})")

        busy = True
        # 如果 此函数中有填写超时时间  使用此函数的超时时间   如果没有  实现 类变量的值
        blpop_timeout = timeout or self._expire or 0
        timed_out = False
        while busy:
            # 在 redis 中设置一个值 key: self._name   value: self._id  原子操作(不能被拆分)  超时时间: self._expire
            busy = not self._client.set(self._name, self._id, nx=True, ex=self._expire)     # 一般返回 False 说明设置成功 退出循环
            if busy:
                if timed_out:
                    return False
                elif blocking:
                    # 用于检查 是否能连接上  能连接上  等待    不能就返回 False
                    timed_out = not self._client.blpop(self._signal, blpop_timeout) and timeout
                else:
                    logger_for_acquire.warning("获取Lock失败 (%r).", self._name)
                    return False
        # 是否应该去刷新过期时间, 不是一定要这样做, 这是有风险, 如果当前的进程没有挂, 但是一直阻塞, 退不出来, 就会永远一直续租
        logger_for_acquire.info("Acquired Lock(%r).", self._name)
        if self._lock_renewal_interval is not None:
            self._start_lock_renewer()
        return True

    def extend(self, expire=None):
        """
        Extends expiration time of the lock.
        :param expire:
            New expiration time. If ``None`` - `expire` provided during
            lock initialization will be taken.
        """
        if expire:                          # 如果存在权限的过期时间
            expire = int(expire)
            if expire < 0:
                raise ValueError("负过期是不可接受的")
        elif self._expire is not None:      # 如果 类变量 过期时间 不为空
            expire = self._expire
        else:
            raise TypeError("要扩展锁，必须在extend()方法的参数或初始化时提供'expire'")

        # 执行 lua 脚本  提供所需要的参数
        error = self.extend_script(client=self._client, keys=(self._name, self._signal), args=(self._id, expire))
        if error == 1:
            raise NotAcquired(f"Lock {self._name} is not acquired or it already expired.")
        elif error == 2:
            raise NotExpirable(f"Lock {self._name} has no assigned expiration time")
        elif error:
            raise RuntimeError(f"Unsupported error code {error} from EXTEND script")

    @staticmethod
    def _lock_renewer(name, lockref, interval, stop):
        """
        Renew the lock key in redis every `interval` seconds for as long
        as `self._lock_renewal_thread.should_exit` is False.
        """
        while not stop.wait(timeout=interval):          # 会被阻塞在这里  如果是超时 返回 not False    被唤醒 返回 not True
            logger_for_refresh_thread.debug("Refreshing Lock(%r).", name)
            lock: "Lock" = lockref()                    # 弱引用 在线程里使用
            if lock is None:
                logger_for_refresh_thread.debug("停止循环，因为锁(%r)已被垃圾回收 ", name)
                break
            lock.extend(expire=lock._expire)
            del lock        # 删除 弱引用
        logger_for_refresh_thread.debug("Exiting renewal thread for Lock(%r).", name)

    def _start_lock_renewer(self):
        """
        启动锁刷新线程
        """
        # 如果 线程的记时器 不为空
        if self._lock_renewal_thread is not None:
            raise AlreadyStarted("锁刷新线程已经启动")

        logger_for_refresh_start.debug(
            "Starting renewal thread for Lock(%r). Refresh interval: %s seconds.", self._name, self._lock_renewal_interval
        )
        self._lock_renewal_stop = threading.Event()     # 事件管理标志
        self._lock_renewal_thread = threading.Thread(
            group=None,
            target=self._lock_renewer,                  # 要执行的函数
            kwargs={                                    # 携带的参数
                'name': self._name,
                'lockref': weakref.ref(self),
                'interval': self._lock_renewal_interval,
                'stop': self._lock_renewal_stop,
            },
        )
        self._lock_renewal_thread.demon = True
        self._lock_renewal_thread.start()               # 开启线程

    def _stop_lock_renewer(self):
        """
        Stop the lock renewer.
        This signals the renewal thread and waits for its exit.
        """
        # 如果线程计时器为空 或者 线程计时器 已经死掉
        if self._lock_renewal_thread is None or not self._lock_renewal_thread.is_alive():
            return
        logger_for_refresh_shutdown.debug("Signaling renewal thread for Lock(%r) to exit.", self._name)
        # 事件管理下 的 线程唤醒 因为是主动唤醒  所有 为 True  就跳出 while 循环
        self._lock_renewal_stop.set()

        self._lock_renewal_thread.join()
        self._lock_renewal_thread = None
        logger_for_refresh_exit.debug("Renewal thread for Lock(%r) exited.", self._name)

    def __enter__(self):    # 用来使用with语句
        acquired = self.acquire(blocking=True)
        if not acquired:
            raise AssertionError(f"Lock({self._name}) wasn't acquired, but blocking=True was used!")
        return self

    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        self.release()

    def release(self):
        """Releases the lock, that was acquired with the same object.
        .. note::
            If you want to release a lock that you acquired in a different place you have two choices:
            * Use ``Lock("name", id=id_from_other_place).release()``
            * Use ``Lock("name").reset()``
        """
        # 线程的记时器 不为空
        if self._lock_renewal_thread is not None:
            self._stop_lock_renewer()
        logger_for_release.debug("Releasing Lock(%r).", self._name)

        # 执行 lua脚本 和lua所需要的参数
        error = self.unlock_script(client=self._client, keys=(self._name, self._signal), args=(self._id, self._signal_expire))
        if error == 1:
            raise NotAcquired(f"Lock({self._name}) is not acquired or it already expired.")
        elif error:
            raise RuntimeError(f"Unsupported error code {error} from EXTEND script.")

    def locked(self):
        """
        Return true if the lock is acquired.
        Checks that lock with same name already exists. This method returns true, even if
        lock have another id.
        """
        return self._client.exists(self._name) == 1


reset_all_script = None


def reset_all(redis_client):
    """
    强制删除所有锁，如果它仍然存在(比如崩溃原因)。 小心使用。
    :param redis_client:
        An instance of :class:`~StrictRedis`.
    """
    Lock.register_scripts(redis_client)

    reset_all_script(client=redis_client)  # noqa