from datetime import datetime

from peewee import *
from settings import settings


class BaseModel(Model):
    add_time = DateTimeField(default=datetime.now, verbose_name="添加时间")
    update_time = DateTimeField(default=datetime.now, verbose_name="更新时间")
    is_deleted = BooleanField(default=False, verbose_name="是否删除")

    def save(self, *args, **kwargs):
        # 判断这是一个新添加的数据还是更新的数据
        if self._pk is not None:
            # 这是一个新数据
            self.update_time = datetime.now()
        return super().save(*args, **kwargs)

    @classmethod
    def delete(cls, permanently=False):   # permanently 表示是否永久删除
        if permanently:
            return super().delete()
        else:
            return super().update(is_deleted=True)

    def delete_instance(self, permanently=False, recursive=False, delete_nullable=False):
        if permanently:
            return self.delete(permanently).where(self._pk_expr()).execute()
        else:
            self.is_deleted = True
            self.save()

    @classmethod
    def select(cls, *fields):
        return super().select(*fields).where(cls.is_deleted==False)

    class Meta:
        database = settings.DB


class User(BaseModel):
    # 用户模型
    GENDER_CHOICES = (
        ("female", "女"),
        ("male", "男"),
    )

    ROLE_CHOICES = {
        (1, "普通用户"),
        (2, "管理员"),
    }

    mobile = CharField(max_length=11, index=True, unique=True, verbose_name="手机号码") # max_length:最大长度  index:在此列上创建索引  unique:在此列上创建唯一索引
    password = CharField(max_length=100, verbose_name="密码")     # 1.密文 2.密文不可反解
    nick_name = CharField(max_length=20, null=True, verbose_name="昵称")
    head_url = CharField(max_length=200, null=True, verbose_name="头像")
    birthday = DateField(null=True, verbose_name="生日")
    address = CharField(max_length=200, null=True, verbose_name="地址")
    desc = TextField(null=True, verbose_name="个人简介")
    # salt = CharField(max_length=200, null=True, verbose_name="")
    gender = CharField(max_length=6, choices=GENDER_CHOICES, null=True, verbose_name="性别")
    role = IntegerField(default=1, choices=ROLE_CHOICES, verbose_name="用户角色")


if __name__ == '__main__':
    from passlib.hash import pbkdf2_sha256
    import time
    from datetime import date

    # # 创建 表结构
    # settings.DB.create_tables([User])

    # # 1. 对称加密 2. 非对称加密
    # for i in range(10):
    #     user = User()
    #     user.nick_name = f"bobby{i}"
    #     user.mobile = f"1306735369{i}"
    #     user.password = pbkdf2_sha256.hash(f"admin123")
    #     user.save()

    user = User.select()
    user.limit(2).offset(2)

    for user in User.select():
        print(user.mobile)
        if user.birthday:
            u_time = time.mktime(user.birthday.timetuple())
            print(user.birthday)
            print(type(user.birthday))
            print(user.birthday.timetuple())
            print(u_time)
            print(date.fromtimestamp(u_time))
        # print(pbkdf2_sha256.verify("admin123"+user.nick_name[-1], user.password))
        print("===============")

