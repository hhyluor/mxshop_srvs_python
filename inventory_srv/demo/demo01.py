class A:
    def __init__(self):
        self._a = 10

    @property
    def a(self):
        return self._a

    def b(self):
        return 10

    def aaa(self):
        print(self.a)
        print(self.a == self.b())


if __name__ == '__main__':
    z = A()
    z.aaa()
