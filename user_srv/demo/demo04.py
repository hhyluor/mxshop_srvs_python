import time
from model.models import User


user = User.get(id=1)

print(user.birthday)
print(user.birthday.timetuple())
print(int(time.mktime(user.birthday.timetuple())))