import threading
import time


def libai():
    while True:
        print(event.isSet())
        time.sleep(0.05)


def dufu():
    event.set()
    event.clear()
    event.wait()



if __name__ == '__main__':

    event = threading.Event()
    # event.set()

    t1 = threading.Thread(target=libai)
    t2 = threading.Thread(target=dufu)

    t1.start()
    t2.start()
    t1.join()
    t2.join()