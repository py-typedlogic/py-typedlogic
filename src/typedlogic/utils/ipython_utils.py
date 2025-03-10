from IPython.lib.display import Code


def show(path):
    return Code(filename=path, language="python")
