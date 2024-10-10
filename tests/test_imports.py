import os


def test_env():
    path = os.getenv("PATH")
    print(path)
