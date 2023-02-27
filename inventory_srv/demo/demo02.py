# encoding=utf8

import threading
from time import sleep


def test(n, event):
    print(event.wait())

    while event.isSet():
        print('Thread %s is running' % n)
        sleep(1)


def main():
    event = threading.Event()
    a = None
    for i in range(1):
        th = threading.Thread(target=test, args=(i, event))
        th.start()
        a = th

    event.set()
    print(2222222222)
    a.join()
    a = None


    print(111111111111111)


if __name__ == '__main__':
    main()