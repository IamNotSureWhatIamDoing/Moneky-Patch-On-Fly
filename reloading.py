# This module provides a base class, Reloadable.
# Reloadable classes, and modules containing them, will automatically be
# reloaded when they're changed. Furthermore, the old class will have new
# methods monkey-patched in, so existing instances of a class will use
# the new version of the class's methods.

import sys
import weakref
import os
import fcntl
import signal
import traceback


# (module_name, class_name) -> class
reloadable_classes = weakref.WeakValueDictionary()

# module -> (mtime, dir)
reloadable_modules = {}

# dir -> fd
dir_fds = {}


def module_source(module):
    """Return the source file name of a module."""
    filename = module.__file__
    base, ext = os.path.splitext(filename)
    if ext in (".pyc", ".pyo"):
        return base + ".py"
    else:
        return filename


def watch_module(module):
    """Reload a module when it changes."""
    source = module_source(module)
    dirname = os.path.dirname(source)
    watch_dir(dirname)
    reloadable_modules[module] = (os.stat(source).st_mtime, dirname)


def watch_dir(dirname):
    """Watch a directory for changes."""
    dirname = os.path.abspath(dirname)
    if dirname not in dir_fds:
        if not dir_fds:
            signal.signal(signal.SIGIO, handle_sigio)
        fd = os.open(dirname, os.O_RDONLY)
        fcntl.fcntl(fd, fcntl.F_NOTIFY, fcntl.DN_MULTISHOT | fcntl.DN_MODIFY)
        dir_fds[dirname] = fd


def handle_sigio(signum, frame):
    """Signal handler for SIGIO. Checks timestamps for all watched
    modules and reloads changed ones."""
    for module, (mtime, dirname) in reloadable_modules.iteritems():
        try:
            new_mtime = os.stat(module_source(module)).st_mtime
        except OSError:
            # It has disappeared. It'll probably re-appear again soon. ;)
            pass
        else:
            if new_mtime > mtime:
                reloadable_modules[module] = (new_mtime, dirname)
                try:
                    reload(module)
                except:
                    traceback.print_exc()


class Reloadable(object):
    """Base class for automatically reloaded classes."""
    class __metaclass__(type):
        def __new__(mcs, name, bases, dict):
            module = dict["__module__"]
            if module.endswith("reloading") and name == "Reloadable":
                # Seems to be the best check we can reasonably do to avoid
                # reloading the reloading module (which would be horrendously
                # confusing and would trash the global variables!)
                return type.__new__(mcs, name, bases, dict)
            else:
                old_class = reloadable_classes.get((module, name))
                if old_class is None:
                    # First definition. Create class as normal but watch the
                    # module for changes.
                    cls = type.__new__(mcs, name, bases, dict)
                    watch_module(sys.modules[module])
                    reloadable_classes[(module, name)] = cls
                    return cls
                else:
                    # Subsequent definition. Steal all the methods and
                    # monkey-patch them into the old class, without actually
                    # creating a new class.
                    for k, v in dict.iteritems():
                        setattr(old_class, k, v)
                    return old_class



class ReloMeta(type):
    """Base metaclass for automatically reloaded classes."""
    def __new__(mcs, name, bases, dict):
        module = dict["__module__"]
        if module.endswith("reloading") and name == "Reloadable":
            # Seems to be the best check we can reasonably do to avoid
            # reloading the reloading module (which would be horrendously
            # confusing and would trash the global variables!)
            return type.__new__(mcs, name, bases, dict)
        else:
            old_class = reloadable_classes.get((module, name))
            if old_class is None:
                # First definition. Create class as normal but watch the
                # module for changes.
                cls = type.__new__(mcs, name, bases, dict)
                watch_module(sys.modules[module])
                reloadable_classes[(module, name)] = cls
                return cls
            else:
                # Subsequent definition. Steal all the methods and
                # monkey-patch them into the old class, without actually
                # creating a new class.
                for k, v in dict.iteritems():
                    setattr(old_class, k, v)
                return old_class
