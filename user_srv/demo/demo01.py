from retrying import retry


def retry_error(exception):
    return isinstance(exception, NameError)
    # return isinstance(exception, Exception)


@retry(retry_on_exception=retry_error, stop_max_attempt_number=3)
def demo_():
    print('重试')
    print(a)


if __name__ == '__main__':
    demo_()