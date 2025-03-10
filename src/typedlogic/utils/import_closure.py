import importlib


def compute_import_closure(root_module_name):
    """
    Compute the import closure of a module.

    :param root_module_name:
    :return:
    """
    closure = {root_module_name}
    visited = set()

    def dfs(module_name):
        if module_name in visited:
            return
        visited.add(module_name)
        closure.add(module_name)

        module = importlib.import_module(module_name)

        # closure[root_module_name].add(module_name)

        for name, _ in module.__dict__.items():
            if name.startswith("__"):
                continue
            try:
                submodule = getattr(module, name)
                if hasattr(submodule, "__module__"):
                    dfs(submodule.__module__)
            except:
                pass

    dfs(root_module_name)
    return closure


def get_class_module(cls):
    return cls.__module__


def check_class_module_and_closure(c, closure):
    class_module = get_class_module(c)
    is_in_closure = class_module in closure

    print(f"Class {c.__name__} is declared in module: {class_module}")
    print(f"Is {class_module} in the import closure? {is_in_closure}")
